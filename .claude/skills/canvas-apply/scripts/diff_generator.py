#!/usr/bin/env python3
"""
Diff Generator - Generate unified diffs for canvas session changes.

Takes a ChangeManifest (from session_parser) and FileCandidate mappings (from file_finder)
to produce unified diffs for:
- Text changes: Replace string literals in JSX
- Style changes: Modify className attributes or add inline styles
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from session_parser import ChangeManifest, StyleChange, TextChange
from file_finder import (
    FileCandidate,
    ElementQuery,
    find_element_in_source,
    find_project_root,
)


@dataclass
class FileDiff:
    """A diff for a single file."""

    file_path: str
    original_content: str
    modified_content: str
    changes: list[str] = field(default_factory=list)  # Description of changes
    confidence: float = 0.0


@dataclass
class DiffResult:
    """Complete diff result for a session."""

    session_id: str
    file_diffs: list[FileDiff] = field(default_factory=list)
    unmapped_changes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def escape_for_regex(text: str) -> str:
    """Escape text for use in regex pattern."""
    return re.escape(text)


def find_text_in_jsx(
    content: str, text: str, tag: Optional[str] = None
) -> list[tuple[int, int]]:
    """
    Find occurrences of text in JSX content.

    Returns list of (start, end) positions.
    """
    matches = []
    escaped_text = escape_for_regex(text)

    # Pattern 1: Text between tags: >text<
    pattern1 = rf"(>)\s*({escaped_text})\s*(<)"
    for m in re.finditer(pattern1, content):
        matches.append((m.start(2), m.end(2)))

    # Pattern 2: Text in JSX expressions or string literals
    # Match "text", 'text', or `text`
    for quote in ['"', "'", "`"]:
        pattern = rf"({re.escape(quote)})({escaped_text})({re.escape(quote)})"
        for m in re.finditer(pattern, content):
            matches.append((m.start(2), m.end(2)))

    return matches


def find_classname_for_element(
    content: str,
    line_number: int,
    class_name: str,
) -> Optional[tuple[int, int, str]]:
    """
    Find the className attribute for an element near a line.

    Returns (start, end, full_match) or None.
    """
    lines = content.split("\n")

    # Search within a window around the target line
    start_line = max(0, line_number - 5)
    end_line = min(len(lines), line_number + 5)

    # Calculate character offset for start_line
    char_offset = sum(len(lines[i]) + 1 for i in range(start_line))
    search_region = "\n".join(lines[start_line:end_line])

    # Patterns for className
    patterns = [
        r'className\s*=\s*"([^"]*)"',
        r"className\s*=\s*'([^']*)'",
        r"className\s*=\s*\{[`'\"]([^`'\"]*)[`'\"]\}",
        r'class\s*=\s*"([^"]*)"',
        r"class\s*=\s*'([^']*)'",
    ]

    for pattern in patterns:
        for m in re.finditer(pattern, search_region):
            found_classes = set(m.group(1).split())
            target_classes = set(class_name.split())

            # Check if this className contains our target classes
            if target_classes & found_classes:  # Intersection
                global_start = char_offset + m.start()
                global_end = char_offset + m.end()
                return (global_start, global_end, m.group(0))

    return None


def generate_text_diff(
    content: str,
    change: TextChange,
    candidate: FileCandidate,
) -> Optional[str]:
    """
    Generate modified content for a text change.

    Returns modified content or None if change couldn't be applied.
    """
    # Find the old text in the content
    matches = find_text_in_jsx(content, change.old_text)

    if not matches:
        return None

    # If multiple matches, prefer one near the candidate line
    lines = content.split("\n")
    target_char = sum(len(lines[i]) + 1 for i in range(candidate.line_number - 1))

    # Sort by proximity to target line
    matches.sort(key=lambda m: abs(m[0] - target_char))

    # Apply the change to the closest match
    start, end = matches[0]
    return content[:start] + change.new_text + content[end:]


def css_property_to_style_attr(prop: str) -> str:
    """Convert CSS property name to React style attribute name."""
    # Handle common conversions
    conversions = {
        "background-color": "backgroundColor",
        "font-size": "fontSize",
        "font-weight": "fontWeight",
        "border-radius": "borderRadius",
        "padding": "padding",
        "margin": "margin",
        "color": "color",
        "width": "width",
        "height": "height",
    }

    if prop in conversions:
        return conversions[prop]

    # Generic kebab-case to camelCase
    parts = prop.split("-")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def generate_style_diff_classname(
    content: str,
    change: StyleChange,
    candidate: FileCandidate,
) -> Optional[str]:
    """
    Generate modified content for a style change by modifying className.

    This is a simple approach that adds inline styles if className modification
    isn't straightforward.
    """
    # For now, we'll add inline styles since Tailwind class generation is Phase 5
    # Find the element's opening tag

    lines = content.split("\n")
    line_idx = candidate.line_number - 1

    if line_idx < 0 or line_idx >= len(lines):
        return None

    line = lines[line_idx]

    # Find the element opening in this line
    # Look for <tag or <Tag pattern
    tag_match = re.search(r"<([A-Za-z][A-Za-z0-9]*)", line)
    if not tag_match:
        # Try previous lines
        for i in range(line_idx - 1, max(0, line_idx - 5), -1):
            tag_match = re.search(r"<([A-Za-z][A-Za-z0-9]*)", lines[i])
            if tag_match:
                line_idx = i
                line = lines[line_idx]
                break

    if not tag_match:
        return None

    # Check if element already has style attribute
    style_attr_match = re.search(r"style\s*=\s*\{\{([^}]*)\}\}", line)

    style_name = css_property_to_style_attr(change.property)
    style_value = change.new_value

    # Quote string values
    if not style_value.replace(".", "").replace("-", "").isdigit():
        style_value = f'"{style_value}"'

    if style_attr_match:
        # Add to existing style
        existing_styles = style_attr_match.group(1).strip()
        if existing_styles and not existing_styles.endswith(","):
            existing_styles += ","
        new_styles = f"{existing_styles} {style_name}: {style_value}"
        new_line = (
            line[: style_attr_match.start()]
            + f"style={{{{ {new_styles} }}}}"
            + line[style_attr_match.end() :]
        )
    else:
        # Find where to insert style attribute (before > or before className ends)
        # Insert before the closing > of the opening tag
        close_match = re.search(r"(\s*)/?>", line)
        if close_match:
            insert_pos = close_match.start()
            new_line = (
                line[:insert_pos]
                + f" style={{{{ {style_name}: {style_value} }}}}"
                + line[insert_pos:]
            )
        else:
            # Can't find good insertion point
            return None

    lines[line_idx] = new_line
    return "\n".join(lines)


def generate_diffs(manifest: ChangeManifest, root: Optional[Path] = None) -> DiffResult:
    """
    Generate diffs for all changes in a manifest.

    Returns a DiffResult with file diffs and any unmapped changes.
    """
    if root is None:
        root = find_project_root()

    result = DiffResult(session_id=manifest.session_id)

    # Group changes by their target files
    file_changes: dict[str, tuple[str, list]] = {}  # file_path -> (content, changes)

    # Process text changes
    for tc in manifest.text_changes:
        # Get element info if available
        elem_info = manifest.elements.get(tc.selector)

        # Build query
        query = ElementQuery(
            selector=tc.selector,
            tag=elem_info.tag if elem_info else "",
            class_name=elem_info.class_name if elem_info else None,
            element_id=elem_info.element_id if elem_info else None,
            text=tc.old_text,
            data_testid=elem_info.data_testid if elem_info else None,
            selector_confidence=tc.selector_confidence,
        )

        # Find candidates
        candidates = find_element_in_source(query, root)

        if not candidates:
            result.unmapped_changes.append(
                f"Text change unmapped: '{tc.old_text}' -> '{tc.new_text}' (selector: {tc.selector})"
            )
            continue

        # Use best candidate
        best = candidates[0]
        file_path = best.file_path

        # Load or get content
        if file_path not in file_changes:
            try:
                content = Path(file_path).read_text()
                file_changes[file_path] = (content, [])
            except Exception as e:
                result.warnings.append(f"Could not read {file_path}: {e}")
                continue

        original, changes = file_changes[file_path]

        # Apply text change
        modified = generate_text_diff(original, tc, best)
        if modified:
            file_changes[file_path] = (
                modified,
                changes
                + [
                    f"Text: '{tc.old_text}' -> '{tc.new_text}' (confidence: {best.confidence:.2f})"
                ],
            )
        else:
            result.warnings.append(
                f"Could not apply text change: '{tc.old_text}' -> '{tc.new_text}' in {file_path}"
            )

    # Process style changes
    for sc in manifest.style_changes:
        elem_info = manifest.elements.get(sc.selector)

        query = ElementQuery(
            selector=sc.selector,
            tag=elem_info.tag if elem_info else "",
            class_name=elem_info.class_name if elem_info else None,
            element_id=elem_info.element_id if elem_info else None,
            data_testid=elem_info.data_testid if elem_info else None,
            selector_confidence=sc.selector_confidence,
        )

        candidates = find_element_in_source(query, root)

        if not candidates:
            result.unmapped_changes.append(
                f"Style change unmapped: {sc.property}: {sc.new_value} (selector: {sc.selector})"
            )
            continue

        best = candidates[0]
        file_path = best.file_path

        if file_path not in file_changes:
            try:
                content = Path(file_path).read_text()
                file_changes[file_path] = (content, [])
            except Exception as e:
                result.warnings.append(f"Could not read {file_path}: {e}")
                continue

        current_content, changes = file_changes[file_path]

        # Apply style change
        modified = generate_style_diff_classname(current_content, sc, best)
        if modified:
            file_changes[file_path] = (
                modified,
                changes
                + [
                    f"Style: {sc.property}: {sc.old_value or '(none)'} -> {sc.new_value} (confidence: {best.confidence:.2f})"
                ],
            )
        else:
            result.warnings.append(
                f"Could not apply style change: {sc.property}: {sc.new_value} in {file_path}"
            )

    # Build FileDiff objects
    for file_path, (modified_content, changes) in file_changes.items():
        try:
            original = Path(file_path).read_text()
            if original != modified_content:
                # Calculate average confidence from changes
                confidences = []
                for c in changes:
                    if "confidence:" in c:
                        conf_str = c.split("confidence:")[1].strip().rstrip(")")
                        try:
                            confidences.append(float(conf_str))
                        except ValueError:
                            pass

                avg_confidence = (
                    sum(confidences) / len(confidences) if confidences else 0.5
                )

                result.file_diffs.append(
                    FileDiff(
                        file_path=file_path,
                        original_content=original,
                        modified_content=modified_content,
                        changes=changes,
                        confidence=avg_confidence,
                    )
                )
        except Exception as e:
            result.warnings.append(f"Error processing {file_path}: {e}")

    return result


def format_unified_diff(diff: FileDiff, context_lines: int = 3) -> str:
    """Format a FileDiff as unified diff output."""
    import difflib

    original_lines = diff.original_content.splitlines(keepends=True)
    modified_lines = diff.modified_content.splitlines(keepends=True)

    # Ensure lines end with newline for proper diff formatting
    if original_lines and not original_lines[-1].endswith("\n"):
        original_lines[-1] += "\n"
    if modified_lines and not modified_lines[-1].endswith("\n"):
        modified_lines[-1] += "\n"

    diff_lines = difflib.unified_diff(
        original_lines,
        modified_lines,
        fromfile=f"a/{diff.file_path}",
        tofile=f"b/{diff.file_path}",
        n=context_lines,
    )

    return "".join(diff_lines)


def result_to_dict(result: DiffResult) -> dict:
    """Convert DiffResult to JSON-serializable dict."""
    return {
        "sessionId": result.session_id,
        "fileDiffs": [
            {
                "filePath": d.file_path,
                "changes": d.changes,
                "confidence": round(d.confidence, 3),
                "unifiedDiff": format_unified_diff(d),
            }
            for d in result.file_diffs
        ],
        "unmappedChanges": result.unmapped_changes,
        "warnings": result.warnings,
        "summary": {
            "filesModified": len(result.file_diffs),
            "unmappedCount": len(result.unmapped_changes),
            "warningCount": len(result.warnings),
        },
    }


if __name__ == "__main__":
    import json
    import sys
    from session_parser import parse_session

    if len(sys.argv) < 2:
        print("Usage: diff_generator.py <session_id>", file=sys.stderr)
        sys.exit(1)

    session_id = sys.argv[1]
    manifest = parse_session(session_id)

    if not manifest:
        print(f"Session not found: {session_id}", file=sys.stderr)
        sys.exit(1)

    result = generate_diffs(manifest)

    # Output as JSON
    print(json.dumps(result_to_dict(result), indent=2))
