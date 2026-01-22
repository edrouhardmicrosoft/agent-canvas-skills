#!/usr/bin/env python3
"""
File Finder - Map DOM selectors to source file locations.

Uses a multi-strategy approach to find where elements are defined in code:
1. ID attribute -> search for id="value"
2. data-testid -> search for data-testid="value"
3. className + tag -> search for <tag className="..." containing classes
4. Text content -> search for literal text in JSX/HTML

Returns candidates with confidence scores.
"""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# File extensions to search
SOURCE_EXTENSIONS = {".tsx", ".jsx", ".js", ".ts", ".html", ".vue", ".svelte"}

SKIP_DIRS = {"node_modules", ".next", ".git", "dist", "build", ".canvas", ".claude"}


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


@dataclass
class FileCandidate:
    """A potential source file match."""

    file_path: str
    line_number: int
    column: int
    confidence: float  # 0.0 - 1.0
    match_reasons: list[str] = field(default_factory=list)
    matched_text: str = ""
    context_lines: list[str] = field(default_factory=list)


@dataclass
class ElementQuery:
    """Query parameters for finding an element in source."""

    selector: str
    tag: str
    class_name: Optional[str] = None
    element_id: Optional[str] = None
    text: Optional[str] = None
    data_testid: Optional[str] = None
    selector_confidence: str = "medium"


def get_source_files(root: Optional[Path] = None) -> list[Path]:
    """Get all source files to search."""
    if root is None:
        root = find_project_root()
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Filter out skip directories
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

        for filename in filenames:
            if Path(filename).suffix in SOURCE_EXTENSIONS:
                files.append(Path(dirpath) / filename)

    return files


def extract_classes_from_selector(selector: str) -> list[str]:
    """Extract class names from a CSS selector."""
    classes = []

    # Split by . to get class parts
    parts = selector.split(".")

    for i, part in enumerate(parts):
        if not part:
            continue

        # First part might be the tag name
        if i == 0 and re.match(r"^[a-z][a-z0-9]*$", part):
            continue

        # Unescape Tailwind bracket notation
        class_name = part.replace("\\[", "[").replace("\\]", "]")

        # Remove pseudo-selectors
        class_name = re.sub(r":[a-z-]+$", "", class_name)

        if class_name:
            classes.append(class_name)

    return classes


def extract_tag_from_selector(selector: str) -> Optional[str]:
    """Extract the tag name from a CSS selector."""
    # Selector format: tag.class1.class2 or just .class1.class2
    parts = selector.split(".")
    if parts and parts[0] and re.match(r"^[a-z][a-z0-9]*$", parts[0]):
        return parts[0]
    return None


def search_by_id(files: list[Path], element_id: str) -> list[FileCandidate]:
    """Search for element by ID attribute."""
    candidates = []

    # Patterns to match id in various frameworks
    patterns = [
        rf'\bid\s*=\s*["\']({re.escape(element_id)})["\']',  # id="value" or id='value'
        rf'\bid:\s*["\']({re.escape(element_id)})["\']',  # Vue :id="value"
    ]

    for file_path in files:
        try:
            content = file_path.read_text()
            lines = content.split("\n")

            for pattern in patterns:
                for match in re.finditer(pattern, content):
                    # Find line number
                    line_start = content[: match.start()].count("\n")
                    col = match.start() - content.rfind("\n", 0, match.start()) - 1

                    # Get context lines
                    start_line = max(0, line_start - 2)
                    end_line = min(len(lines), line_start + 3)
                    context = lines[start_line:end_line]

                    candidates.append(
                        FileCandidate(
                            file_path=str(file_path),
                            line_number=line_start + 1,
                            column=col,
                            confidence=0.95,
                            match_reasons=["id attribute match"],
                            matched_text=match.group(0),
                            context_lines=context,
                        )
                    )
        except Exception:
            continue

    return candidates


def search_by_data_testid(files: list[Path], testid: str) -> list[FileCandidate]:
    """Search for element by data-testid attribute."""
    candidates = []

    patterns = [
        rf'data-testid\s*=\s*["\']({re.escape(testid)})["\']',
        rf'data-cy\s*=\s*["\']({re.escape(testid)})["\']',
    ]

    for file_path in files:
        try:
            content = file_path.read_text()
            lines = content.split("\n")

            for pattern in patterns:
                for match in re.finditer(pattern, content):
                    line_start = content[: match.start()].count("\n")
                    col = match.start() - content.rfind("\n", 0, match.start()) - 1

                    start_line = max(0, line_start - 2)
                    end_line = min(len(lines), line_start + 3)
                    context = lines[start_line:end_line]

                    candidates.append(
                        FileCandidate(
                            file_path=str(file_path),
                            line_number=line_start + 1,
                            column=col,
                            confidence=0.90,
                            match_reasons=["data-testid match"],
                            matched_text=match.group(0),
                            context_lines=context,
                        )
                    )
        except Exception:
            continue

    return candidates


def search_by_classname(
    files: list[Path],
    tag: Optional[str],
    classes: list[str],
) -> list[FileCandidate]:
    """Search for element by tag and className."""
    candidates = []

    if not classes:
        return candidates

    # Build patterns for different frameworks
    # We need to find className containing these classes (not necessarily all)

    for file_path in files:
        try:
            content = file_path.read_text()
            lines = content.split("\n")

            # For JSX/TSX: className="..." or className={...}
            # For HTML: class="..."
            # For Vue: :class="..." or class="..."

            class_patterns = [
                r'className\s*=\s*["\']([^"\']+)["\']',
                r'className\s*=\s*\{[`"\']([^`"\']+)[`"\']\}',
                r'class\s*=\s*["\']([^"\']+)["\']',
            ]

            for pattern in class_patterns:
                for match in re.finditer(pattern, content):
                    found_classes = match.group(1).split()

                    # Count how many of our target classes are present
                    matched_classes = [c for c in classes if c in found_classes]

                    if not matched_classes:
                        continue

                    # Calculate confidence based on match ratio
                    class_match_ratio = len(matched_classes) / len(classes)

                    # Check if tag matches (if specified)
                    tag_matches = False
                    line_start = content[: match.start()].count("\n")
                    line_content = lines[line_start]

                    if tag:
                        # Look for <tag in the same line or nearby
                        tag_pattern = rf"<{tag}[\s>]"
                        if re.search(tag_pattern, line_content):
                            tag_matches = True
                        # Also check a few lines before
                        for i in range(max(0, line_start - 3), line_start + 1):
                            if re.search(tag_pattern, lines[i]):
                                tag_matches = True
                                break

                    # Calculate confidence
                    confidence = 0.5 + (class_match_ratio * 0.3)
                    if tag_matches:
                        confidence += 0.15
                    if class_match_ratio == 1.0:
                        confidence += 0.05

                    confidence = min(confidence, 0.95)

                    # Build match reasons
                    reasons = [
                        f"className match ({len(matched_classes)}/{len(classes)} classes)"
                    ]
                    if tag_matches:
                        reasons.append(f"tag match ({tag})")

                    col = match.start() - content.rfind("\n", 0, match.start()) - 1

                    start_line = max(0, line_start - 2)
                    end_line = min(len(lines), line_start + 3)
                    context = lines[start_line:end_line]

                    candidates.append(
                        FileCandidate(
                            file_path=str(file_path),
                            line_number=line_start + 1,
                            column=col,
                            confidence=confidence,
                            match_reasons=reasons,
                            matched_text=match.group(0),
                            context_lines=context,
                        )
                    )
        except Exception:
            continue

    return candidates


def search_by_text(
    files: list[Path],
    text: str,
    tag: Optional[str] = None,
) -> list[FileCandidate]:
    """Search for element by text content."""
    candidates = []

    if not text or len(text) < 3:
        return candidates

    # Escape for regex but allow some flexibility
    escaped_text = re.escape(text)

    for file_path in files:
        try:
            content = file_path.read_text()
            lines = content.split("\n")

            # Look for text in JSX (between tags or in expressions)
            patterns = [
                rf">\s*{escaped_text}\s*<",  # >text<
                rf"[\"'`]{escaped_text}[\"'`]",  # "text" or 'text' or `text`
            ]

            for pattern in patterns:
                for match in re.finditer(pattern, content, re.IGNORECASE):
                    line_start = content[: match.start()].count("\n")
                    line_content = lines[line_start]

                    # Check if tag matches nearby
                    tag_matches = False
                    if tag:
                        tag_pattern = rf"<{tag}[\s>]"
                        for i in range(
                            max(0, line_start - 5), min(len(lines), line_start + 2)
                        ):
                            if re.search(tag_pattern, lines[i]):
                                tag_matches = True
                                break

                    # Base confidence for text match
                    confidence = 0.60
                    if tag_matches:
                        confidence += 0.20

                    reasons = ["text content match"]
                    if tag_matches:
                        reasons.append(f"tag match ({tag})")

                    col = match.start() - content.rfind("\n", 0, match.start()) - 1

                    start_line = max(0, line_start - 2)
                    end_line = min(len(lines), line_start + 3)
                    context = lines[start_line:end_line]

                    candidates.append(
                        FileCandidate(
                            file_path=str(file_path),
                            line_number=line_start + 1,
                            column=col,
                            confidence=confidence,
                            match_reasons=reasons,
                            matched_text=match.group(0),
                            context_lines=context,
                        )
                    )
        except Exception:
            continue

    return candidates


def deduplicate_candidates(candidates: list[FileCandidate]) -> list[FileCandidate]:
    """Remove duplicate candidates, keeping highest confidence."""
    seen = {}  # (file, line) -> candidate

    for c in candidates:
        key = (c.file_path, c.line_number)
        if key not in seen or c.confidence > seen[key].confidence:
            # Merge match reasons if updating
            if key in seen:
                existing_reasons = set(seen[key].match_reasons)
                new_reasons = set(c.match_reasons)
                c.match_reasons = list(existing_reasons | new_reasons)
                c.confidence = (
                    max(c.confidence, seen[key].confidence) + 0.05
                )  # Bonus for multiple matches
                c.confidence = min(c.confidence, 0.99)
            seen[key] = c

    return sorted(seen.values(), key=lambda x: -x.confidence)


def find_element_in_source(
    query: ElementQuery,
    root: Optional[Path] = None,
) -> list[FileCandidate]:
    """
    Find source file locations for an element.

    Returns candidates sorted by confidence (highest first).
    """
    if root is None:
        root = find_project_root()
    files = get_source_files(root)
    all_candidates = []

    # Strategy 1: ID (highest confidence)
    if query.element_id:
        candidates = search_by_id(files, query.element_id)
        all_candidates.extend(candidates)

    # Strategy 2: data-testid (high confidence)
    if query.data_testid:
        candidates = search_by_data_testid(files, query.data_testid)
        all_candidates.extend(candidates)

    # Strategy 3: className + tag (medium confidence)
    if query.class_name:
        classes = query.class_name.split()
        tag = query.tag or extract_tag_from_selector(query.selector)
        candidates = search_by_classname(files, tag, classes)
        all_candidates.extend(candidates)

    # Strategy 4: Text content (lower confidence, fallback)
    if query.text and not all_candidates:
        tag = query.tag or extract_tag_from_selector(query.selector)
        candidates = search_by_text(files, query.text, tag)
        all_candidates.extend(candidates)

    # Deduplicate and sort
    return deduplicate_candidates(all_candidates)


def candidate_to_dict(c: FileCandidate) -> dict:
    """Convert candidate to JSON-serializable dict."""
    return {
        "filePath": c.file_path,
        "lineNumber": c.line_number,
        "column": c.column,
        "confidence": round(c.confidence, 3),
        "matchReasons": c.match_reasons,
        "matchedText": c.matched_text,
        "contextLines": c.context_lines,
    }


if __name__ == "__main__":
    import json
    import sys

    # Test with command line args
    if len(sys.argv) < 2:
        print(
            "Usage: file_finder.py <selector> [--class <className>] [--tag <tag>] [--text <text>]",
            file=sys.stderr,
        )
        sys.exit(1)

    selector = sys.argv[1]
    class_name = None
    tag = None
    text = None

    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == "--class" and i + 1 < len(sys.argv):
            class_name = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--tag" and i + 1 < len(sys.argv):
            tag = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--text" and i + 1 < len(sys.argv):
            text = sys.argv[i + 1]
            i += 2
        else:
            i += 1

    # Extract tag from selector if not provided
    if not tag:
        tag = extract_tag_from_selector(selector)

    # Extract classes from selector if className not provided
    if not class_name:
        classes = extract_classes_from_selector(selector)
        if classes:
            class_name = " ".join(classes)

    query = ElementQuery(
        selector=selector,
        tag=tag or "",
        class_name=class_name,
        text=text,
    )

    candidates = find_element_in_source(query)

    print(json.dumps([candidate_to_dict(c) for c in candidates], indent=2))
