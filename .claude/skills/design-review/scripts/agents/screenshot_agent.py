#!/usr/bin/env python3
"""
Screenshot Sub-Agent - Captures screenshots with minimal token overhead.

Output Budget: ~1K tokens

Usage:
    python screenshot_agent.py <url> [--selector SELECTOR] [--output-dir DIR]
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


def generate_session_id() -> str:
    """Generate a unique session ID."""
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")[:-3]
    return f"screenshot_{ts}"


class ScreenshotAgent:
    """
    Token-efficient screenshot agent.

    Returns file paths instead of base64, keeping output under ~1K tokens.
    """

    def __init__(self, output_dir: Optional[Path] = None):
        """
        Initialize the screenshot agent.

        Args:
            output_dir: Directory to save screenshots. Defaults to .canvas/screenshots/
        """
        self.output_dir = output_dir or Path(".canvas/screenshots")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def capture(
        self,
        url: str,
        selector: Optional[str] = None,
        full_page: bool = True,
        viewport: tuple[int, int] = (1280, 720),
    ) -> dict:
        """
        Capture screenshot and return path reference only.

        Args:
            url: URL to capture
            selector: Optional CSS selector to capture specific element
            full_page: Whether to capture full page or just viewport
            viewport: Viewport dimensions (width, height)

        Returns:
            {
                "ok": True,
                "path": ".canvas/screenshots/.../screenshot.png",
                "sizeBytes": 443281,
                "dimensions": {"width": 1280, "height": 720}
            }
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return {
                "ok": False,
                "error": "Playwright not installed. Run: pip install playwright && playwright install chromium",
            }

        session_id = generate_session_id()
        session_dir = self.output_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = session_dir / "screenshot.png"

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                page = browser.new_page(
                    viewport={"width": viewport[0], "height": viewport[1]}
                )

                page.goto(url, wait_until="networkidle")

                if selector:
                    # Capture specific element
                    element = page.query_selector(selector)
                    if element:
                        element.screenshot(path=str(screenshot_path))
                    else:
                        browser.close()
                        return {"ok": False, "error": f"Selector not found: {selector}"}
                else:
                    # Capture full page or viewport
                    page.screenshot(path=str(screenshot_path), full_page=full_page)

                browser.close()

            # Get file stats
            stats = screenshot_path.stat()

            # Get image dimensions (without PIL dependency)
            # Read PNG header for dimensions
            width, height = self._get_png_dimensions(screenshot_path)

            return {
                "ok": True,
                "sessionId": session_id,
                "path": str(screenshot_path),
                "sizeBytes": stats.st_size,
                "dimensions": {"width": width, "height": height},
            }

        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _get_png_dimensions(self, path: Path) -> tuple[int, int]:
        """Extract PNG dimensions from file header."""
        with open(path, "rb") as f:
            # Skip PNG signature (8 bytes) and IHDR chunk length + type (8 bytes)
            f.seek(16)
            # Read width and height (4 bytes each, big-endian)
            import struct

            width = struct.unpack(">I", f.read(4))[0]
            height = struct.unpack(">I", f.read(4))[0]
            return width, height


def main():
    parser = argparse.ArgumentParser(
        description="Screenshot Sub-Agent - Token-efficient screenshot capture"
    )
    parser.add_argument("url", help="URL to capture")
    parser.add_argument("--selector", "-s", help="CSS selector for specific element")
    parser.add_argument("--output-dir", "-o", help="Output directory for screenshots")
    parser.add_argument(
        "--viewport-only",
        action="store_true",
        help="Capture viewport only (not full page)",
    )
    parser.add_argument(
        "--width", type=int, default=1280, help="Viewport width (default: 1280)"
    )
    parser.add_argument(
        "--height", type=int, default=720, help="Viewport height (default: 720)"
    )

    args = parser.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else None
    agent = ScreenshotAgent(output_dir=output_dir)

    result = agent.capture(
        url=args.url,
        selector=args.selector,
        full_page=not args.viewport_only,
        viewport=(args.width, args.height),
    )

    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    main()
