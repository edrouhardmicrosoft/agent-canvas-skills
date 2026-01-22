#!/usr/bin/env python3
"""
Diff Generator - Generate unified diffs for canvas session changes.

Takes a ChangeManifest (from session_parser) and FileCandidate mappings (from file_finder)
to produce unified diffs for:
- Text changes: Replace string literals in JSX
- Style changes: Modify className attributes or add inline styles

Phase 5 enhancements:
- Tailwind class detection and suggestion
- Design token inference
- Component boundary awareness
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

# Phase 5 imports - gracefully handle if not present
try:
    from tailwind_detector import detect_tailwind, TailwindConfig
    from tailwind_mapper import css_to_tailwind, TailwindSuggestion

    TAILWIND_AVAILABLE = True
except ImportError:
    TAILWIND_AVAILABLE = False
    TailwindConfig = None
    TailwindSuggestion = None

try:
    from design_tokens import extract_tokens, suggest_token_for_value, DesignTokens

    TOKENS_AVAILABLE = True
except ImportError:
    TOKENS_AVAILABLE = False
    DesignTokens = None


@dataclass
class FileDiff:
    """A diff for a single file."""

    file_path: str
    original_content: str
    modified_content: str
    changes: list[str] = field(default_factory=list)  # Description of changes
    confidence: float = 0.0
    tailwind_suggestions: list[str] = field(
        default_factory=list
    )  # Phase 5: Tailwind suggestions
    token_suggestions: list[str] = field(
        default_factory=list
    )  # Phase 5: Design token suggestions


@dataclass
class DiffResult:
    """Complete diff result for a session."""

    session_id: str
    file_diffs: list[FileDiff] = field(default_factory=list)
    unmapped_changes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    # Phase 5 metadata
    tailwind_detected: bool = False
    tailwind_version: Optional[str] = None
    design_tokens_found: int = 0


@dataclass
class StyleSuggestion:
    """Suggestion for how to apply a style change."""

    method: str  # "tailwind", "token", "inline"
    value: str  # The actual value to use (class name, var(), or style value)
    confidence: float
    description: str


def escape_for_regex(text: str) -> str:
    """Escape text for use in regex pattern."""
    return re.escape(text)


def get_style_suggestion(
    css_property: str,
    css_value: str,
    tailwind_config: Optional["TailwindConfig"] = None,
    design_tokens: Optional["DesignTokens"] = None,
    prefer_tailwind: bool = True,
    prefer_tokens: bool = True,
) -> StyleSuggestion:
    """
    Get the best suggestion for applying a style change.

    Priority:
    1. Tailwind class (if detected and exact match)
    2. Design token (if found with matching value)
    3. Tailwind arbitrary value (if Tailwind detected)
    4. Inline style (fallback)
    """
    # Try Tailwind first
    if (
        prefer_tailwind
        and TAILWIND_AVAILABLE
        and tailwind_config
        and tailwind_config.detected
    ):
        suggestion = css_to_tailwind(
            css_property,
            css_value,
            custom_colors=tailwind_config.custom_colors,
        )
        if suggestion:
            if suggestion.is_exact_match:
                return StyleSuggestion(
                    method="tailwind",
                    value=suggestion.tailwind_class,
                    confidence=suggestion.confidence,
                    description=f"Tailwind class: {suggestion.tailwind_class}",
                )
            # Keep as fallback
            tailwind_fallback = StyleSuggestion(
                method="tailwind-arbitrary",
                value=suggestion.fallback_arbitrary,
                confidence=0.7,
                description=f"Tailwind arbitrary: {suggestion.fallback_arbitrary}",
            )
        else:
            tailwind_fallback = None
    else:
        tailwind_fallback = None

    # Try design tokens
    if prefer_tokens and TOKENS_AVAILABLE and design_tokens:
        token_result = suggest_token_for_value(design_tokens, css_property, css_value)
        if token_result:
            token, css_usage = token_result
            return StyleSuggestion(
                method="token",
                value=css_usage,
                confidence=1.0,
                description=f"Design token: {token.variable} ({token.value})",
            )

    # Use Tailwind fallback if available
    if tailwind_fallback:
        return tailwind_fallback

    # Inline style fallback
    return StyleSuggestion(
        method="inline",
        value=css_value,
        confidence=0.5,
        description=f"Inline style: {css_property}: {css_value}",
    )


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
    tailwind_config: Optional["TailwindConfig"] = None,
    design_tokens: Optional["DesignTokens"] = None,
) -> tuple[Optional[str], Optional[StyleSuggestion]]:
    """
    Generate modified content for a style change.

    Phase 5: Uses Tailwind classes or design tokens when available.
    Falls back to inline styles if neither is available.

    Returns:
        tuple of (modified_content, suggestion_used) or (None, None) if failed
    """
    lines = content.split("\n")
    line_idx = candidate.line_number - 1

    if line_idx < 0 or line_idx >= len(lines):
        return None, None

    line = lines[line_idx]

    # Find the element opening in this line
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
        return None, None

    # Get style suggestion (Phase 5: Tailwind/tokens priority)
    suggestion = get_style_suggestion(
        change.property,
        change.new_value,
        tailwind_config=tailwind_config,
        design_tokens=design_tokens,
    )

    if suggestion.method == "tailwind":
        # Add/modify className with Tailwind class
        new_line = _add_tailwind_class(line, suggestion.value)
        if new_line:
            lines[line_idx] = new_line
            return "\n".join(lines), suggestion

    elif suggestion.method == "tailwind-arbitrary":
        # Add Tailwind arbitrary value class
        new_line = _add_tailwind_class(line, suggestion.value)
        if new_line:
            lines[line_idx] = new_line
            return "\n".join(lines), suggestion

    elif suggestion.method == "token":
        # Use design token via CSS var() in inline style
        style_name = css_property_to_style_attr(change.property)
        style_value = f'"{suggestion.value}"'
        new_line = _add_inline_style(line, style_name, style_value)
        if new_line:
            lines[line_idx] = new_line
            return "\n".join(lines), suggestion

    # Fallback: inline style with raw value
    style_name = css_property_to_style_attr(change.property)
    style_value = change.new_value
    if not style_value.replace(".", "").replace("-", "").isdigit():
        style_value = f'"{style_value}"'

    new_line = _add_inline_style(line, style_name, style_value)
    if new_line:
        lines[line_idx] = new_line
        return "\n".join(lines), suggestion

    return None, None


def _add_tailwind_class(line: str, new_class: str) -> Optional[str]:
    """Add a Tailwind class to an element's className attribute."""
    # Pattern for className="..." or className='...'
    classname_match = re.search(r'className\s*=\s*"([^"]*)"', line)
    if classname_match:
        existing = classname_match.group(1)
        # Remove conflicting classes (same prefix)
        # e.g., if adding text-red-500, remove existing text-* color classes
        prefix = new_class.split("-")[0] if "-" in new_class else new_class
        existing_classes = existing.split()
        # Simple conflict resolution: remove classes with same prefix for colors
        if prefix in ["text", "bg", "border"] and "-" in new_class:
            # More aggressive: remove classes that look like color utilities
            existing_classes = [
                c
                for c in existing_classes
                if not (c.startswith(f"{prefix}-") and _looks_like_color_class(c))
            ]
        new_classes = " ".join(existing_classes + [new_class])
        return (
            line[: classname_match.start()]
            + f'className="{new_classes}"'
            + line[classname_match.end() :]
        )

    # Pattern for className={'...'} or className={`...`}
    classname_template = re.search(r"className\s*=\s*\{[`'\"]([^`'\"]*)[`'\"]\}", line)
    if classname_template:
        existing = classname_template.group(1)
        new_classes = f"{existing} {new_class}".strip()
        return (
            line[: classname_template.start()]
            + f'className="{new_classes}"'
            + line[classname_template.end() :]
        )

    # No className found, insert before closing >
    close_match = re.search(r"(\s*)/?>", line)
    if close_match:
        insert_pos = close_match.start()
        return line[:insert_pos] + f' className="{new_class}"' + line[insert_pos:]

    return None


def _looks_like_color_class(class_name: str) -> bool:
    """Check if a class name looks like a Tailwind color utility."""
    color_keywords = [
        "red",
        "blue",
        "green",
        "yellow",
        "orange",
        "purple",
        "pink",
        "gray",
        "grey",
        "black",
        "white",
        "slate",
        "zinc",
        "neutral",
        "stone",
        "amber",
        "lime",
        "emerald",
        "teal",
        "cyan",
        "sky",
        "indigo",
        "violet",
        "fuchsia",
        "rose",
        "transparent",
        "current",
    ]
    parts = class_name.lower().split("-")
    return any(color in parts for color in color_keywords)


def _add_inline_style(line: str, style_name: str, style_value: str) -> Optional[str]:
    """Add an inline style to an element."""
    # Check if element already has style attribute
    style_attr_match = re.search(r"style\s*=\s*\{\{([^}]*)\}\}", line)

    if style_attr_match:
        # Add to existing style
        existing_styles = style_attr_match.group(1).strip()
        if existing_styles and not existing_styles.endswith(","):
            existing_styles += ","
        new_styles = f"{existing_styles} {style_name}: {style_value}"
        return (
            line[: style_attr_match.start()]
            + f"style={{{{ {new_styles} }}}}"
            + line[style_attr_match.end() :]
        )
    else:
        # Insert before the closing > of the opening tag
        close_match = re.search(r"(\s*)/?>", line)
        if close_match:
            insert_pos = close_match.start()
            return (
                line[:insert_pos]
                + f" style={{{{ {style_name}: {style_value} }}}}"
                + line[insert_pos:]
            )

    return None


def generate_diffs(
    manifest: ChangeManifest,
    root: Optional[Path] = None,
    prefer_tailwind: bool = True,
    prefer_tokens: bool = True,
) -> DiffResult:
    """
    Generate diffs for all changes in a manifest.

    Phase 5 enhancements:
    - Detects Tailwind CSS and uses utility classes when available
    - Detects design tokens and suggests them over hardcoded values
    - Falls back to inline styles if neither is available

    Args:
        manifest: The change manifest from session parser
        root: Project root path (auto-detected if not provided)
        prefer_tailwind: Use Tailwind classes when project supports them
        prefer_tokens: Use design tokens when available

    Returns a DiffResult with file diffs and any unmapped changes.
    """
    if root is None:
        root = find_project_root()

    result = DiffResult(session_id=manifest.session_id)

    # Phase 5: Detect Tailwind configuration
    tailwind_config = None
    if prefer_tailwind and TAILWIND_AVAILABLE:
        try:
            tailwind_config = detect_tailwind(root)
            if tailwind_config and tailwind_config.detected:
                result.tailwind_detected = True
                result.tailwind_version = tailwind_config.version
        except Exception as e:
            result.warnings.append(f"Tailwind detection failed: {e}")

    # Phase 5: Extract design tokens
    design_tokens = None
    if prefer_tokens and TOKENS_AVAILABLE:
        try:
            design_tokens = extract_tokens(root)
            if design_tokens:
                result.design_tokens_found = len(design_tokens.tokens)
        except Exception as e:
            result.warnings.append(f"Design token extraction failed: {e}")

    # Group changes by their target files
    # file_path -> (content, changes, tailwind_suggestions, token_suggestions)
    file_changes: dict[str, tuple[str, list, list, list]] = {}

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
                file_changes[file_path] = (content, [], [], [])
            except Exception as e:
                result.warnings.append(f"Could not read {file_path}: {e}")
                continue

        original, changes, tw_sugg, tok_sugg = file_changes[file_path]

        # Apply text change
        modified = generate_text_diff(original, tc, best)
        if modified:
            file_changes[file_path] = (
                modified,
                changes
                + [
                    f"Text: '{tc.old_text}' -> '{tc.new_text}' (confidence: {best.confidence:.2f})"
                ],
                tw_sugg,
                tok_sugg,
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
                file_changes[file_path] = (content, [], [], [])
            except Exception as e:
                result.warnings.append(f"Could not read {file_path}: {e}")
                continue

        current_content, changes, tw_sugg, tok_sugg = file_changes[file_path]

        # Apply style change (Phase 5: pass Tailwind/token context)
        modified, suggestion = generate_style_diff_classname(
            current_content,
            sc,
            best,
            tailwind_config=tailwind_config,
            design_tokens=design_tokens,
        )
        if modified:
            change_desc = f"Style: {sc.property}: {sc.old_value or '(none)'} -> {sc.new_value} (confidence: {best.confidence:.2f})"

            # Track suggestions used
            new_tw_sugg = tw_sugg.copy()
            new_tok_sugg = tok_sugg.copy()
            if suggestion:
                if suggestion.method in ("tailwind", "tailwind-arbitrary"):
                    new_tw_sugg.append(suggestion.description)
                elif suggestion.method == "token":
                    new_tok_sugg.append(suggestion.description)
                change_desc += f" [{suggestion.method}: {suggestion.value}]"

            file_changes[file_path] = (
                modified,
                changes + [change_desc],
                new_tw_sugg,
                new_tok_sugg,
            )
        else:
            result.warnings.append(
                f"Could not apply style change: {sc.property}: {sc.new_value} in {file_path}"
            )

    # Build FileDiff objects
    for file_path, (
        modified_content,
        changes,
        tw_sugg,
        tok_sugg,
    ) in file_changes.items():
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
                        tailwind_suggestions=tw_sugg,
                        token_suggestions=tok_sugg,
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
                "tailwindSuggestions": d.tailwind_suggestions,
                "tokenSuggestions": d.token_suggestions,
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
        # Phase 5 metadata
        "tailwindDetected": result.tailwind_detected,
        "tailwindVersion": result.tailwind_version,
        "designTokensFound": result.design_tokens_found,
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
