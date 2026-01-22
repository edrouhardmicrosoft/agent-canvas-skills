#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pillow",
#     "scikit-image",
#     "numpy",
# ]
# ///
"""
Image Comparator - Compare screenshots against reference images.

Provides multiple comparison algorithms:
- Pixel diff: Fast, highlights exact pixel differences
- SSIM: Structural similarity index, better for perceptual comparison
- Hybrid: Combines both for comprehensive analysis

Library Usage:
    from image_comparator import compare_images, ComparisonResult

    result = compare_images(
        reference="imgs/homepage.png",
        current="screenshot.png",
        output_diff="diff.png",
        method="hybrid"
    )

CLI Usage:
    uv run image_comparator.py reference.png current.png --output diff.png
    uv run image_comparator.py reference.png current.png --method ssim --threshold 0.95
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

# Try to import skimage for SSIM, fall back to PIL-only mode
try:
    from skimage.metrics import structural_similarity as ssim
    from skimage import img_as_float

    HAS_SKIMAGE = True
except ImportError:
    HAS_SKIMAGE = False


# =============================================================================
# Constants & Configuration
# =============================================================================


class CompareMethod(str, Enum):
    """Available comparison methods."""

    PIXEL = "pixel"  # Fast pixel-by-pixel diff
    SSIM = "ssim"  # Structural similarity (requires scikit-image)
    HYBRID = "hybrid"  # Both methods combined


# Thresholds
DEFAULT_PIXEL_THRESHOLD = 5.0  # 5% pixel difference
DEFAULT_SSIM_THRESHOLD = 0.95  # 95% structural similarity
DEFAULT_DIFF_HIGHLIGHT_COLOR = (255, 0, 100, 180)  # Magenta with transparency

# Diff visualization
DIFF_OUTLINE_WIDTH = 2
DIFF_REGION_MIN_SIZE = 10  # Minimum region size to highlight


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class DiffRegion:
    """A region of difference between images."""

    x: int
    y: int
    width: int
    height: int
    pixel_count: int
    severity: str  # "minor", "moderate", "major"

    def to_dict(self) -> dict:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "pixelCount": self.pixel_count,
            "severity": self.severity,
        }


@dataclass
class ComparisonResult:
    """Result of image comparison."""

    ok: bool
    match: bool  # True if images match within threshold
    method: str

    # Metrics
    pixel_diff_percent: Optional[float] = None
    ssim_score: Optional[float] = None

    # Thresholds used
    pixel_threshold: float = DEFAULT_PIXEL_THRESHOLD
    ssim_threshold: float = DEFAULT_SSIM_THRESHOLD

    # Diff details
    diff_regions: list[DiffRegion] = field(default_factory=list)

    # Paths
    reference_path: Optional[str] = None
    current_path: Optional[str] = None
    diff_path: Optional[str] = None

    # Metadata
    reference_size: Optional[tuple[int, int]] = None
    current_size: Optional[tuple[int, int]] = None
    size_mismatch: bool = False

    # Error info
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "match": self.match,
            "method": self.method,
            "pixelDiffPercent": self.pixel_diff_percent,
            "ssimScore": self.ssim_score,
            "pixelThreshold": self.pixel_threshold,
            "ssimThreshold": self.ssim_threshold,
            "diffRegions": [r.to_dict() for r in self.diff_regions],
            "referencePath": self.reference_path,
            "currentPath": self.current_path,
            "diffPath": self.diff_path,
            "referenceSize": self.reference_size,
            "currentSize": self.current_size,
            "sizeMismatch": self.size_mismatch,
            "error": self.error,
        }


# =============================================================================
# Image Loading & Preprocessing
# =============================================================================


def load_image(path: Path | str) -> Image.Image:
    """Load an image and convert to RGB."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")

    img = Image.open(path)

    # Convert to RGB (drop alpha channel for comparison)
    if img.mode in ("RGBA", "LA", "P"):
        # Create white background for transparent images
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        if img.mode in ("RGBA", "LA"):
            background.paste(img, mask=img.split()[-1])  # Use alpha as mask
            img = background
        else:
            img = img.convert("RGB")
    elif img.mode != "RGB":
        img = img.convert("RGB")

    return img


def resize_to_match(
    reference: Image.Image, current: Image.Image, strategy: str = "pad"
) -> tuple[Image.Image, Image.Image, bool]:
    """
    Resize images to match dimensions.

    Args:
        reference: Reference image
        current: Current image
        strategy: "pad" (add white padding) or "crop" (crop to smaller)

    Returns:
        Tuple of (reference, current, size_mismatch)
    """
    if reference.size == current.size:
        return reference, current, False

    ref_w, ref_h = reference.size
    cur_w, cur_h = current.size

    if strategy == "pad":
        # Pad both to max dimensions
        max_w = max(ref_w, cur_w)
        max_h = max(ref_h, cur_h)

        def pad_image(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
            if img.size == (target_w, target_h):
                return img
            new_img = Image.new("RGB", (target_w, target_h), (255, 255, 255))
            new_img.paste(img, (0, 0))
            return new_img

        return (
            pad_image(reference, max_w, max_h),
            pad_image(current, max_w, max_h),
            True,
        )
    else:
        # Crop to min dimensions
        min_w = min(ref_w, cur_w)
        min_h = min(ref_h, cur_h)

        return (
            reference.crop((0, 0, min_w, min_h)),
            current.crop((0, 0, min_w, min_h)),
            True,
        )


# =============================================================================
# Comparison Algorithms
# =============================================================================


def compute_pixel_diff(
    reference: Image.Image, current: Image.Image
) -> tuple[float, Image.Image]:
    """
    Compute pixel-by-pixel difference.

    Returns:
        Tuple of (diff_percentage, diff_image)
    """
    # Compute absolute difference
    diff = ImageChops.difference(reference, current)

    # Convert to grayscale for analysis
    diff_gray = diff.convert("L")

    # Count non-zero pixels using histogram
    histogram = diff_gray.histogram()
    total_pixels = reference.width * reference.height
    identical_pixels = histogram[0]
    diff_pixels = total_pixels - identical_pixels
    diff_percent = (diff_pixels / total_pixels) * 100

    return diff_percent, diff


def compute_ssim(
    reference: Image.Image, current: Image.Image
) -> tuple[float, Optional[np.ndarray]]:
    """
    Compute Structural Similarity Index (SSIM).

    Returns:
        Tuple of (ssim_score, ssim_diff_map or None)
    """
    if not HAS_SKIMAGE:
        return 0.0, None

    # Convert to numpy arrays
    ref_array = img_as_float(np.array(reference))
    cur_array = img_as_float(np.array(current))

    # Compute SSIM with full diff map
    # Use channel_axis for color images
    score, diff_map = ssim(
        ref_array,
        cur_array,
        full=True,
        channel_axis=2,  # RGB channel axis
        data_range=1.0,
    )

    return float(score), diff_map


def find_diff_regions(
    diff_image: Image.Image, threshold: int = 30, min_size: int = DIFF_REGION_MIN_SIZE
) -> list[DiffRegion]:
    """
    Find contiguous regions of difference.

    Args:
        diff_image: The difference image (from pixel diff)
        threshold: Pixel value threshold for "different"
        min_size: Minimum region size to report

    Returns:
        List of DiffRegion objects
    """
    # Convert to grayscale and threshold
    gray = diff_image.convert("L")

    # Apply threshold to create binary mask
    binary = gray.point(lambda x: 255 if x > threshold else 0)

    # Dilate to connect nearby regions
    binary = binary.filter(ImageFilter.MaxFilter(5))

    # Find bounding boxes of regions using simple flood-fill approach
    # For efficiency, we'll use a grid-based approach
    regions = []
    width, height = binary.size
    pixels = list(binary.getdata())

    # Grid-based region detection (8x8 cells)
    cell_w = max(width // 32, 1)
    cell_h = max(height // 32, 1)

    checked_cells = set()

    for cell_y in range(0, height, cell_h):
        for cell_x in range(0, width, cell_w):
            cell_key = (cell_x // cell_w, cell_y // cell_h)
            if cell_key in checked_cells:
                continue

            # Check if this cell has differences
            has_diff = False
            diff_count = 0

            for y in range(cell_y, min(cell_y + cell_h, height)):
                for x in range(cell_x, min(cell_x + cell_w, width)):
                    idx = y * width + x
                    if idx < len(pixels) and pixels[idx] > 0:
                        has_diff = True
                        diff_count += 1

            if has_diff and diff_count >= min_size:
                # Expand to find full region bounds
                min_x, min_y = cell_x, cell_y
                max_x, max_y = min(cell_x + cell_w, width), min(cell_y + cell_h, height)

                # Simple expansion (could be improved with flood fill)
                region_pixels = diff_count

                # Determine severity based on size
                region_area = (max_x - min_x) * (max_y - min_y)
                total_area = width * height
                area_percent = (region_area / total_area) * 100

                if area_percent > 10:
                    severity = "major"
                elif area_percent > 2:
                    severity = "moderate"
                else:
                    severity = "minor"

                regions.append(
                    DiffRegion(
                        x=min_x,
                        y=min_y,
                        width=max_x - min_x,
                        height=max_y - min_y,
                        pixel_count=region_pixels,
                        severity=severity,
                    )
                )

                checked_cells.add(cell_key)

    # Merge overlapping regions
    merged = merge_regions(regions)

    return merged


def merge_regions(regions: list[DiffRegion]) -> list[DiffRegion]:
    """Merge overlapping or adjacent regions."""
    if len(regions) <= 1:
        return regions

    # Sort by position
    sorted_regions = sorted(regions, key=lambda r: (r.y, r.x))
    merged = []

    for region in sorted_regions:
        if not merged:
            merged.append(region)
            continue

        last = merged[-1]

        # Check if regions overlap or are adjacent
        if (
            region.x <= last.x + last.width + 10
            and region.y <= last.y + last.height + 10
            and region.x + region.width >= last.x - 10
            and region.y + region.height >= last.y - 10
        ):
            # Merge
            new_x = min(last.x, region.x)
            new_y = min(last.y, region.y)
            new_max_x = max(last.x + last.width, region.x + region.width)
            new_max_y = max(last.y + last.height, region.y + region.height)

            merged[-1] = DiffRegion(
                x=new_x,
                y=new_y,
                width=new_max_x - new_x,
                height=new_max_y - new_y,
                pixel_count=last.pixel_count + region.pixel_count,
                severity=max(
                    last.severity,
                    region.severity,
                    key=lambda s: {"minor": 0, "moderate": 1, "major": 2}[s],
                ),
            )
        else:
            merged.append(region)

    return merged


# =============================================================================
# Diff Visualization
# =============================================================================


def generate_diff_image(
    reference: Image.Image,
    current: Image.Image,
    diff_regions: list[DiffRegion],
    pixel_diff: Optional[Image.Image] = None,
    ssim_map: Optional[np.ndarray] = None,
    style: str = "overlay",  # "overlay", "sidebyside", "heatmap"
) -> Image.Image:
    """
    Generate a visual diff image highlighting differences.

    Args:
        reference: Reference image
        current: Current screenshot
        diff_regions: List of diff regions to highlight
        pixel_diff: Pixel difference image (optional)
        ssim_map: SSIM difference map (optional)
        style: Visualization style

    Returns:
        Diff visualization image
    """
    if style == "sidebyside":
        return _generate_sidebyside_diff(reference, current, diff_regions)
    elif style == "heatmap" and pixel_diff is not None:
        return _generate_heatmap_diff(current, pixel_diff)
    else:
        return _generate_overlay_diff(current, diff_regions)


def _generate_overlay_diff(
    current: Image.Image, diff_regions: list[DiffRegion]
) -> Image.Image:
    """Generate overlay-style diff with highlighted regions."""
    # Create RGBA copy for transparency
    result = current.convert("RGBA")

    # Create overlay for highlights
    overlay = Image.new("RGBA", result.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Color coding by severity
    severity_colors = {
        "minor": (255, 193, 7, 100),  # Yellow, semi-transparent
        "moderate": (255, 145, 0, 120),  # Orange
        "major": (220, 53, 69, 140),  # Red
    }

    for region in diff_regions:
        color = severity_colors.get(region.severity, severity_colors["moderate"])

        # Fill region with semi-transparent color
        draw.rectangle(
            [region.x, region.y, region.x + region.width, region.y + region.height],
            fill=color,
            outline=(255, 255, 255, 200),
            width=2,
        )

    # Composite overlay onto result
    result = Image.alpha_composite(result, overlay)

    return result.convert("RGB")


def _generate_sidebyside_diff(
    reference: Image.Image, current: Image.Image, diff_regions: list[DiffRegion]
) -> Image.Image:
    """Generate side-by-side comparison with diff in middle."""
    width = reference.width
    height = reference.height

    # Create wide canvas: reference | diff | current
    total_width = width * 3 + 20  # 10px gaps
    result = Image.new("RGB", (total_width, height + 40), (248, 249, 250))

    # Paste reference on left
    result.paste(reference, (0, 40))

    # Generate and paste diff overlay in middle
    diff_overlay = _generate_overlay_diff(current, diff_regions)
    result.paste(diff_overlay, (width + 10, 40))

    # Paste current on right
    result.paste(current, (width * 2 + 20, 40))

    # Add labels
    draw = ImageDraw.Draw(result)
    try:
        from PIL import ImageFont

        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)
    except Exception:
        font = ImageFont.load_default()

    draw.text((width // 2 - 40, 10), "Reference", fill=(100, 100, 100), font=font)
    draw.text(
        (width + 10 + width // 2 - 20, 10), "Diff", fill=(100, 100, 100), font=font
    )
    draw.text(
        (width * 2 + 20 + width // 2 - 30, 10),
        "Current",
        fill=(100, 100, 100),
        font=font,
    )

    return result


def _generate_heatmap_diff(
    current: Image.Image, pixel_diff: Image.Image
) -> Image.Image:
    """Generate heatmap-style diff showing intensity of changes."""
    # Convert diff to heatmap colors
    diff_gray = pixel_diff.convert("L")

    # Create heatmap (blue -> green -> yellow -> red)
    heatmap = Image.new("RGB", diff_gray.size)
    diff_pixels = list(diff_gray.getdata())

    heatmap_pixels = []
    for p in diff_pixels:
        if p == 0:
            heatmap_pixels.append((0, 0, 0, 0))  # Transparent for no diff
        elif p < 64:
            # Blue to cyan
            heatmap_pixels.append((0, p * 4, 255))
        elif p < 128:
            # Cyan to green
            heatmap_pixels.append((0, 255, 255 - (p - 64) * 4))
        elif p < 192:
            # Green to yellow
            heatmap_pixels.append(((p - 128) * 4, 255, 0))
        else:
            # Yellow to red
            heatmap_pixels.append((255, 255 - (p - 192) * 4, 0))

    heatmap.putdata(heatmap_pixels)

    # Blend with current image
    result = Image.blend(current.convert("RGB"), heatmap, 0.5)

    return result


# =============================================================================
# Main Comparison Function
# =============================================================================


def compare_images(
    reference: str | Path,
    current: str | Path,
    output_diff: Optional[str | Path] = None,
    method: str | CompareMethod = CompareMethod.HYBRID,
    pixel_threshold: float = DEFAULT_PIXEL_THRESHOLD,
    ssim_threshold: float = DEFAULT_SSIM_THRESHOLD,
    diff_style: str = "overlay",
) -> ComparisonResult:
    """
    Compare a current screenshot against a reference image.

    Args:
        reference: Path to reference image
        current: Path to current screenshot
        output_diff: Optional path to save diff visualization
        method: Comparison method ("pixel", "ssim", "hybrid")
        pixel_threshold: Max allowed pixel diff percentage (default 5%)
        ssim_threshold: Min required SSIM score (default 0.95)
        diff_style: Diff visualization style ("overlay", "sidebyside", "heatmap")

    Returns:
        ComparisonResult with match status, metrics, and diff info
    """
    reference = Path(reference)
    current = Path(current)

    if isinstance(method, str):
        method = CompareMethod(method)

    result = ComparisonResult(
        ok=True,
        match=True,
        method=method.value,
        pixel_threshold=pixel_threshold,
        ssim_threshold=ssim_threshold,
        reference_path=str(reference),
        current_path=str(current),
    )

    # Load images
    try:
        ref_img = load_image(reference)
        cur_img = load_image(current)
    except FileNotFoundError as e:
        result.ok = False
        result.error = str(e)
        return result
    except Exception as e:
        result.ok = False
        result.error = f"Failed to load images: {e}"
        return result

    result.reference_size = ref_img.size
    result.current_size = cur_img.size

    # Resize if needed
    ref_img, cur_img, size_mismatch = resize_to_match(ref_img, cur_img)
    result.size_mismatch = size_mismatch

    # Compute pixel diff
    pixel_diff_img = None
    if method in (CompareMethod.PIXEL, CompareMethod.HYBRID):
        diff_percent, pixel_diff_img = compute_pixel_diff(ref_img, cur_img)
        result.pixel_diff_percent = round(diff_percent, 2)

        if diff_percent > pixel_threshold:
            result.match = False

    # Compute SSIM
    ssim_map = None
    if method in (CompareMethod.SSIM, CompareMethod.HYBRID):
        if not HAS_SKIMAGE:
            if method == CompareMethod.SSIM:
                result.ok = False
                result.error = (
                    "SSIM requires scikit-image. Install with: pip install scikit-image"
                )
                return result
            # For hybrid, just skip SSIM
        else:
            ssim_score, ssim_map = compute_ssim(ref_img, cur_img)
            result.ssim_score = round(ssim_score, 4)

            if ssim_score < ssim_threshold:
                result.match = False

    # Find diff regions (from pixel diff)
    if pixel_diff_img:
        result.diff_regions = find_diff_regions(pixel_diff_img)

    # Generate diff visualization
    if output_diff and (not result.match or pixel_diff_img):
        output_diff = Path(output_diff)
        output_diff.parent.mkdir(parents=True, exist_ok=True)

        diff_img = generate_diff_image(
            ref_img,
            cur_img,
            result.diff_regions,
            pixel_diff=pixel_diff_img,
            ssim_map=ssim_map,
            style=diff_style,
        )
        diff_img.save(str(output_diff))
        result.diff_path = str(output_diff)

    return result


def compare_from_base64(
    reference_b64: str,
    current_b64: str,
    output_diff: Optional[str | Path] = None,
    method: str | CompareMethod = CompareMethod.HYBRID,
    pixel_threshold: float = DEFAULT_PIXEL_THRESHOLD,
    ssim_threshold: float = DEFAULT_SSIM_THRESHOLD,
) -> ComparisonResult:
    """
    Compare images from base64 strings.

    Useful for comparing screenshots captured in memory.
    """
    import base64
    import io
    import tempfile

    def decode_b64(data: str) -> bytes:
        if data.startswith("data:"):
            data = data.split(",", 1)[1]
        return base64.b64decode(data)

    # Save to temp files and compare
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as ref_f:
        ref_f.write(decode_b64(reference_b64))
        ref_path = ref_f.name

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as cur_f:
        cur_f.write(decode_b64(current_b64))
        cur_path = cur_f.name

    try:
        result = compare_images(
            reference=ref_path,
            current=cur_path,
            output_diff=output_diff,
            method=method,
            pixel_threshold=pixel_threshold,
            ssim_threshold=ssim_threshold,
        )
        # Clear temp paths from result
        result.reference_path = None
        result.current_path = None
        return result
    finally:
        # Cleanup temp files
        Path(ref_path).unlink(missing_ok=True)
        Path(cur_path).unlink(missing_ok=True)


# =============================================================================
# CLI Entry Point
# =============================================================================


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare images for visual regression testing"
    )
    parser.add_argument("reference", help="Path to reference image")
    parser.add_argument("current", help="Path to current screenshot")
    parser.add_argument("--output", "-o", help="Path to save diff visualization")
    parser.add_argument(
        "--method",
        "-m",
        choices=["pixel", "ssim", "hybrid"],
        default="hybrid",
        help="Comparison method (default: hybrid)",
    )
    parser.add_argument(
        "--pixel-threshold",
        "-p",
        type=float,
        default=DEFAULT_PIXEL_THRESHOLD,
        help=f"Pixel diff threshold %% (default: {DEFAULT_PIXEL_THRESHOLD})",
    )
    parser.add_argument(
        "--ssim-threshold",
        "-s",
        type=float,
        default=DEFAULT_SSIM_THRESHOLD,
        help=f"SSIM threshold (default: {DEFAULT_SSIM_THRESHOLD})",
    )
    parser.add_argument(
        "--style",
        choices=["overlay", "sidebyside", "heatmap"],
        default="overlay",
        help="Diff visualization style (default: overlay)",
    )
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    result = compare_images(
        reference=args.reference,
        current=args.current,
        output_diff=args.output,
        method=args.method,
        pixel_threshold=args.pixel_threshold,
        ssim_threshold=args.ssim_threshold,
        diff_style=args.style,
    )

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        # Human-readable output
        status = "✅ MATCH" if result.match else "❌ MISMATCH"
        print(f"Comparison: {status}")
        print(f"Method: {result.method}")

        if result.pixel_diff_percent is not None:
            print(
                f"Pixel diff: {result.pixel_diff_percent}% (threshold: {result.pixel_threshold}%)"
            )

        if result.ssim_score is not None:
            print(
                f"SSIM score: {result.ssim_score} (threshold: {result.ssim_threshold})"
            )

        if result.size_mismatch:
            print(
                f"⚠️  Size mismatch: reference {result.reference_size} vs current {result.current_size}"
            )

        if result.diff_regions:
            print(f"Diff regions: {len(result.diff_regions)}")
            for i, region in enumerate(result.diff_regions[:5], 1):
                print(
                    f"  {i}. [{region.severity}] {region.width}x{region.height} at ({region.x}, {region.y})"
                )

        if result.diff_path:
            print(f"Diff saved: {result.diff_path}")

        if result.error:
            print(f"Error: {result.error}")

    sys.exit(0 if result.match else 1)


if __name__ == "__main__":
    main()
