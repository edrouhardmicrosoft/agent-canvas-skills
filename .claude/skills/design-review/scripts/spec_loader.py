#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pyyaml",
# ]
# ///
"""
Spec Loader - Parse design review specs from markdown files.

Supports:
- YAML frontmatter (name, version, extends)
- Pillars as H2 headers (## Pillar Name)
- Checks as H4 headers under ### Checks sections
- Check metadata: Severity, Description, Config, How to check
- Spec inheritance via `extends` field
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml


@dataclass
class Check:
    """A single design review check."""

    id: str
    pillar: str
    severity: str  # blocking, major, minor
    description: str
    config: dict[str, Any] = field(default_factory=dict)
    how_to_check: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "pillar": self.pillar,
            "severity": self.severity,
            "description": self.description,
            "config": self.config,
            "howToCheck": self.how_to_check,
        }


@dataclass
class Pillar:
    """A design pillar containing multiple checks."""

    name: str
    description: str
    checks: list[Check] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "checks": [c.to_dict() for c in self.checks],
        }


@dataclass
class DesignSpec:
    """Complete design specification."""

    name: str
    version: str
    extends: Optional[str]
    description: str = ""
    pillars: list[Pillar] = field(default_factory=list)
    overrides: dict[str, dict] = field(default_factory=dict)
    source_path: Optional[Path] = None
    format_type: str = "spec"  # "spec" or "skill"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "extends": self.extends,
            "description": self.description,
            "pillars": [p.to_dict() for p in self.pillars],
            "overrides": self.overrides,
            "sourcePath": str(self.source_path) if self.source_path else None,
            "formatType": self.format_type,
        }

    def get_all_checks(self) -> list[Check]:
        """Get flat list of all checks across all pillars."""
        checks = []
        for pillar in self.pillars:
            checks.extend(pillar.checks)
        return checks

    def get_check(self, check_id: str) -> Optional[Check]:
        """Get a check by ID."""
        for pillar in self.pillars:
            for check in pillar.checks:
                if check.id == check_id:
                    return check
        return None

    def get_checks_by_severity(self, severity: str) -> list[Check]:
        """Get all checks of a specific severity."""
        return [c for c in self.get_all_checks() if c.severity == severity]


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Extract YAML frontmatter and remaining content."""
    if not content.startswith("---"):
        return {}, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content

    try:
        frontmatter = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        frontmatter = {}

    remaining = parts[2].strip()
    return frontmatter, remaining


def detect_frontmatter_format(frontmatter: dict) -> str:
    """Detect if frontmatter is spec format or skill format."""
    if "version" in frontmatter or "extends" in frontmatter:
        return "spec"
    if "description" in frontmatter and "name" in frontmatter:
        return "skill"
    return "spec"


def parse_check_content(content: str, pillar_name: str, check_id: str) -> Check:
    """Parse the content under a check heading (H4)."""
    severity = "minor"  # default
    description = ""
    config: dict[str, Any] = {}
    how_to_check = ""

    lines = content.strip().split("\n")

    current_section = None
    current_content: list[str] = []

    for line in lines:
        stripped = line.strip()

        # Check for list items with metadata
        if stripped.startswith("- **Severity**:"):
            severity = stripped.split(":", 1)[1].strip().lower()
        elif stripped.startswith("- **Description**:"):
            description = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("- **How to check**:"):
            how_to_check = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("- **Config**:"):
            current_section = "config"
            current_content = []
        elif current_section == "config" and stripped.startswith("-"):
            # Parse config items like "  - minimum_ratio: 4.5"
            config_match = re.match(r"-\s*(\w+):\s*(.+)", stripped)
            if config_match:
                key = config_match.group(1)
                value = config_match.group(2)
                # Try to parse as number
                try:
                    if "." in value:
                        config[key] = float(value)
                    else:
                        config[key] = int(value)
                except ValueError:
                    config[key] = value
        elif stripped and not stripped.startswith("-"):
            # Reset current section on non-list content
            current_section = None

    return Check(
        id=check_id,
        pillar=pillar_name,
        severity=severity,
        description=description,
        config=config,
        how_to_check=how_to_check,
    )


def parse_spec_content(content: str) -> tuple[list[Pillar], dict[str, dict]]:
    """Parse spec content into pillars and overrides."""
    pillars: list[Pillar] = []
    overrides: dict[str, dict] = {}

    # Split by H2 headers (pillars)
    h2_pattern = r"^## (.+)$"
    h2_splits = re.split(h2_pattern, content, flags=re.MULTILINE)

    # First element is content before first H2 (if any)
    i = 1  # Skip content before first H2

    while i < len(h2_splits):
        pillar_name = h2_splits[i].strip()
        pillar_content = h2_splits[i + 1] if i + 1 < len(h2_splits) else ""
        i += 2

        # Check if this is the Overrides section
        if pillar_name.lower() == "overrides":
            # Parse overrides - they're H3 headers with check ID
            h3_pattern = r"^### (.+)$"
            h3_splits = re.split(h3_pattern, pillar_content, flags=re.MULTILINE)
            j = 1
            while j < len(h3_splits):
                check_id = h3_splits[j].strip()
                override_content = h3_splits[j + 1] if j + 1 < len(h3_splits) else ""
                j += 2

                # Parse override as simplified check
                override_check = parse_check_content(
                    override_content, "override", check_id
                )
                overrides[check_id] = {
                    "severity": override_check.severity,
                    "config": override_check.config,
                }
            continue

        # Get pillar description (text before ### Checks)
        desc_match = re.match(r"^([^#]+)", pillar_content, re.DOTALL)
        pillar_desc = desc_match.group(1).strip() if desc_match else ""

        # Find ### Checks section - capture until next H2 (##) or end, but not H4 (####)
        checks_match = re.search(
            r"### Checks\s*\n(.+?)(?=^## [^#]|\Z)",
            pillar_content,
            re.MULTILINE | re.DOTALL,
        )
        if not checks_match:
            # Pillar without checks section
            pillars.append(Pillar(name=pillar_name, description=pillar_desc, checks=[]))
            continue

        checks_content = checks_match.group(1)

        # Parse checks (H4 headers)
        h4_pattern = r"^#### (.+)$"
        h4_splits = re.split(h4_pattern, checks_content, flags=re.MULTILINE)

        checks: list[Check] = []
        k = 1
        while k < len(h4_splits):
            check_id = h4_splits[k].strip()
            check_content = h4_splits[k + 1] if k + 1 < len(h4_splits) else ""
            k += 2

            check = parse_check_content(check_content, pillar_name, check_id)
            checks.append(check)

        pillars.append(Pillar(name=pillar_name, description=pillar_desc, checks=checks))

    return pillars, overrides


def load_spec(path: Path, specs_dir: Optional[Path] = None) -> DesignSpec:
    """
    Load a design spec from a markdown file.
    Supports both spec format (version, extends) and skill format (name, description).
    """
    if not path.exists():
        raise FileNotFoundError(f"Spec file not found: {path}")

    content = path.read_text()
    frontmatter, body = parse_frontmatter(content)

    format_type = detect_frontmatter_format(frontmatter)

    name = frontmatter.get("name", path.stem)
    version = frontmatter.get("version", "1.0")
    extends = frontmatter.get("extends")
    description = frontmatter.get("description", "")

    pillars, overrides = parse_spec_content(body)

    spec = DesignSpec(
        name=name,
        version=version,
        extends=extends,
        description=description,
        pillars=pillars,
        overrides=overrides,
        source_path=path,
        format_type=format_type,
    )

    if extends and specs_dir:
        parent_path = specs_dir / extends
        if parent_path.exists():
            parent_spec = load_spec(parent_path, specs_dir)
            spec = merge_specs(parent_spec, spec)

    return spec


def merge_specs(parent: DesignSpec, child: DesignSpec) -> DesignSpec:
    """
    Merge child spec into parent spec.

    - Child pillars are added to parent pillars
    - Checks with same ID override parent checks
    - Child overrides are applied to matching checks
    """
    # Start with parent pillars
    merged_pillars: dict[str, Pillar] = {}
    for pillar in parent.pillars:
        merged_pillars[pillar.name] = Pillar(
            name=pillar.name,
            description=pillar.description,
            checks=list(pillar.checks),
        )

    # Add/merge child pillars
    for pillar in child.pillars:
        if pillar.name in merged_pillars:
            # Merge checks
            existing = merged_pillars[pillar.name]
            existing_ids = {c.id for c in existing.checks}

            for check in pillar.checks:
                if check.id in existing_ids:
                    # Replace existing check
                    existing.checks = [
                        c if c.id != check.id else check for c in existing.checks
                    ]
                else:
                    # Add new check
                    existing.checks.append(check)
        else:
            # New pillar
            merged_pillars[pillar.name] = pillar

    # Apply overrides
    for check_id, override in child.overrides.items():
        for pillar in merged_pillars.values():
            for check in pillar.checks:
                if check.id == check_id:
                    if "severity" in override:
                        check.severity = override["severity"]
                    if "config" in override:
                        check.config.update(override["config"])

    return DesignSpec(
        name=child.name,
        version=child.version,
        extends=child.extends,
        pillars=list(merged_pillars.values()),
        overrides={},  # Already applied
        source_path=child.source_path,
        format_type=child.format_type,
    )


def get_default_spec_path() -> Path:
    return Path(__file__).parent.parent / "specs" / "default.md"


def find_project_spec(project_root: Optional[Path] = None) -> Optional[Path]:
    """
    Find DESIGN-SPEC.md in project root.
    Returns None if not found.
    """
    if project_root is None:
        project_root = Path.cwd()

    candidates = [
        project_root / "DESIGN-SPEC.md",
        project_root / "design-spec.md",
        project_root / ".claude" / "DESIGN-SPEC.md",
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return None


def resolve_spec(
    spec_arg: Optional[str] = None,
    project_root: Optional[Path] = None,
) -> Path:
    """
    Resolve which spec to use with priority:
    1. Explicit --spec argument
    2. DESIGN-SPEC.md in project root
    3. Default spec (default.md)
    """
    specs_dir = Path(__file__).parent.parent / "specs"

    if spec_arg:
        spec_path = Path(spec_arg)
        if spec_path.is_absolute():
            return spec_path
        if (specs_dir / spec_arg).exists():
            return specs_dir / spec_arg
        if project_root and (project_root / spec_arg).exists():
            return project_root / spec_arg
        return specs_dir / spec_arg

    project_spec = find_project_spec(project_root)
    if project_spec:
        return project_spec

    return get_default_spec_path()


def list_specs(specs_dir: Optional[Path] = None) -> list[dict]:
    if specs_dir is None:
        specs_dir = Path(__file__).parent.parent / "specs"

    specs = []
    for path in specs_dir.glob("*.md"):
        if path.name == "README.md":
            continue
        try:
            content = path.read_text()
            frontmatter, _ = parse_frontmatter(content)
            specs.append(
                {
                    "file": path.name,
                    "name": frontmatter.get("name", path.stem),
                    "version": frontmatter.get("version", "1.0"),
                    "extends": frontmatter.get("extends"),
                }
            )
        except Exception:
            specs.append(
                {
                    "file": path.name,
                    "name": path.stem,
                    "version": "unknown",
                    "extends": None,
                }
            )

    return specs


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 2:
        print("Usage: spec_loader.py <spec_file> | --list")
        sys.exit(1)

    if sys.argv[1] == "--list":
        specs = list_specs()
        print(json.dumps({"ok": True, "specs": specs}, indent=2))
    else:
        spec_path = Path(sys.argv[1])
        if not spec_path.is_absolute():
            specs_dir = Path(__file__).parent.parent / "specs"
            spec_path = specs_dir / spec_path

        try:
            spec = load_spec(spec_path, spec_path.parent)
            print(json.dumps({"ok": True, "spec": spec.to_dict()}, indent=2))
        except FileNotFoundError as e:
            print(json.dumps({"ok": False, "error": str(e)}))
            sys.exit(1)
