#!/usr/bin/env python3
"""
Component Detector - AST-based component boundary detection for React/Vue/Svelte.

Improves file_finder.py's ability to map DOM selectors to the correct component file.

Uses regex-based heuristics (not full AST parsing) for:
1. React functional and class components
2. Vue Single File Components (.vue)
3. Svelte components (.svelte)

Returns component metadata including:
- Component name
- File path
- Exported elements
- Props/slots that might render content
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ComponentInfo:
    """Information about a detected component."""

    name: str
    file_path: str
    framework: str  # "react", "vue", "svelte"
    export_type: str  # "default", "named", "both"
    line_number: int
    rendered_tags: list[str] = field(
        default_factory=list
    )  # HTML tags returned/rendered
    class_names: list[str] = field(
        default_factory=list
    )  # Class names used in component
    ids: list[str] = field(default_factory=list)  # IDs used in component
    test_ids: list[str] = field(default_factory=list)  # data-testid values
    props: list[str] = field(default_factory=list)  # Component props
    confidence: float = 0.0  # How confident we are this is the right component


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


def detect_framework(file_path: str, content: str) -> str:
    """Detect the framework used in a file."""
    path = Path(file_path)

    if path.suffix == ".vue":
        return "vue"
    if path.suffix == ".svelte":
        return "svelte"

    # Check for React patterns
    if path.suffix in (".tsx", ".jsx", ".ts", ".js"):
        if re.search(r"import\s+.*?React", content):
            return "react"
        if re.search(r"from\s+['\"]react['\"]", content):
            return "react"
        if re.search(r"import\s+{[^}]*useState|useEffect|useRef", content):
            return "react"
        # JSX return pattern
        if re.search(r"return\s*\(\s*<", content):
            return "react"

    return "unknown"


def extract_react_components(content: str, file_path: str) -> list[ComponentInfo]:
    """Extract React component information from file content."""
    components = []

    # Pattern 1: Function components with explicit return
    # export function ComponentName(...) { ... return (<...>) }
    func_pattern = r"(?:export\s+)?(function|const|let)\s+([A-Z][a-zA-Z0-9]*)\s*[=:]?\s*(?:\([^)]*\)|[^=]*=>)"

    for match in re.finditer(func_pattern, content):
        decl_type = match.group(1)
        comp_name = match.group(2)
        line_number = content[: match.start()].count("\n") + 1

        # Check if it's exported
        pre_match = content[max(0, match.start() - 20) : match.start()]
        export_type = (
            "default"
            if "export default" in pre_match
            else "named"
            if "export" in pre_match
            else "none"
        )

        # Extract JSX from the component
        # Find the component body (simplified - looks for return statement)
        comp_start = match.end()
        jsx_content = extract_jsx_content(content[comp_start:])

        # Extract identifiers from JSX
        class_names = extract_classnames(jsx_content)
        ids = extract_ids(jsx_content)
        test_ids = extract_testids(jsx_content)
        rendered_tags = extract_tags(jsx_content)

        components.append(
            ComponentInfo(
                name=comp_name,
                file_path=file_path,
                framework="react",
                export_type=export_type,
                line_number=line_number,
                rendered_tags=rendered_tags,
                class_names=class_names,
                ids=ids,
                test_ids=test_ids,
            )
        )

    # Pattern 2: Arrow function default exports
    # export default function() or export default () =>
    default_pattern = r"export\s+default\s+(?:function\s*)?(\([^)]*\)|[a-zA-Z_][a-zA-Z0-9_]*)\s*(?:=>|{)"

    for match in re.finditer(default_pattern, content):
        line_number = content[: match.start()].count("\n") + 1

        # Try to get component name from file
        comp_name = Path(file_path).stem
        if comp_name == "index":
            comp_name = Path(file_path).parent.name

        # Check if we already have this component
        if any(c.name == comp_name for c in components):
            continue

        comp_start = match.end()
        jsx_content = extract_jsx_content(content[comp_start:])

        class_names = extract_classnames(jsx_content)
        ids = extract_ids(jsx_content)
        test_ids = extract_testids(jsx_content)
        rendered_tags = extract_tags(jsx_content)

        components.append(
            ComponentInfo(
                name=comp_name,
                file_path=file_path,
                framework="react",
                export_type="default",
                line_number=line_number,
                rendered_tags=rendered_tags,
                class_names=class_names,
                ids=ids,
                test_ids=test_ids,
            )
        )

    return components


def extract_vue_components(content: str, file_path: str) -> list[ComponentInfo]:
    """Extract Vue SFC component information."""
    components = []

    # Get component name from file
    comp_name = Path(file_path).stem

    # Extract template content
    template_match = re.search(r"<template[^>]*>(.*?)</template>", content, re.DOTALL)
    template_content = template_match.group(1) if template_match else ""

    # Extract script for component name override
    script_match = re.search(r"<script[^>]*>(.*?)</script>", content, re.DOTALL)
    if script_match:
        script_content = script_match.group(1)
        # Look for name: 'ComponentName' pattern
        name_match = re.search(r"name:\s*['\"]([^'\"]+)['\"]", script_content)
        if name_match:
            comp_name = name_match.group(1)

    class_names = extract_classnames(template_content)
    ids = extract_ids(template_content)
    test_ids = extract_testids(template_content)
    rendered_tags = extract_tags(template_content)

    components.append(
        ComponentInfo(
            name=comp_name,
            file_path=file_path,
            framework="vue",
            export_type="default",
            line_number=1,
            rendered_tags=rendered_tags,
            class_names=class_names,
            ids=ids,
            test_ids=test_ids,
        )
    )

    return components


def extract_svelte_components(content: str, file_path: str) -> list[ComponentInfo]:
    """Extract Svelte component information."""
    components = []

    # Get component name from file
    comp_name = Path(file_path).stem

    # In Svelte, the entire file is the component
    # Extract markup (everything outside script and style tags)
    markup = content
    markup = re.sub(r"<script[^>]*>.*?</script>", "", markup, flags=re.DOTALL)
    markup = re.sub(r"<style[^>]*>.*?</style>", "", markup, flags=re.DOTALL)

    class_names = extract_classnames(markup)
    ids = extract_ids(markup)
    test_ids = extract_testids(markup)
    rendered_tags = extract_tags(markup)

    components.append(
        ComponentInfo(
            name=comp_name,
            file_path=file_path,
            framework="svelte",
            export_type="default",
            line_number=1,
            rendered_tags=rendered_tags,
            class_names=class_names,
            ids=ids,
            test_ids=test_ids,
        )
    )

    return components


def extract_jsx_content(content: str) -> str:
    """Extract JSX content from a function body (simplified)."""
    # Find return statement with JSX
    return_match = re.search(
        r"return\s*\(?\s*(<[\s\S]*?>[\s\S]*?</[\s\S]*?>|<[\s\S]*?/>)", content
    )
    if return_match:
        return return_match.group(1)

    # Try finding JSX-like content
    jsx_match = re.search(
        r"(<[A-Za-z][^>]*>[\s\S]*?</[A-Za-z][^>]*>|<[A-Za-z][^>]*/>)", content[:2000]
    )
    if jsx_match:
        return jsx_match.group(1)

    return content[:2000]  # Return first 2000 chars as fallback


def extract_classnames(content: str) -> list[str]:
    """Extract className/class values from JSX/HTML content."""
    classes = set()

    # className="..." or class="..."
    patterns = [
        r'className\s*=\s*["\']([^"\']+)["\']',
        r'class\s*=\s*["\']([^"\']+)["\']',
        r'className\s*=\s*\{[`"\']([^`"\']+)[`"\']\}',
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, content):
            # Split by whitespace to get individual classes
            for cls in match.group(1).split():
                if cls and not cls.startswith("$"):  # Skip template variables
                    classes.add(cls)

    return list(classes)


def extract_ids(content: str) -> list[str]:
    """Extract id attribute values from JSX/HTML content."""
    ids = set()

    patterns = [
        r'id\s*=\s*["\']([^"\']+)["\']',
        r'id\s*=\s*\{[`"\']([^`"\']+)[`"\']\}',
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, content):
            ids.add(match.group(1))

    return list(ids)


def extract_testids(content: str) -> list[str]:
    """Extract data-testid values from JSX/HTML content."""
    testids = set()

    patterns = [
        r'data-testid\s*=\s*["\']([^"\']+)["\']',
        r'data-cy\s*=\s*["\']([^"\']+)["\']',
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, content):
            testids.add(match.group(1))

    return list(testids)


def extract_tags(content: str) -> list[str]:
    """Extract HTML/JSX tag names from content."""
    tags = set()

    # Match opening tags
    tag_pattern = r"<([a-z][a-z0-9]*)"
    for match in re.finditer(tag_pattern, content, re.IGNORECASE):
        tag = match.group(1).lower()
        if tag not in ("script", "style", "template"):  # Skip container tags
            tags.add(tag)

    return list(tags)


def detect_components(
    root: Optional[Path] = None,
    extensions: Optional[set[str]] = None,
) -> list[ComponentInfo]:
    """
    Detect all components in a project.

    Returns list of ComponentInfo sorted by file path.
    """
    if root is None:
        root = find_project_root()

    if extensions is None:
        extensions = {".tsx", ".jsx", ".vue", ".svelte"}

    skip_dirs = {"node_modules", ".next", "dist", "build", ".git", ".canvas"}
    components = []

    for ext in extensions:
        for file_path in root.glob(f"**/*{ext}"):
            if any(skip in file_path.parts for skip in skip_dirs):
                continue

            try:
                content = file_path.read_text()
                file_str = str(file_path)

                framework = detect_framework(file_str, content)

                if framework == "react":
                    comps = extract_react_components(content, file_str)
                elif framework == "vue":
                    comps = extract_vue_components(content, file_str)
                elif framework == "svelte":
                    comps = extract_svelte_components(content, file_str)
                else:
                    continue

                components.extend(comps)

            except Exception:
                continue

    return sorted(components, key=lambda c: c.file_path)


def score_component_match(
    component: ComponentInfo,
    selector: str,
    tag: Optional[str] = None,
    class_name: Optional[str] = None,
    element_id: Optional[str] = None,
    test_id: Optional[str] = None,
) -> float:
    """
    Score how well a component matches the given selector criteria.

    Returns confidence score 0.0 - 1.0.
    """
    score = 0.0
    max_score = 0.0

    # ID match (highest weight)
    if element_id:
        max_score += 1.0
        if element_id in component.ids:
            score += 1.0

    # Test ID match (high weight)
    if test_id:
        max_score += 0.9
        if test_id in component.test_ids:
            score += 0.9

    # Class name match (medium weight)
    if class_name:
        max_score += 0.7
        classes = set(class_name.split())
        component_classes = set(component.class_names)
        if classes & component_classes:  # Any intersection
            match_ratio = len(classes & component_classes) / len(classes)
            score += 0.7 * match_ratio

    # Tag match (low weight)
    if tag:
        max_score += 0.3
        if tag.lower() in [t.lower() for t in component.rendered_tags]:
            score += 0.3

    if max_score == 0:
        return 0.0

    return score / max_score


def find_component_for_selector(
    components: list[ComponentInfo],
    selector: str,
    tag: Optional[str] = None,
    class_name: Optional[str] = None,
    element_id: Optional[str] = None,
    test_id: Optional[str] = None,
) -> list[ComponentInfo]:
    """
    Find components that match the given selector criteria.

    Returns components sorted by match score (highest first).
    """
    scored = []

    for comp in components:
        score = score_component_match(
            comp,
            selector,
            tag=tag,
            class_name=class_name,
            element_id=element_id,
            test_id=test_id,
        )
        if score > 0:
            comp.confidence = score
            scored.append(comp)

    return sorted(scored, key=lambda c: -c.confidence)


def component_to_dict(comp: ComponentInfo) -> dict:
    """Convert ComponentInfo to JSON-serializable dict."""
    return {
        "name": comp.name,
        "filePath": comp.file_path,
        "framework": comp.framework,
        "exportType": comp.export_type,
        "lineNumber": comp.line_number,
        "renderedTags": comp.rendered_tags,
        "classNames": comp.class_names,
        "ids": comp.ids,
        "testIds": comp.test_ids,
        "confidence": round(comp.confidence, 3),
    }


if __name__ == "__main__":
    import json
    import sys

    root = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    components = detect_components(root)

    print(json.dumps([component_to_dict(c) for c in components], indent=2))
