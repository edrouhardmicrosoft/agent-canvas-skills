#!/usr/bin/env python3
"""
Session Parser - Parse canvas session JSON and extract change manifest.

Reads session artifacts from .canvas/sessions/<sessionId>/ and extracts
a normalized change manifest suitable for file finding and diff generation.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class StyleChange:
    """A single style property change."""

    selector: str
    property: str
    old_value: Optional[str]
    new_value: str
    selector_confidence: str = "medium"
    selector_alternatives: list = field(default_factory=list)


@dataclass
class TextChange:
    """A text content change."""

    selector: str
    old_text: str
    new_text: str
    selector_confidence: str = "medium"
    selector_alternatives: list = field(default_factory=list)


@dataclass
class ElementInfo:
    """Information about a DOM element from session."""

    tag: str
    selector: str
    class_name: Optional[str]
    element_id: Optional[str]
    text: Optional[str]
    data_testid: Optional[str]
    selector_confidence: str
    selector_alternatives: list
    styles: dict = field(default_factory=dict)
    attributes: dict = field(default_factory=dict)


@dataclass
class ChangeManifest:
    """Complete manifest of changes from a session."""

    session_id: str
    url: str
    style_changes: list[StyleChange] = field(default_factory=list)
    text_changes: list[TextChange] = field(default_factory=list)
    elements: dict[str, ElementInfo] = field(default_factory=dict)  # selector -> info
    before_screenshot: Optional[str] = None


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


def find_session_dir(session_id: str, root: Optional[Path] = None) -> Optional[Path]:
    """Find session directory, handling various session ID formats."""
    if root is None:
        root = find_project_root()
    base = root / ".canvas/sessions"

    # Try exact match first
    exact = base / session_id
    if exact.exists():
        return exact

    # Try with ses- prefix if not present
    if not session_id.startswith("ses-"):
        prefixed = base / f"ses-{session_id}"
        if prefixed.exists():
            return prefixed

    # Try partial match
    if base.exists():
        for d in base.iterdir():
            if d.is_dir() and session_id in d.name:
                return d

    return None


def load_session(session_id: str) -> Optional[dict]:
    """Load session JSON from disk."""
    session_dir = find_session_dir(session_id)
    if not session_dir:
        return None

    session_file = session_dir / "session.json"
    if not session_file.exists():
        return None

    return json.loads(session_file.read_text())


def extract_element_info(
    element_data: dict, eyes_data: Optional[dict] = None
) -> ElementInfo:
    """Extract normalized element info from session data."""
    # Prefer eyes data if available (more detailed)
    data = eyes_data if eyes_data and eyes_data.get("ok") else element_data

    attributes = data.get("attributes", {})

    return ElementInfo(
        tag=data.get("tag", ""),
        selector=data.get("selector", ""),
        class_name=data.get("className"),
        element_id=data.get("id"),
        text=data.get("text") or data.get("textContent"),
        data_testid=attributes.get("dataTestid"),
        selector_confidence=data.get("selectorConfidence", "medium"),
        selector_alternatives=data.get("selectorAlternatives", []),
        styles=data.get("styles", {}),
        attributes=attributes,
    )


def parse_selector_classes(selector: str) -> list[str]:
    """Extract class names from a CSS selector."""
    # Handle escaped brackets in Tailwind classes like text-\[72px\]
    # Selector format: tag.class1.class2.class3
    classes = []

    # Remove tag prefix
    parts = selector.split(".")
    if parts:
        # First part might be the tag, skip it if it looks like a tag
        start = 0
        if (
            parts[0]
            and not parts[0].startswith("[")
            and re.match(r"^[a-z]+$", parts[0].split(":")[0].split("\\")[0])
        ):
            start = 1

        for part in parts[start:]:
            if part:
                # Unescape the class name
                class_name = part.replace("\\[", "[").replace("\\]", "]")
                classes.append(class_name)

    return classes


def extract_save_request_changes(
    save_request: dict,
) -> tuple[list[StyleChange], list[TextChange]]:
    """Extract style and text changes from a save_request event."""
    style_changes = []
    text_changes = []

    changes = save_request.get("changes") or save_request.get("payload", {}).get(
        "changes", {}
    )

    # Style changes
    for sc in changes.get("styles", []):
        style_changes.append(
            StyleChange(
                selector=sc.get("selector", ""),
                property=sc.get("property", ""),
                old_value=sc.get("oldValue"),
                new_value=sc.get("newValue", ""),
                selector_confidence=sc.get("selectorConfidence", "medium"),
                selector_alternatives=sc.get("selectorAlternatives", []),
            )
        )

    # Text changes
    for tc in changes.get("texts", []):
        text_changes.append(
            TextChange(
                selector=tc.get("selector", ""),
                old_text=tc.get("oldText", ""),
                new_text=tc.get("newText", ""),
                selector_confidence=tc.get("selectorConfidence", "medium"),
                selector_alternatives=tc.get("selectorAlternatives", []),
            )
        )

    return style_changes, text_changes


def synthesize_changes_from_edits(
    edits: list, selections: list
) -> tuple[list[StyleChange], list[TextChange]]:
    """
    Synthesize changes from edit events when no save_request exists.

    Compares initial selection state with final edit events to determine what changed.
    """
    style_changes = []
    text_changes = []

    # Group edits by selector
    edits_by_selector: dict[str, list] = {}
    for edit in edits:
        event_type = edit.get("type") or edit.get("event")
        if event_type and ("style" in event_type or "text" in event_type):
            selector = (
                edit.get("selector")
                or edit.get("payload", {}).get("selector")
                or edit.get("payload", {}).get("element", {}).get("selector")
            )
            if selector:
                edits_by_selector.setdefault(selector, []).append(edit)

    # Build element info from selections
    element_info: dict[str, ElementInfo] = {}
    for sel in selections:
        elem = sel.get("payload", {}).get("element", {})
        eyes = sel.get("eyes", {})
        selector = elem.get("selector")
        if selector:
            element_info[selector] = extract_element_info(elem, eyes)

    # Process edits for each selector
    for selector, edit_list in edits_by_selector.items():
        info = element_info.get(selector)
        original_styles = info.styles if info else {}
        original_text = info.text if info else ""

        for edit in edit_list:
            event_type = edit.get("type") or edit.get("event")

            if "style" in event_type:
                prop = edit.get("property") or edit.get("payload", {}).get("property")
                new_val = edit.get("newValue") or edit.get("payload", {}).get(
                    "newValue"
                )
                old_val = (
                    edit.get("oldValue")
                    or edit.get("payload", {}).get("oldValue")
                    or original_styles.get(prop)
                )

                if prop and new_val:
                    style_changes.append(
                        StyleChange(
                            selector=selector,
                            property=prop,
                            old_value=old_val,
                            new_value=new_val,
                            selector_confidence=info.selector_confidence
                            if info
                            else "medium",
                            selector_alternatives=info.selector_alternatives
                            if info
                            else [],
                        )
                    )

            elif "text" in event_type:
                new_text = edit.get("newText") or edit.get("payload", {}).get("newText")
                old_text = (
                    edit.get("oldText")
                    or edit.get("payload", {}).get("oldText")
                    or original_text
                )

                if new_text and new_text != old_text:
                    text_changes.append(
                        TextChange(
                            selector=selector,
                            old_text=old_text or "",
                            new_text=new_text,
                            selector_confidence=info.selector_confidence
                            if info
                            else "medium",
                            selector_alternatives=info.selector_alternatives
                            if info
                            else [],
                        )
                    )

    return style_changes, text_changes


def parse_session(session_id: str) -> Optional[ChangeManifest]:
    """
    Parse a session and return a change manifest.

    Looks for save_request events first, falls back to synthesizing from edits.
    """
    session = load_session(session_id)
    if not session:
        return None

    # Extract basic info
    manifest = ChangeManifest(
        session_id=session.get("sessionId", session_id),
        url=session.get("url", ""),
        before_screenshot=session.get("beforeScreenshot"),
    )

    # Get events
    events = session.get("events", {})
    selections = events.get("selections", [])
    edits = events.get("edits", [])

    # Build element info map from selections
    for sel in selections:
        elem = sel.get("payload", {}).get("element", {})
        eyes = sel.get("eyes", {})
        selector = elem.get("selector")
        if selector and selector not in manifest.elements:
            manifest.elements[selector] = extract_element_info(elem, eyes)

    # Look for save_request
    save_requests = [
        e
        for e in edits
        if e.get("type") == "save_request" or e.get("event") == "save_request"
    ]

    if save_requests:
        # Use the last save_request
        style_changes, text_changes = extract_save_request_changes(save_requests[-1])
        manifest.style_changes = style_changes
        manifest.text_changes = text_changes
    else:
        # Synthesize from edit events
        style_changes, text_changes = synthesize_changes_from_edits(edits, selections)
        manifest.style_changes = style_changes
        manifest.text_changes = text_changes

    return manifest


def manifest_to_dict(manifest: ChangeManifest) -> dict:
    """Convert manifest to JSON-serializable dict."""
    return {
        "sessionId": manifest.session_id,
        "url": manifest.url,
        "styleChanges": [
            {
                "selector": sc.selector,
                "property": sc.property,
                "oldValue": sc.old_value,
                "newValue": sc.new_value,
                "selectorConfidence": sc.selector_confidence,
                "selectorAlternatives": sc.selector_alternatives,
            }
            for sc in manifest.style_changes
        ],
        "textChanges": [
            {
                "selector": tc.selector,
                "oldText": tc.old_text,
                "newText": tc.new_text,
                "selectorConfidence": tc.selector_confidence,
                "selectorAlternatives": tc.selector_alternatives,
            }
            for tc in manifest.text_changes
        ],
        "elements": {
            selector: {
                "tag": info.tag,
                "selector": info.selector,
                "className": info.class_name,
                "id": info.element_id,
                "text": info.text,
                "dataTestid": info.data_testid,
                "selectorConfidence": info.selector_confidence,
                "selectorAlternatives": info.selector_alternatives,
            }
            for selector, info in manifest.elements.items()
        },
        "hasBeforeScreenshot": manifest.before_screenshot is not None,
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: session_parser.py <session_id>", file=sys.stderr)
        sys.exit(1)

    session_id = sys.argv[1]
    manifest = parse_session(session_id)

    if manifest:
        print(json.dumps(manifest_to_dict(manifest), indent=2))
    else:
        print(f"Session not found: {session_id}", file=sys.stderr)
        sys.exit(1)
