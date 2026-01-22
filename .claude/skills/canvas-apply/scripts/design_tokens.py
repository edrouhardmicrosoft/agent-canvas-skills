#!/usr/bin/env python3
"""
Design Tokens - Detect and extract CSS custom properties (design tokens) from project files.

Scans for:
1. CSS custom properties (--variable-name) in CSS/SCSS files
2. Theme definitions in Tailwind v4 @theme blocks
3. CSS variables in :root and .dark selectors
4. Theme files (theme.js, tokens.json, etc.)
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class DesignToken:
    """A single design token."""

    name: str  # e.g., "primary", "background", "radius"
    variable: str  # e.g., "--color-primary", "--background"
    value: str  # The actual CSS value
    category: str  # "color", "spacing", "radius", "typography", "other"
    source_file: str
    scope: str = ":root"  # ":root", ".dark", etc.


@dataclass
class DesignTokens:
    """Collection of design tokens from a project."""

    tokens: list[DesignToken] = field(default_factory=list)
    source_files: list[str] = field(default_factory=list)

    def get_by_category(self, category: str) -> list[DesignToken]:
        """Get tokens by category."""
        return [t for t in self.tokens if t.category == category]

    def get_by_variable(self, variable: str) -> Optional[DesignToken]:
        """Get token by variable name."""
        for t in self.tokens:
            if t.variable == variable:
                return t
        return None

    def find_matching_token(
        self, value: str, category: str = ""
    ) -> Optional[DesignToken]:
        """Find a token that matches the given value."""
        normalized_value = normalize_css_value(value)

        for token in self.tokens:
            if category and token.category != category:
                continue
            if normalize_css_value(token.value) == normalized_value:
                return token

        return None


def normalize_css_value(value: str) -> str:
    """Normalize a CSS value for comparison."""
    value = value.strip().lower()

    # Normalize rgb to hex
    rgb_match = re.match(r"rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", value)
    if rgb_match:
        r, g, b = (
            int(rgb_match.group(1)),
            int(rgb_match.group(2)),
            int(rgb_match.group(3)),
        )
        return f"#{r:02x}{g:02x}{b:02x}"

    # Normalize hex shorthand
    if value.startswith("#") and len(value) == 4:
        return f"#{value[1] * 2}{value[2] * 2}{value[3] * 2}"

    return value


def categorize_token(name: str, value: str) -> str:
    """Determine the category of a token based on its name and value."""
    name_lower = name.lower()
    value_lower = value.lower()

    # Color indicators
    color_keywords = [
        "color",
        "bg",
        "background",
        "border",
        "text",
        "foreground",
        "accent",
        "primary",
        "secondary",
        "muted",
        "destructive",
        "ring",
        "chart",
    ]
    if any(kw in name_lower for kw in color_keywords):
        return "color"
    if (
        value.startswith("#")
        or value.startswith("rgb")
        or value.startswith("hsl")
        or value.startswith("oklch")
    ):
        return "color"

    # Spacing indicators
    spacing_keywords = ["space", "gap", "padding", "margin", "size", "width", "height"]
    if any(kw in name_lower for kw in spacing_keywords):
        return "spacing"
    if re.match(r"^[\d.]+(px|rem|em)$", value_lower):
        return "spacing"

    # Radius indicators
    if "radius" in name_lower or "rounded" in name_lower:
        return "radius"

    # Typography indicators
    typography_keywords = ["font", "text", "line", "letter", "weight"]
    if any(kw in name_lower for kw in typography_keywords):
        return "typography"

    return "other"


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


def extract_css_variables(content: str, file_path: str) -> list[DesignToken]:
    """Extract CSS custom properties from CSS content."""
    tokens = []

    # Find all selector blocks
    block_pattern = r"([^{]+)\s*\{([^}]+)\}"

    for match in re.finditer(block_pattern, content):
        selector = match.group(1).strip()
        block_content = match.group(2)

        # Skip @theme blocks (handled separately)
        if "@theme" in selector:
            continue

        # Extract variable definitions: --name: value;
        var_pattern = r"--([a-zA-Z0-9_-]+)\s*:\s*([^;]+);"

        for var_match in re.finditer(var_pattern, block_content):
            var_name = var_match.group(1)
            var_value = var_match.group(2).strip()

            # Skip references to other variables for the value
            if var_value.startswith("var("):
                continue

            # Clean up selector for scope
            scope = selector.split("\n")[-1].strip()
            if not scope or scope.startswith("@"):
                scope = ":root"

            category = categorize_token(var_name, var_value)

            tokens.append(
                DesignToken(
                    name=var_name,
                    variable=f"--{var_name}",
                    value=var_value,
                    category=category,
                    source_file=file_path,
                    scope=scope,
                )
            )

    return tokens


def extract_tailwind_v4_theme(content: str, file_path: str) -> list[DesignToken]:
    """Extract tokens from Tailwind v4 @theme blocks."""
    tokens = []

    # Find @theme blocks
    theme_pattern = r"@theme\s+(?:inline\s+)?\{([^}]+)\}"

    for match in re.finditer(theme_pattern, content, re.DOTALL):
        block_content = match.group(1)

        # Extract variable definitions
        var_pattern = r"--([a-zA-Z0-9_-]+)\s*:\s*([^;]+);"

        for var_match in re.finditer(var_pattern, block_content):
            var_name = var_match.group(1)
            var_value = var_match.group(2).strip()

            # Skip references to other variables
            if var_value.startswith("var("):
                continue

            category = categorize_token(var_name, var_value)

            tokens.append(
                DesignToken(
                    name=var_name,
                    variable=f"--{var_name}",
                    value=var_value,
                    category=category,
                    source_file=file_path,
                    scope="@theme",
                )
            )

    return tokens


def extract_from_json_theme(content: str, file_path: str) -> list[DesignToken]:
    """Extract tokens from JSON theme files (tokens.json, theme.json)."""
    tokens = []

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return tokens

    def traverse(obj: dict, prefix: str = ""):
        for key, value in obj.items():
            full_name = f"{prefix}-{key}" if prefix else key

            if isinstance(value, dict):
                # Check if it's a token definition (has 'value' key)
                if "value" in value:
                    token_value = value["value"]
                    category = categorize_token(full_name, str(token_value))
                    tokens.append(
                        DesignToken(
                            name=full_name,
                            variable=f"--{full_name}",
                            value=str(token_value),
                            category=category,
                            source_file=file_path,
                            scope="json",
                        )
                    )
                else:
                    traverse(value, full_name)
            elif isinstance(value, str):
                category = categorize_token(full_name, value)
                tokens.append(
                    DesignToken(
                        name=full_name,
                        variable=f"--{full_name}",
                        value=value,
                        category=category,
                        source_file=file_path,
                        scope="json",
                    )
                )

    traverse(data)
    return tokens


def extract_tokens(root: Optional[Path] = None) -> DesignTokens:
    """
    Extract all design tokens from a project.

    Scans CSS files, theme files, and configuration.
    """
    if root is None:
        root = find_project_root()

    result = DesignTokens()
    skip_dirs = {"node_modules", ".next", "dist", "build", ".git", ".canvas"}

    # Scan CSS files
    for css_file in root.glob("**/*.css"):
        if any(skip in css_file.parts for skip in skip_dirs):
            continue

        try:
            content = css_file.read_text()
            file_path = str(css_file)

            # Extract from @theme blocks (Tailwind v4)
            theme_tokens = extract_tailwind_v4_theme(content, file_path)
            if theme_tokens:
                result.tokens.extend(theme_tokens)
                if file_path not in result.source_files:
                    result.source_files.append(file_path)

            # Extract regular CSS variables
            css_tokens = extract_css_variables(content, file_path)
            if css_tokens:
                result.tokens.extend(css_tokens)
                if file_path not in result.source_files:
                    result.source_files.append(file_path)

        except Exception:
            continue

    # Scan SCSS files
    for scss_file in root.glob("**/*.scss"):
        if any(skip in scss_file.parts for skip in skip_dirs):
            continue

        try:
            content = scss_file.read_text()
            file_path = str(scss_file)

            css_tokens = extract_css_variables(content, file_path)
            if css_tokens:
                result.tokens.extend(css_tokens)
                if file_path not in result.source_files:
                    result.source_files.append(file_path)

        except Exception:
            continue

    # Scan JSON theme files
    theme_file_patterns = ["tokens.json", "theme.json", "design-tokens.json"]
    for pattern in theme_file_patterns:
        for json_file in root.glob(f"**/{pattern}"):
            if any(skip in json_file.parts for skip in skip_dirs):
                continue

            try:
                content = json_file.read_text()
                file_path = str(json_file)

                json_tokens = extract_from_json_theme(content, file_path)
                if json_tokens:
                    result.tokens.extend(json_tokens)
                    if file_path not in result.source_files:
                        result.source_files.append(file_path)

            except Exception:
                continue

    return result


def suggest_token_for_value(
    tokens: DesignTokens,
    css_property: str,
    css_value: str,
) -> Optional[tuple[DesignToken, str]]:
    """
    Suggest a design token to use instead of a hardcoded value.

    Returns (token, css_usage) where css_usage is like "var(--color-primary)".
    """
    # Determine category from property
    property_lower = css_property.lower()

    category = ""
    if property_lower in ("color", "background-color", "border-color"):
        category = "color"
    elif property_lower in ("padding", "margin", "gap", "width", "height"):
        category = "spacing"
    elif property_lower in ("border-radius",):
        category = "radius"

    # Find matching token
    token = tokens.find_matching_token(css_value, category)

    if token:
        css_usage = f"var({token.variable})"
        return token, css_usage

    return None


def tokens_to_dict(tokens: DesignTokens) -> dict:
    """Convert DesignTokens to JSON-serializable dict."""
    return {
        "sourceFiles": tokens.source_files,
        "tokenCount": len(tokens.tokens),
        "tokens": [
            {
                "name": t.name,
                "variable": t.variable,
                "value": t.value,
                "category": t.category,
                "sourceFile": t.source_file,
                "scope": t.scope,
            }
            for t in tokens.tokens
        ],
        "byCategory": {
            "color": len(tokens.get_by_category("color")),
            "spacing": len(tokens.get_by_category("spacing")),
            "radius": len(tokens.get_by_category("radius")),
            "typography": len(tokens.get_by_category("typography")),
            "other": len(tokens.get_by_category("other")),
        },
    }


if __name__ == "__main__":
    import sys

    root = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    tokens = extract_tokens(root)

    print(json.dumps(tokens_to_dict(tokens), indent=2))
