#!/usr/bin/env python3
"""
Tailwind Mapper - Convert CSS values to Tailwind utility classes.

Maps raw CSS property values to their Tailwind class equivalents.
Supports:
- Colors (text-red-500, bg-blue-300)
- Spacing (p-4, m-2, gap-4)
- Font sizes (text-sm, text-lg, text-2xl)
- Font weights (font-bold, font-medium)
- Border radius (rounded-sm, rounded-lg)
- Opacity (opacity-50)
"""

import re
from dataclasses import dataclass
from typing import Optional


# Tailwind default spacing scale (in rem, where 1rem = 16px)
# Key = Tailwind class suffix, Value = pixel value
SPACING_SCALE = {
    "0": 0,
    "px": 1,
    "0.5": 2,
    "1": 4,
    "1.5": 6,
    "2": 8,
    "2.5": 10,
    "3": 12,
    "3.5": 14,
    "4": 16,
    "5": 20,
    "6": 24,
    "7": 28,
    "8": 32,
    "9": 36,
    "10": 40,
    "11": 44,
    "12": 48,
    "14": 56,
    "16": 64,
    "20": 80,
    "24": 96,
    "28": 112,
    "32": 128,
    "36": 144,
    "40": 160,
    "44": 176,
    "48": 192,
    "52": 208,
    "56": 224,
    "60": 240,
    "64": 256,
    "72": 288,
    "80": 320,
    "96": 384,
}

# Reverse mapping: px value -> Tailwind suffix
PX_TO_SPACING = {v: k for k, v in SPACING_SCALE.items()}

# Font size scale: Tailwind class -> (font-size px, line-height)
FONT_SIZE_SCALE = {
    "xs": (12, 16),
    "sm": (14, 20),
    "base": (16, 24),
    "lg": (18, 28),
    "xl": (20, 28),
    "2xl": (24, 32),
    "3xl": (30, 36),
    "4xl": (36, 40),
    "5xl": (48, 48),
    "6xl": (60, 60),
    "7xl": (72, 72),
    "8xl": (96, 96),
    "9xl": (128, 128),
}

# Reverse mapping: px font-size -> Tailwind class
PX_TO_FONT_SIZE = {v[0]: k for k, v in FONT_SIZE_SCALE.items()}

# Font weight scale
FONT_WEIGHT_SCALE = {
    "thin": 100,
    "extralight": 200,
    "light": 300,
    "normal": 400,
    "medium": 500,
    "semibold": 600,
    "bold": 700,
    "extrabold": 800,
    "black": 900,
}

# Reverse mapping
WEIGHT_TO_FONT = {v: k for k, v in FONT_WEIGHT_SCALE.items()}

# Border radius scale (in px)
BORDER_RADIUS_SCALE = {
    "none": 0,
    "sm": 2,
    "DEFAULT": 4,  # "rounded" without suffix
    "md": 6,
    "lg": 8,
    "xl": 12,
    "2xl": 16,
    "3xl": 24,
    "full": 9999,
}

PX_TO_RADIUS = {v: k for k, v in BORDER_RADIUS_SCALE.items()}

# Tailwind default color palette with hex values
# Format: color-shade -> hex
COLOR_PALETTE = {
    # Slate
    "slate-50": "#f8fafc",
    "slate-100": "#f1f5f9",
    "slate-200": "#e2e8f0",
    "slate-300": "#cbd5e1",
    "slate-400": "#94a3b8",
    "slate-500": "#64748b",
    "slate-600": "#475569",
    "slate-700": "#334155",
    "slate-800": "#1e293b",
    "slate-900": "#0f172a",
    "slate-950": "#020617",
    # Gray
    "gray-50": "#f9fafb",
    "gray-100": "#f3f4f6",
    "gray-200": "#e5e7eb",
    "gray-300": "#d1d5db",
    "gray-400": "#9ca3af",
    "gray-500": "#6b7280",
    "gray-600": "#4b5563",
    "gray-700": "#374151",
    "gray-800": "#1f2937",
    "gray-900": "#111827",
    "gray-950": "#030712",
    # Zinc
    "zinc-50": "#fafafa",
    "zinc-100": "#f4f4f5",
    "zinc-200": "#e4e4e7",
    "zinc-300": "#d4d4d8",
    "zinc-400": "#a1a1aa",
    "zinc-500": "#71717a",
    "zinc-600": "#52525b",
    "zinc-700": "#3f3f46",
    "zinc-800": "#27272a",
    "zinc-900": "#18181b",
    "zinc-950": "#09090b",
    # Neutral
    "neutral-50": "#fafafa",
    "neutral-100": "#f5f5f5",
    "neutral-200": "#e5e5e5",
    "neutral-300": "#d4d4d4",
    "neutral-400": "#a3a3a3",
    "neutral-500": "#737373",
    "neutral-600": "#525252",
    "neutral-700": "#404040",
    "neutral-800": "#262626",
    "neutral-900": "#171717",
    "neutral-950": "#0a0a0a",
    # Red
    "red-50": "#fef2f2",
    "red-100": "#fee2e2",
    "red-200": "#fecaca",
    "red-300": "#fca5a5",
    "red-400": "#f87171",
    "red-500": "#ef4444",
    "red-600": "#dc2626",
    "red-700": "#b91c1c",
    "red-800": "#991b1b",
    "red-900": "#7f1d1d",
    "red-950": "#450a0a",
    # Orange
    "orange-50": "#fff7ed",
    "orange-100": "#ffedd5",
    "orange-200": "#fed7aa",
    "orange-300": "#fdba74",
    "orange-400": "#fb923c",
    "orange-500": "#f97316",
    "orange-600": "#ea580c",
    "orange-700": "#c2410c",
    "orange-800": "#9a3412",
    "orange-900": "#7c2d12",
    "orange-950": "#431407",
    # Yellow
    "yellow-50": "#fefce8",
    "yellow-100": "#fef9c3",
    "yellow-200": "#fef08a",
    "yellow-300": "#fde047",
    "yellow-400": "#facc15",
    "yellow-500": "#eab308",
    "yellow-600": "#ca8a04",
    "yellow-700": "#a16207",
    "yellow-800": "#854d0e",
    "yellow-900": "#713f12",
    "yellow-950": "#422006",
    # Green
    "green-50": "#f0fdf4",
    "green-100": "#dcfce7",
    "green-200": "#bbf7d0",
    "green-300": "#86efac",
    "green-400": "#4ade80",
    "green-500": "#22c55e",
    "green-600": "#16a34a",
    "green-700": "#15803d",
    "green-800": "#166534",
    "green-900": "#14532d",
    "green-950": "#052e16",
    # Blue
    "blue-50": "#eff6ff",
    "blue-100": "#dbeafe",
    "blue-200": "#bfdbfe",
    "blue-300": "#93c5fd",
    "blue-400": "#60a5fa",
    "blue-500": "#3b82f6",
    "blue-600": "#2563eb",
    "blue-700": "#1d4ed8",
    "blue-800": "#1e40af",
    "blue-900": "#1e3a8a",
    "blue-950": "#172554",
    # Indigo
    "indigo-50": "#eef2ff",
    "indigo-100": "#e0e7ff",
    "indigo-200": "#c7d2fe",
    "indigo-300": "#a5b4fc",
    "indigo-400": "#818cf8",
    "indigo-500": "#6366f1",
    "indigo-600": "#4f46e5",
    "indigo-700": "#4338ca",
    "indigo-800": "#3730a3",
    "indigo-900": "#312e81",
    "indigo-950": "#1e1b4b",
    # Purple
    "purple-50": "#faf5ff",
    "purple-100": "#f3e8ff",
    "purple-200": "#e9d5ff",
    "purple-300": "#d8b4fe",
    "purple-400": "#c084fc",
    "purple-500": "#a855f7",
    "purple-600": "#9333ea",
    "purple-700": "#7e22ce",
    "purple-800": "#6b21a8",
    "purple-900": "#581c87",
    "purple-950": "#3b0764",
    # Pink
    "pink-50": "#fdf2f8",
    "pink-100": "#fce7f3",
    "pink-200": "#fbcfe8",
    "pink-300": "#f9a8d4",
    "pink-400": "#f472b6",
    "pink-500": "#ec4899",
    "pink-600": "#db2777",
    "pink-700": "#be185d",
    "pink-800": "#9d174d",
    "pink-900": "#831843",
    "pink-950": "#500724",
    # Special colors
    "white": "#ffffff",
    "black": "#000000",
    "transparent": "transparent",
    "current": "currentColor",
}

# Reverse mapping: hex -> color name
HEX_TO_COLOR = {v.lower(): k for k, v in COLOR_PALETTE.items() if v.startswith("#")}

# CSS property to Tailwind prefix mapping
PROPERTY_PREFIXES = {
    "color": "text",
    "background-color": "bg",
    "backgroundColor": "bg",
    "border-color": "border",
    "borderColor": "border",
    "padding": "p",
    "padding-top": "pt",
    "padding-right": "pr",
    "padding-bottom": "pb",
    "padding-left": "pl",
    "paddingTop": "pt",
    "paddingRight": "pr",
    "paddingBottom": "pb",
    "paddingLeft": "pl",
    "margin": "m",
    "margin-top": "mt",
    "margin-right": "mr",
    "margin-bottom": "mb",
    "margin-left": "ml",
    "marginTop": "mt",
    "marginRight": "mr",
    "marginBottom": "mb",
    "marginLeft": "ml",
    "font-size": "text",
    "fontSize": "text",
    "font-weight": "font",
    "fontWeight": "font",
    "border-radius": "rounded",
    "borderRadius": "rounded",
    "gap": "gap",
    "width": "w",
    "height": "h",
    "opacity": "opacity",
}


@dataclass
class TailwindSuggestion:
    """A suggested Tailwind class for a CSS value."""

    css_property: str
    css_value: str
    tailwind_class: str
    confidence: float  # 0.0 - 1.0
    is_exact_match: bool
    fallback_arbitrary: str  # e.g., "text-[#ff0000]"


def parse_px_value(value: str) -> Optional[int]:
    """Parse a CSS pixel value, returning integer pixels."""
    value = value.strip().lower()

    # Handle "0"
    if value == "0":
        return 0

    # Handle "Xpx"
    if value.endswith("px"):
        try:
            return int(float(value[:-2]))
        except ValueError:
            return None

    # Handle rem (assuming 16px base)
    if value.endswith("rem"):
        try:
            return int(float(value[:-3]) * 16)
        except ValueError:
            return None

    return None


def parse_rgb_to_hex(value: str) -> Optional[str]:
    """Convert rgb(r, g, b) or rgba(r, g, b, a) to hex."""
    value = value.strip().lower()

    # Match rgb(r, g, b) or rgba(r, g, b, a)
    rgb_match = re.match(r"rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", value)
    if rgb_match:
        r, g, b = (
            int(rgb_match.group(1)),
            int(rgb_match.group(2)),
            int(rgb_match.group(3)),
        )
        return f"#{r:02x}{g:02x}{b:02x}"

    return None


def normalize_color(value: str) -> Optional[str]:
    """Normalize a color value to lowercase hex."""
    value = value.strip().lower()

    # Already hex
    if value.startswith("#"):
        # Expand shorthand: #abc -> #aabbcc
        if len(value) == 4:
            return f"#{value[1] * 2}{value[2] * 2}{value[3] * 2}"
        return value

    # RGB/RGBA
    hex_color = parse_rgb_to_hex(value)
    if hex_color:
        return hex_color

    # Named colors (basic support)
    named_colors = {
        "red": "#ff0000",
        "green": "#00ff00",
        "blue": "#0000ff",
        "white": "#ffffff",
        "black": "#000000",
        "transparent": "transparent",
    }
    if value in named_colors:
        return named_colors[value]

    return None


def find_closest_color(
    hex_color: str, custom_colors: Optional[dict] = None
) -> tuple[str, float]:
    """
    Find the closest Tailwind color to a hex value.

    Returns (color_name, confidence).
    """
    hex_color = hex_color.lower()

    # Check custom colors first
    if custom_colors:
        for name, value in custom_colors.items():
            if value.lower() == hex_color:
                return name, 1.0

    # Exact match in palette
    if hex_color in HEX_TO_COLOR:
        return HEX_TO_COLOR[hex_color], 1.0

    # Calculate color distance for approximate matching
    def hex_to_rgb(h: str) -> tuple[int, int, int]:
        h = h.lstrip("#")
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

    try:
        target_rgb = hex_to_rgb(hex_color)
    except (ValueError, IndexError):
        return "", 0.0

    best_match = ""
    best_distance = float("inf")

    for palette_hex, color_name in HEX_TO_COLOR.items():
        try:
            palette_rgb = hex_to_rgb(palette_hex)
            # Euclidean distance in RGB space
            distance = sum((a - b) ** 2 for a, b in zip(target_rgb, palette_rgb)) ** 0.5
            if distance < best_distance:
                best_distance = distance
                best_match = color_name
        except (ValueError, IndexError):
            continue

    # Confidence based on distance (max distance in RGB space is ~441)
    confidence = max(
        0, 1 - (best_distance / 100)
    )  # High confidence if within 100 units

    return best_match, confidence


def map_color_to_tailwind(
    css_property: str, value: str, custom_colors: Optional[dict] = None
) -> Optional[TailwindSuggestion]:
    """Map a CSS color value to a Tailwind class."""
    prefix = PROPERTY_PREFIXES.get(css_property, "text")

    normalized = normalize_color(value)
    if not normalized:
        return None

    # Special values
    if normalized == "transparent":
        return TailwindSuggestion(
            css_property=css_property,
            css_value=value,
            tailwind_class=f"{prefix}-transparent",
            confidence=1.0,
            is_exact_match=True,
            fallback_arbitrary=f"{prefix}-[transparent]",
        )

    color_name, confidence = find_closest_color(normalized, custom_colors)

    if color_name:
        tailwind_class = f"{prefix}-{color_name}"
        return TailwindSuggestion(
            css_property=css_property,
            css_value=value,
            tailwind_class=tailwind_class,
            confidence=confidence,
            is_exact_match=confidence == 1.0,
            fallback_arbitrary=f"{prefix}-[{normalized}]",
        )

    # No match, provide arbitrary value
    return TailwindSuggestion(
        css_property=css_property,
        css_value=value,
        tailwind_class=f"{prefix}-[{normalized}]",
        confidence=0.5,
        is_exact_match=False,
        fallback_arbitrary=f"{prefix}-[{normalized}]",
    )


def map_spacing_to_tailwind(
    css_property: str, value: str
) -> Optional[TailwindSuggestion]:
    """Map a CSS spacing value (padding, margin) to a Tailwind class."""
    prefix = PROPERTY_PREFIXES.get(css_property)
    if not prefix:
        return None

    px_value = parse_px_value(value)
    if px_value is None:
        # Can't parse, use arbitrary value
        return TailwindSuggestion(
            css_property=css_property,
            css_value=value,
            tailwind_class=f"{prefix}-[{value}]",
            confidence=0.5,
            is_exact_match=False,
            fallback_arbitrary=f"{prefix}-[{value}]",
        )

    # Exact match
    if px_value in PX_TO_SPACING:
        suffix = PX_TO_SPACING[px_value]
        return TailwindSuggestion(
            css_property=css_property,
            css_value=value,
            tailwind_class=f"{prefix}-{suffix}",
            confidence=1.0,
            is_exact_match=True,
            fallback_arbitrary=f"{prefix}-[{px_value}px]",
        )

    # Find closest value
    closest = min(SPACING_SCALE.values(), key=lambda x: abs(x - px_value))
    suffix = PX_TO_SPACING[closest]
    distance = abs(closest - px_value)
    confidence = max(
        0.5, 1 - (distance / 20)
    )  # Reduce confidence as distance increases

    return TailwindSuggestion(
        css_property=css_property,
        css_value=value,
        tailwind_class=f"{prefix}-{suffix}",
        confidence=confidence,
        is_exact_match=False,
        fallback_arbitrary=f"{prefix}-[{px_value}px]",
    )


def map_font_size_to_tailwind(value: str) -> Optional[TailwindSuggestion]:
    """Map a CSS font-size value to a Tailwind class."""
    px_value = parse_px_value(value)
    if px_value is None:
        return TailwindSuggestion(
            css_property="font-size",
            css_value=value,
            tailwind_class=f"text-[{value}]",
            confidence=0.5,
            is_exact_match=False,
            fallback_arbitrary=f"text-[{value}]",
        )

    # Exact match
    if px_value in PX_TO_FONT_SIZE:
        suffix = PX_TO_FONT_SIZE[px_value]
        return TailwindSuggestion(
            css_property="font-size",
            css_value=value,
            tailwind_class=f"text-{suffix}",
            confidence=1.0,
            is_exact_match=True,
            fallback_arbitrary=f"text-[{px_value}px]",
        )

    # Find closest
    closest = min(PX_TO_FONT_SIZE.keys(), key=lambda x: abs(x - px_value))
    suffix = PX_TO_FONT_SIZE[closest]
    distance = abs(closest - px_value)
    confidence = max(0.5, 1 - (distance / 10))

    return TailwindSuggestion(
        css_property="font-size",
        css_value=value,
        tailwind_class=f"text-{suffix}",
        confidence=confidence,
        is_exact_match=False,
        fallback_arbitrary=f"text-[{px_value}px]",
    )


def map_font_weight_to_tailwind(value: str) -> Optional[TailwindSuggestion]:
    """Map a CSS font-weight value to a Tailwind class."""
    value = value.strip().lower()

    # Handle numeric weights
    try:
        weight = int(value)
    except ValueError:
        # Handle named weights
        if value in FONT_WEIGHT_SCALE:
            return TailwindSuggestion(
                css_property="font-weight",
                css_value=value,
                tailwind_class=f"font-{value}",
                confidence=1.0,
                is_exact_match=True,
                fallback_arbitrary=f"font-[{FONT_WEIGHT_SCALE[value]}]",
            )
        return None

    # Exact numeric match
    if weight in WEIGHT_TO_FONT:
        name = WEIGHT_TO_FONT[weight]
        return TailwindSuggestion(
            css_property="font-weight",
            css_value=value,
            tailwind_class=f"font-{name}",
            confidence=1.0,
            is_exact_match=True,
            fallback_arbitrary=f"font-[{weight}]",
        )

    # Find closest
    closest = min(WEIGHT_TO_FONT.keys(), key=lambda x: abs(x - weight))
    name = WEIGHT_TO_FONT[closest]
    confidence = 0.8 if abs(closest - weight) <= 100 else 0.6

    return TailwindSuggestion(
        css_property="font-weight",
        css_value=value,
        tailwind_class=f"font-{name}",
        confidence=confidence,
        is_exact_match=False,
        fallback_arbitrary=f"font-[{weight}]",
    )


def map_border_radius_to_tailwind(value: str) -> Optional[TailwindSuggestion]:
    """Map a CSS border-radius value to a Tailwind class."""
    px_value = parse_px_value(value)
    if px_value is None:
        return TailwindSuggestion(
            css_property="border-radius",
            css_value=value,
            tailwind_class=f"rounded-[{value}]",
            confidence=0.5,
            is_exact_match=False,
            fallback_arbitrary=f"rounded-[{value}]",
        )

    # Exact match
    if px_value in PX_TO_RADIUS:
        suffix = PX_TO_RADIUS[px_value]
        if suffix == "DEFAULT":
            return TailwindSuggestion(
                css_property="border-radius",
                css_value=value,
                tailwind_class="rounded",
                confidence=1.0,
                is_exact_match=True,
                fallback_arbitrary=f"rounded-[{px_value}px]",
            )
        return TailwindSuggestion(
            css_property="border-radius",
            css_value=value,
            tailwind_class=f"rounded-{suffix}",
            confidence=1.0,
            is_exact_match=True,
            fallback_arbitrary=f"rounded-[{px_value}px]",
        )

    # Find closest
    closest = min(
        [v for v in PX_TO_RADIUS.keys() if v < 9999],
        key=lambda x: abs(x - px_value),
    )
    suffix = PX_TO_RADIUS[closest]
    if suffix == "DEFAULT":
        tw_class = "rounded"
    else:
        tw_class = f"rounded-{suffix}"

    confidence = 0.8 if abs(closest - px_value) <= 4 else 0.6

    return TailwindSuggestion(
        css_property="border-radius",
        css_value=value,
        tailwind_class=tw_class,
        confidence=confidence,
        is_exact_match=False,
        fallback_arbitrary=f"rounded-[{px_value}px]",
    )


def css_to_tailwind(
    css_property: str,
    css_value: str,
    custom_colors: Optional[dict] = None,
    prefer_arbitrary: bool = False,
) -> Optional[TailwindSuggestion]:
    """
    Convert a CSS property/value pair to a Tailwind class suggestion.

    Args:
        css_property: CSS property name (e.g., "color", "padding")
        css_value: CSS value (e.g., "rgb(255, 0, 0)", "16px")
        custom_colors: Optional dict of custom color names -> values
        prefer_arbitrary: If True, always use arbitrary value syntax

    Returns:
        TailwindSuggestion or None if no mapping available
    """
    property_lower = css_property.lower().strip()

    # Color properties
    if property_lower in (
        "color",
        "background-color",
        "backgroundcolor",
        "border-color",
        "bordercolor",
    ):
        suggestion = map_color_to_tailwind(property_lower, css_value, custom_colors)
        if suggestion and prefer_arbitrary:
            suggestion.tailwind_class = suggestion.fallback_arbitrary
        return suggestion

    # Spacing properties
    if property_lower in (
        "padding",
        "padding-top",
        "padding-right",
        "padding-bottom",
        "padding-left",
        "paddingtop",
        "paddingright",
        "paddingbottom",
        "paddingleft",
        "margin",
        "margin-top",
        "margin-right",
        "margin-bottom",
        "margin-left",
        "margintop",
        "marginright",
        "marginbottom",
        "marginleft",
        "gap",
        "width",
        "height",
    ):
        suggestion = map_spacing_to_tailwind(property_lower, css_value)
        if suggestion and prefer_arbitrary:
            suggestion.tailwind_class = suggestion.fallback_arbitrary
        return suggestion

    # Font size
    if property_lower in ("font-size", "fontsize"):
        suggestion = map_font_size_to_tailwind(css_value)
        if suggestion and prefer_arbitrary:
            suggestion.tailwind_class = suggestion.fallback_arbitrary
        return suggestion

    # Font weight
    if property_lower in ("font-weight", "fontweight"):
        suggestion = map_font_weight_to_tailwind(css_value)
        if suggestion and prefer_arbitrary:
            suggestion.tailwind_class = suggestion.fallback_arbitrary
        return suggestion

    # Border radius
    if property_lower in ("border-radius", "borderradius"):
        suggestion = map_border_radius_to_tailwind(css_value)
        if suggestion and prefer_arbitrary:
            suggestion.tailwind_class = suggestion.fallback_arbitrary
        return suggestion

    return None


def suggestion_to_dict(s: TailwindSuggestion) -> dict:
    """Convert suggestion to JSON-serializable dict."""
    return {
        "cssProperty": s.css_property,
        "cssValue": s.css_value,
        "tailwindClass": s.tailwind_class,
        "confidence": round(s.confidence, 3),
        "isExactMatch": s.is_exact_match,
        "fallbackArbitrary": s.fallback_arbitrary,
    }


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 3:
        print("Usage: tailwind_mapper.py <property> <value>", file=sys.stderr)
        print("Example: tailwind_mapper.py color 'rgb(255, 0, 0)'", file=sys.stderr)
        sys.exit(1)

    prop = sys.argv[1]
    value = sys.argv[2]

    suggestion = css_to_tailwind(prop, value)
    if suggestion:
        print(json.dumps(suggestion_to_dict(suggestion), indent=2))
    else:
        print(f"No mapping found for {prop}: {value}", file=sys.stderr)
        sys.exit(1)
