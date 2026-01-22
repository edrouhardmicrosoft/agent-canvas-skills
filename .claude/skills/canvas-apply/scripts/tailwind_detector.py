#!/usr/bin/env python3
"""
Tailwind Detector - Detect if a project uses Tailwind CSS.

Checks for:
1. tailwind.config.js/ts/mjs/cjs files
2. @tailwind directives in CSS files
3. @import "tailwindcss" in CSS files (Tailwind v4)
4. tailwindcss in package.json dependencies
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class TailwindConfig:
    """Detected Tailwind configuration."""

    detected: bool = False
    version: Optional[str] = None  # "3.x" or "4.x" based on detection
    config_file: Optional[str] = None
    css_files_with_directives: list[str] = field(default_factory=list)
    custom_colors: dict[str, str] = field(default_factory=dict)
    custom_spacing: dict[str, str] = field(default_factory=dict)
    detection_method: str = ""


def find_project_root() -> Path:
    """Find project root by looking for .canvas or package.json."""
    current = Path.cwd()

    for parent in [current] + list(current.parents):
        if (parent / ".canvas").exists():
            return parent
        if (parent / "package.json").exists():
            return parent
        if (parent / ".git").exists():
            return parent

    return current


def check_tailwind_config(root: Path) -> Optional[tuple[str, str]]:
    """
    Check for Tailwind config files.

    Returns (config_path, detected_version) or None.
    """
    # Tailwind v3 and v4 config file patterns
    config_patterns = [
        "tailwind.config.js",
        "tailwind.config.ts",
        "tailwind.config.mjs",
        "tailwind.config.cjs",
    ]

    for pattern in config_patterns:
        config_path = root / pattern
        if config_path.exists():
            # Read config to detect version hints
            try:
                content = config_path.read_text()
                # v4 uses @config in CSS, v3 uses config file heavily
                # v4 configs tend to be simpler or use CSS-based config
                if "content:" in content or "theme:" in content:
                    return str(config_path), "3.x"
                return str(config_path), "3.x"  # Default to 3.x if config exists
            except Exception:
                return str(config_path), "3.x"

    return None


def check_css_directives(root: Path) -> list[tuple[str, str]]:
    """
    Check CSS files for Tailwind directives.

    Returns list of (css_file_path, detected_version).
    """
    results = []

    # Common CSS file locations
    css_patterns = [
        "**/*.css",
    ]

    # Skip directories
    skip_dirs = {"node_modules", ".next", "dist", "build", ".git"}

    for pattern in css_patterns:
        for css_file in root.glob(pattern):
            # Skip if in excluded directory
            if any(skip in css_file.parts for skip in skip_dirs):
                continue

            try:
                content = css_file.read_text()

                # Tailwind v4 detection: @import "tailwindcss"
                if re.search(r'@import\s+["\']tailwindcss["\']', content):
                    results.append((str(css_file), "4.x"))
                    continue

                # Tailwind v3 detection: @tailwind base/components/utilities
                if re.search(r"@tailwind\s+(base|components|utilities)", content):
                    results.append((str(css_file), "3.x"))
                    continue

                # Also detect v4 @theme directive
                if re.search(r"@theme\s+", content):
                    results.append((str(css_file), "4.x"))

            except Exception:
                continue

    return results


def check_package_json(root: Path) -> Optional[str]:
    """
    Check package.json for tailwindcss dependency.

    Returns version string or None.
    """
    package_json = root / "package.json"
    if not package_json.exists():
        return None

    try:
        data = json.loads(package_json.read_text())
        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}

        if "tailwindcss" in deps:
            version = deps["tailwindcss"]
            # Parse version to determine major version
            if version.startswith("^4") or version.startswith("4"):
                return "4.x"
            elif version.startswith("^3") or version.startswith("3"):
                return "3.x"
            return version

    except Exception:
        pass

    return None


def extract_v4_theme_colors(root: Path) -> dict[str, str]:
    """
    Extract custom colors from Tailwind v4 @theme blocks.

    Tailwind v4 defines colors like:
    @theme inline {
      --color-primary: #3b82f6;
    }
    """
    colors = {}

    for css_file in root.glob("**/*.css"):
        skip_dirs = {"node_modules", ".next", "dist", "build", ".git"}
        if any(skip in css_file.parts for skip in skip_dirs):
            continue

        try:
            content = css_file.read_text()

            # Find @theme blocks
            theme_blocks = re.findall(
                r"@theme\s+(?:inline\s+)?{([^}]+)}", content, re.DOTALL
            )

            for block in theme_blocks:
                # Extract color variables: --color-name: value;
                color_matches = re.findall(
                    r"--color-([a-zA-Z0-9-]+):\s*([^;]+);", block
                )
                for name, value in color_matches:
                    # Skip variables that reference other variables
                    if not value.strip().startswith("var("):
                        colors[name] = value.strip()

        except Exception:
            continue

    return colors


def extract_v3_config_colors(config_path: str) -> dict[str, str]:
    """
    Extract custom colors from Tailwind v3 config file.

    This is a simplified parser - full parsing would require JS evaluation.
    """
    colors = {}

    try:
        content = Path(config_path).read_text()

        # Look for colors in theme.extend.colors or theme.colors
        # This is a simple regex-based extraction for common patterns
        color_block = re.search(r"colors:\s*{([^}]+)}", content, re.DOTALL)

        if color_block:
            # Extract simple color definitions: colorName: '#hex' or 'rgb(...)'
            simple_colors = re.findall(
                r"['\"]?([a-zA-Z0-9-]+)['\"]?\s*:\s*['\"]([#a-zA-Z0-9(),.\s]+)['\"]",
                color_block.group(1),
            )
            for name, value in simple_colors:
                colors[name] = value

    except Exception:
        pass

    return colors


def detect_tailwind(root: Optional[Path] = None) -> TailwindConfig:
    """
    Detect Tailwind CSS configuration in a project.

    Checks multiple sources and returns consolidated configuration.
    """
    if root is None:
        root = find_project_root()

    config = TailwindConfig()

    # 1. Check for config file
    config_result = check_tailwind_config(root)
    if config_result:
        config.config_file = config_result[0]
        config.version = config_result[1]
        config.detected = True
        config.detection_method = "config_file"

    # 2. Check CSS directives
    css_results = check_css_directives(root)
    if css_results:
        config.css_files_with_directives = [r[0] for r in css_results]
        # Prefer v4 detection from CSS
        for path, version in css_results:
            if version == "4.x":
                config.version = "4.x"
                break
            config.version = version
        config.detected = True
        if not config.detection_method:
            config.detection_method = "css_directives"

    # 3. Check package.json
    pkg_version = check_package_json(root)
    if pkg_version:
        config.detected = True
        if not config.version:
            config.version = pkg_version
        if not config.detection_method:
            config.detection_method = "package_json"

    # 4. Extract custom colors based on version
    if config.detected:
        if config.version == "4.x":
            config.custom_colors = extract_v4_theme_colors(root)
        elif config.config_file:
            config.custom_colors = extract_v3_config_colors(config.config_file)

    return config


def config_to_dict(config: TailwindConfig) -> dict:
    """Convert TailwindConfig to JSON-serializable dict."""
    return {
        "detected": config.detected,
        "version": config.version,
        "configFile": config.config_file,
        "cssFilesWithDirectives": config.css_files_with_directives,
        "customColors": config.custom_colors,
        "customSpacing": config.custom_spacing,
        "detectionMethod": config.detection_method,
    }


if __name__ == "__main__":
    import sys

    root = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    config = detect_tailwind(root)

    print(json.dumps(config_to_dict(config), indent=2))
