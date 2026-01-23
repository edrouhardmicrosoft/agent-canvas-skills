#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pillow",
# ]
# ///
"""
Annotator - Draw redlines and markers on screenshots.

Takes a screenshot and a list of issues with bounding box information,
draws numbered circles at issue locations with severity-based colors,
borders around problematic elements, and adds a legend.

Library Usage:
    from annotator import annotate_screenshot

    result = annotate_screenshot(
        screenshot_path="screenshot.png",
        issues=[
            {
                "id": 1,
                "severity": "blocking",
                "description": "Missing AI disclaimer",
                "boundingBox": {"x": 100, "y": 200, "width": 300, "height": 50}
            }
        ],
        output_path="annotated.png"
    )

CLI Usage:
    uv run annotator.py screenshot.png issues.json --output annotated.png
"""

import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from PIL import Image, ImageDraw, ImageFont


# =============================================================================
# Constants
# =============================================================================

# Severity colors (RGBA)
SEVERITY_COLORS = {
    "blocking": (220, 53, 69, 255),  # Red
    "major": (255, 145, 0, 255),  # Orange
    "minor": (255, 193, 7, 255),  # Yellow
}

# Circled numbers for markers (Unicode)
CIRCLED_NUMBERS = [
    "①",
    "②",
    "③",
    "④",
    "⑤",
    "⑥",
    "⑦",
    "⑧",
    "⑨",
    "⑩",
    "⑪",
    "⑫",
    "⑬",
    "⑭",
    "⑮",
    "⑯",
    "⑰",
    "⑱",
    "⑲",
    "⑳",
]

# Drawing settings
BORDER_WIDTH = 3
MARKER_RADIUS = 16
LEGEND_PADDING = 20
LEGEND_LINE_HEIGHT = 28
LEGEND_MAX_WIDTH = 400
LEGEND_FONT_SIZE = 14
MARKER_FONT_SIZE = 18


# =============================================================================
# CSS Selector Helpers
# =============================================================================


def _is_utility_class(class_name: str) -> bool:
    """Check if class is a utility/framework class to skip."""
    utility_patterns = [
        "flex",
        "grid",
        "p-",
        "m-",
        "text-",
        "bg-",
        "w-",
        "h-",  # Tailwind
        "col-",
        "row-",
        "d-",  # Bootstrap
        "css-",  # Emotion/styled-components
    ]
    return any(class_name.startswith(p) for p in utility_patterns)


def _build_parent_selector(parent: dict) -> str:
    """Build selector for a parent element."""
    if parent.get("id"):
        return f"#{parent['id']}"

    tag = parent.get("tag", "div")
    classes = parent.get("classes", [])

    if classes:
        main_class = next((c for c in classes if not _is_utility_class(c)), None)
        if main_class:
            return f"{tag}.{main_class}"

    return tag


def _generate_css_selector(element_info: dict) -> str:
    """
    Generate a unique CSS selector for an element.

    Prioritizes:
    1. ID selector (if unique): #my-id
    2. Class chain: .parent > .child.specific
    3. Tag + attributes: button[aria-label="Close"]
    4. Nth-child fallback: div > p:nth-child(2)
    """
    # If element has a unique ID, use it
    if element_info.get("id"):
        return f"#{element_info['id']}"

    # Build selector from tag and classes
    parts = []
    tag = element_info.get("tag", "div")
    classes = element_info.get("classes", [])

    if classes:
        # Use most specific classes (filter out utility classes)
        specific_classes = [c for c in classes if not _is_utility_class(c)]
        if specific_classes:
            selector = f"{tag}.{'.'.join(specific_classes[:2])}"
        else:
            selector = tag
    else:
        selector = tag

    # Add parent context for uniqueness
    parent_chain = element_info.get("parent_chain", [])
    for parent in reversed(parent_chain[:3]):  # Max 3 parents
        parent_selector = _build_parent_selector(parent)
        if parent_selector:
            parts.append(parent_selector)

    parts.append(selector)
    return " > ".join(parts)


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class BoundingBox:
    """Bounding box for an element."""

    x: int
    y: int
    width: int
    height: int

    @classmethod
    def from_dict(cls, d: dict) -> "BoundingBox":
        return cls(
            x=int(d.get("x", 0)),
            y=int(d.get("y", 0)),
            width=int(d.get("width", 0)),
            height=int(d.get("height", 0)),
        )

    @property
    def center(self) -> tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)

    @property
    def top_right(self) -> tuple[int, int]:
        return (self.x + self.width, self.y)


@dataclass
class Issue:
    """An issue to annotate on the screenshot."""

    id: int
    severity: str
    description: str
    bounding_box: Optional[BoundingBox] = None
    check_id: str = ""
    pillar: str = ""
    element: str = ""
    css_selector: str = ""
    element_info: Optional[dict] = None

    @classmethod
    def from_dict(cls, d: dict) -> "Issue":
        bbox = None
        if "boundingBox" in d and d["boundingBox"]:
            bbox = BoundingBox.from_dict(d["boundingBox"])

        # Get element info and generate selector if available
        element_info = d.get("elementInfo")
        css_selector = d.get("cssSelector", "")

        # If elementInfo provided but no cssSelector, generate it
        if element_info and not css_selector:
            css_selector = _generate_css_selector(element_info)

        return cls(
            id=d.get("id", 0),
            severity=d.get("severity", "minor"),
            description=d.get("description", ""),
            bounding_box=bbox,
            check_id=d.get("checkId", ""),
            pillar=d.get("pillar", ""),
            element=d.get("element", ""),
            css_selector=css_selector,
            element_info=element_info,
        )


# =============================================================================
# Font Handling
# =============================================================================


def get_font(
    size: int, bold: bool = False
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Get a font, falling back to default if custom fonts unavailable."""
    # Try common system fonts
    font_paths = [
        # macOS
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNSText.ttf",
        "/Library/Fonts/Arial.ttf",
        # Linux
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        # Windows
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
    ]

    if bold:
        font_paths = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/segoeuib.ttf",
        ] + font_paths

    for path in font_paths:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue

    # Fall back to default
    return ImageFont.load_default()


def get_circled_number(n: int) -> str:
    """Get circled number character, falling back to (N) for large numbers."""
    if 1 <= n <= len(CIRCLED_NUMBERS):
        return CIRCLED_NUMBERS[n - 1]
    return f"({n})"


# =============================================================================
# Drawing Functions
# =============================================================================


def draw_border(
    draw: ImageDraw.ImageDraw,
    bbox: BoundingBox,
    color: tuple[int, int, int, int],
    width: int = BORDER_WIDTH,
) -> None:
    """Draw a border around a bounding box."""
    # Draw rectangle with rounded corners effect
    x1, y1 = bbox.x, bbox.y
    x2, y2 = bbox.x + bbox.width, bbox.y + bbox.height

    # Draw multiple rectangles for thicker border
    for i in range(width):
        draw.rectangle(
            [x1 - i, y1 - i, x2 + i, y2 + i],
            outline=color,
            width=1,
        )


def draw_marker(
    draw: ImageDraw.ImageDraw,
    position: tuple[int, int],
    number: int,
    color: tuple[int, int, int, int],
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> None:
    """Draw a numbered circle marker at a position."""
    x, y = position
    radius = MARKER_RADIUS

    # Draw filled circle with white border
    draw.ellipse(
        [x - radius, y - radius, x + radius, y + radius],
        fill=color,
        outline=(255, 255, 255, 255),
        width=2,
    )

    # Draw number centered in circle
    text = get_circled_number(number)
    # For circled numbers, just draw the number itself
    if number <= len(CIRCLED_NUMBERS):
        text = str(number)

    # Get text bounding box for centering
    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]

    text_x = x - text_width // 2
    text_y = y - text_height // 2 - 2  # Slight adjustment for visual centering

    draw.text((text_x, text_y), text, fill=(255, 255, 255, 255), font=font)


def draw_legend(
    image: Image.Image,
    issues: list[Issue],
    padding: int = LEGEND_PADDING,
) -> Image.Image:
    """Draw a legend at the bottom of the image listing all issues."""
    if not issues:
        return image

    # Calculate legend dimensions
    font = get_font(LEGEND_FONT_SIZE)
    bold_font = get_font(LEGEND_FONT_SIZE, bold=True)
    small_font = get_font(LEGEND_FONT_SIZE - 2)  # Smaller font for selectors

    # Count issues with selectors to calculate height
    issues_with_selectors = sum(1 for i in issues if i.css_selector)

    # Calculate required height - 2 lines per issue with selector, 1 line otherwise
    legend_height = padding * 2  # Top and bottom padding
    legend_height += LEGEND_LINE_HEIGHT  # Header line
    legend_height += len(issues) * LEGEND_LINE_HEIGHT  # Main issue lines
    legend_height += issues_with_selectors * (
        LEGEND_LINE_HEIGHT - 8
    )  # Selector lines (smaller)

    # Create new image with space for legend
    new_width = image.width
    new_height = image.height + legend_height

    new_image = Image.new("RGBA", (new_width, new_height), (255, 255, 255, 255))
    new_image.paste(image, (0, 0))

    draw = ImageDraw.Draw(new_image)

    # Draw legend background
    legend_y = image.height
    draw.rectangle(
        [0, legend_y, new_width, new_height],
        fill=(248, 249, 250, 255),  # Light gray
    )

    # Draw separator line
    draw.line(
        [(0, legend_y), (new_width, legend_y)],
        fill=(200, 200, 200, 255),
        width=2,
    )

    # Draw header
    y = legend_y + padding
    draw.text(
        (padding, y),
        "Issues Found:",
        fill=(33, 37, 41, 255),
        font=bold_font,
    )
    y += LEGEND_LINE_HEIGHT

    # Draw each issue
    for issue in issues:
        color = SEVERITY_COLORS.get(issue.severity, SEVERITY_COLORS["minor"])

        # Draw severity indicator (small circle)
        indicator_x = padding + 8
        indicator_y = y + LEGEND_LINE_HEIGHT // 2
        draw.ellipse(
            [indicator_x - 6, indicator_y - 6, indicator_x + 6, indicator_y + 6],
            fill=color,
        )

        # Draw issue number and description
        text = f"#{issue.id}: {issue.description}"
        if len(text) > 60:
            text = text[:57] + "..."

        draw.text(
            (padding + 24, y + 4),
            text,
            fill=(33, 37, 41, 255),
            font=font,
        )

        y += LEGEND_LINE_HEIGHT

        # Draw CSS selector on second line if present
        if issue.css_selector:
            selector_text = f"→ {issue.css_selector}"
            # Truncate long selectors
            max_selector_len = 55
            if len(selector_text) > max_selector_len:
                selector_text = selector_text[: max_selector_len - 3] + "..."

            draw.text(
                (padding + 36, y - 6),  # Indented more than description
                selector_text,
                fill=(108, 117, 125, 255),  # Gray color
                font=small_font,
            )
            y += LEGEND_LINE_HEIGHT - 8  # Smaller spacing for selector line

    return new_image


# =============================================================================
# Main Annotation Function
# =============================================================================


def annotate_screenshot(
    screenshot_path: str | Path,
    issues: list[dict[str, Any]],
    output_path: Optional[str | Path] = None,
    include_legend: bool = True,
) -> dict[str, Any]:
    """
    Annotate a screenshot with issue markers and borders.

    Args:
        screenshot_path: Path to the original screenshot
        issues: List of issue dictionaries with boundingBox, severity, etc.
        output_path: Optional output path (defaults to screenshot_path with _annotated suffix)
        include_legend: Whether to add a legend at the bottom

    Returns:
        dict with ok, path, annotatedIssues keys
    """
    screenshot_path = Path(screenshot_path)

    if not screenshot_path.exists():
        return {"ok": False, "error": f"Screenshot not found: {screenshot_path}"}

    if output_path is None:
        output_path = screenshot_path.parent / f"{screenshot_path.stem}_annotated.png"
    output_path = Path(output_path)

    try:
        # Load image
        image = Image.open(screenshot_path).convert("RGBA")
        draw = ImageDraw.Draw(image)

        # Get fonts
        marker_font = get_font(MARKER_FONT_SIZE, bold=True)

        # Parse issues
        parsed_issues = [Issue.from_dict(i) for i in issues]

        # Track which issues were annotated
        annotated_issues = []

        # Draw borders and markers for each issue with a bounding box
        for issue in parsed_issues:
            if issue.bounding_box is None:
                continue

            bbox = issue.bounding_box
            color = SEVERITY_COLORS.get(issue.severity, SEVERITY_COLORS["minor"])

            # Draw border around element
            draw_border(draw, bbox, color)

            # Draw numbered marker at top-right corner
            marker_x = min(
                bbox.x + bbox.width + MARKER_RADIUS, image.width - MARKER_RADIUS - 5
            )
            marker_y = max(bbox.y - MARKER_RADIUS, MARKER_RADIUS + 5)

            draw_marker(draw, (marker_x, marker_y), issue.id, color, marker_font)

            annotated_issues.append(
                {
                    "id": issue.id,
                    "severity": issue.severity,
                    "description": issue.description,
                    "markerPosition": {"x": marker_x, "y": marker_y},
                }
            )

        # Add legend if requested
        if include_legend and parsed_issues:
            image = draw_legend(image, parsed_issues)

        # Save annotated image
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(str(output_path), "PNG")

        return {
            "ok": True,
            "path": str(output_path),
            "annotatedIssues": annotated_issues,
            "totalIssues": len(parsed_issues),
            "issuesWithBoundingBox": len(annotated_issues),
        }

    except Exception as e:
        return {"ok": False, "error": str(e)}


def annotate_from_report(
    report: dict[str, Any],
    screenshot_path: Optional[str | Path] = None,
    output_path: Optional[str | Path] = None,
) -> dict[str, Any]:
    """
    Annotate a screenshot using a design review report.

    Args:
        report: Design review report dict with 'issues' and 'artifacts' keys
        screenshot_path: Override screenshot path (defaults to report's screenshot)
        output_path: Override output path

    Returns:
        dict with ok, path, annotatedIssues keys
    """
    if screenshot_path is None:
        artifacts = report.get("artifacts", {})
        screenshot_path = artifacts.get("screenshot")
        if not screenshot_path:
            return {"ok": False, "error": "No screenshot path in report"}

    issues = report.get("issues", [])
    if not issues:
        return {"ok": False, "error": "No issues in report"}

    return annotate_screenshot(
        screenshot_path=screenshot_path,
        issues=issues,
        output_path=output_path,
    )


# =============================================================================
# CLI Entry Point
# =============================================================================


def main() -> None:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Annotate screenshots with design review issues"
    )
    parser.add_argument("screenshot", help="Path to screenshot image")
    parser.add_argument("issues", help="Path to issues JSON file or inline JSON")
    parser.add_argument("--output", "-o", help="Output path for annotated image")
    parser.add_argument("--no-legend", action="store_true", help="Don't include legend")

    args = parser.parse_args()

    # Parse issues
    issues_arg = args.issues
    issues_list: list[dict[str, Any]] = []
    if Path(issues_arg).exists():
        with open(issues_arg) as f:
            loaded = json.load(f)
            # Handle both raw issue list and report format
            if isinstance(loaded, dict) and "issues" in loaded:
                issues_list = loaded["issues"]
            elif isinstance(loaded, list):
                issues_list = loaded
    else:
        try:
            loaded = json.loads(issues_arg)
            if isinstance(loaded, list):
                issues_list = loaded
        except json.JSONDecodeError:
            print(json.dumps({"ok": False, "error": f"Invalid JSON: {issues_arg}"}))
            sys.exit(1)

    result = annotate_screenshot(
        screenshot_path=args.screenshot,
        issues=issues_list,
        output_path=args.output,
        include_legend=not args.no_legend,
    )

    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    main()
