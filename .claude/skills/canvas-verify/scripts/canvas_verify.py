#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "playwright",
#     "axe-playwright-python",
#     "pillow",
# ]
# ///
"""
Canvas Verify - Verify that applied code changes worked correctly.

After canvas-apply modifies source files, canvas-verify captures a new screenshot,
compares it to the baseline, re-runs accessibility scans, and produces a pass/fail summary.

Usage:
    canvas_verify.py --list                           # List sessions with verification status
    canvas_verify.py <url> --session <sessionId>      # Verify changes against session baseline
    canvas_verify.py <url> --session <sessionId> --visual   # Visual comparison only
    canvas_verify.py <url> --session <sessionId> --a11y     # A11y comparison only
    canvas_verify.py <url> --session <sessionId> --full     # Full verification (visual + a11y)
    canvas_verify.py <url> --session <sessionId> --json     # Output as JSON
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

# Add parent directories to path for imports
sys.path.insert(
    0, str(Path(__file__).parent.parent.parent / "canvas-apply" / "scripts")
)
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "agent-eyes" / "scripts"))

from session_parser import find_project_root, find_session_dir, load_session

# Visual diff threshold (percentage of pixels different)
DEFAULT_VISUAL_DIFF_THRESHOLD = 5.0  # 5% difference allowed for "pass"


def get_before_screenshot_b64(session: dict) -> Optional[str]:
    """
    Get before screenshot as base64, handling both v1.0 and v1.1+ session formats.

    v1.0: beforeScreenshot contains base64 string directly
    v1.1+: beforeScreenshotPath contains path to PNG file
    """
    import base64

    # v1.1+ format: path to file
    if path := session.get("beforeScreenshotPath"):
        screenshot_file = Path(path)
        if screenshot_file.exists():
            return base64.b64encode(screenshot_file.read_bytes()).decode("utf-8")

    # v1.0 format: inline base64
    return session.get("beforeScreenshot")


def has_before_screenshot(session: dict) -> bool:
    """Check if session has a before screenshot (any format)."""
    if session.get("beforeScreenshotPath"):
        return Path(session["beforeScreenshotPath"]).exists()
    return session.get("beforeScreenshot") is not None


def resize_with_padding(img, target_width: int, target_height: int):
    """Resize image by padding with white to target dimensions."""
    from PIL import Image

    new_img = Image.new("RGB", (target_width, target_height), (255, 255, 255))
    new_img.paste(img, (0, 0))
    return new_img


def list_sessions() -> list[dict]:
    """List all available canvas sessions with verification status."""
    root = find_project_root()
    sessions_dir = root / ".canvas" / "sessions"

    if not sessions_dir.exists():
        return []

    sessions = []
    for session_path in sessions_dir.iterdir():
        if session_path.is_dir():
            session_file = session_path / "session.json"
            if session_file.exists():
                try:
                    data = json.loads(session_file.read_text())
                    sessions.append(
                        {
                            "id": session_path.name,
                            "url": data.get("url", ""),
                            "startTime": data.get("startTime", ""),
                            "hasChanges": bool(data.get("events", {}).get("edits", [])),
                            "hasBeforeScreenshot": has_before_screenshot(data),
                            "verified": data.get("verification") is not None,
                            "verificationStatus": data.get("verification", {}).get(
                                "overallStatus"
                            ),
                        }
                    )
                except Exception as e:
                    print(
                        f"Warning: Failed to parse {session_file}: {e}",
                        file=sys.stderr,
                    )
                    sessions.append(
                        {
                            "id": session_path.name,
                            "url": "",
                            "startTime": "",
                            "hasChanges": False,
                            "hasBeforeScreenshot": False,
                            "verified": False,
                            "verificationStatus": None,
                        }
                    )

    return sorted(sessions, key=lambda s: s.get("startTime", ""), reverse=True)


def print_sessions(sessions: list[dict]) -> None:
    """Print sessions in a formatted table."""
    if not sessions:
        print("No canvas sessions found.", file=sys.stderr)
        print("Run a canvas-edit session first to generate changes.", file=sys.stderr)
        return

    print(
        f"{'Session ID':<20} {'URL':<30} {'Has Baseline':<12} {'Verified':<10} {'Status':<10}"
    )
    print("-" * 84)
    for s in sessions:
        has_baseline = "Yes" if s["hasBeforeScreenshot"] else "No"
        verified = "Yes" if s["verified"] else "No"
        status = s["verificationStatus"] or "-"
        url = s["url"][:28] + ".." if len(s["url"]) > 30 else s["url"]
        print(f"{s['id']:<20} {url:<30} {has_baseline:<12} {verified:<10} {status:<10}")


def decode_base64_screenshot(data: str) -> bytes:
    """Decode a base64 screenshot, handling data URI prefix."""
    import base64

    if data.startswith("data:"):
        # Remove data URI prefix (e.g., "data:image/png;base64,")
        data = data.split(",", 1)[1]
    return base64.b64decode(data)


def compare_screenshots(
    before_b64: Optional[str],
    after_b64: str,
    threshold: float = DEFAULT_VISUAL_DIFF_THRESHOLD,
) -> dict:
    """
    Compare two screenshots and return diff information.

    Returns dict with:
        - status: "pass" | "fail" | "skip"
        - diffPercentage: float (0-100)
        - beforeScreenshot: base64 string
        - afterScreenshot: base64 string
    """
    if not before_b64:
        return {
            "status": "skip",
            "beforeScreenshot": None,
            "afterScreenshot": after_b64,
            "diffPercentage": None,
            "note": "No baseline screenshot available",
        }

    try:
        from PIL import Image, ImageChops
        import io

        # Decode screenshots
        before_bytes = decode_base64_screenshot(before_b64)
        after_bytes = decode_base64_screenshot(after_b64)

        before_img = Image.open(io.BytesIO(before_bytes)).convert("RGB")
        after_img = Image.open(io.BytesIO(after_bytes)).convert("RGB")

        # Resize if dimensions differ (use the larger dimensions)
        if before_img.size != after_img.size:
            max_width = max(before_img.width, after_img.width)
            max_height = max(before_img.height, after_img.height)
            before_img = resize_with_padding(before_img, max_width, max_height)
            after_img = resize_with_padding(after_img, max_width, max_height)

        # Calculate difference using histogram for performance
        # (avoids iterating all pixels in Python)
        diff = ImageChops.difference(before_img, after_img)

        # Convert to grayscale for simpler histogram analysis
        diff_gray = diff.convert("L")
        histogram = diff_gray.histogram()

        # Count pixels with any difference (non-zero in grayscale)
        total_pixels = before_img.width * before_img.height
        identical_pixels = histogram[0]  # Pixels with value 0 (no difference)
        diff_pixels = total_pixels - identical_pixels
        diff_percentage = (diff_pixels / total_pixels) * 100

        status = "pass" if diff_percentage <= threshold else "fail"

        return {
            "status": status,
            "beforeScreenshot": before_b64,
            "afterScreenshot": after_b64,
            "diffPercentage": round(diff_percentage, 2),
        }

    except ImportError:
        return {
            "status": "skip",
            "beforeScreenshot": before_b64,
            "afterScreenshot": after_b64,
            "diffPercentage": None,
            "note": "PIL not installed. Run: pip install pillow",
        }
    except Exception as e:
        return {
            "status": "skip",
            "beforeScreenshot": before_b64,
            "afterScreenshot": after_b64,
            "diffPercentage": None,
            "note": f"Screenshot comparison failed: {e}",
        }


def get_violation_key(violation: dict) -> str:
    """Generate a unique key for an a11y violation."""
    # Key by rule ID + first target selector + node count for better uniqueness
    rule_id = violation.get("id", "unknown")
    nodes = violation.get("nodes", [])
    if nodes:
        target = nodes[0].get("target", ["unknown"])[0]
    else:
        target = "unknown"
    return f"{rule_id}:{target}:{len(nodes)}"


def compare_a11y(
    before_violations: list,
    after_violations: list,
    baseline_available: bool = True,
) -> dict:
    """
    Compare accessibility violations before and after.

    Returns dict with:
        - status: "pass" | "fail" | "skip"
        - beforeViolations: int
        - afterViolations: int
        - fixed: list of violation descriptions
        - introduced: list of violation descriptions
        - unchanged: list of violation descriptions
    """
    # Build sets of violation keys
    before_keys = {get_violation_key(v): v for v in before_violations}
    after_keys = {get_violation_key(v): v for v in after_violations}

    fixed = []
    introduced = []
    unchanged = []

    # Find fixed violations (in before but not in after)
    for key, v in before_keys.items():
        if key not in after_keys:
            desc = f"{v.get('id', 'unknown')}: {v.get('description', 'No description')}"
            fixed.append(desc)

    # Find introduced violations (in after but not in before)
    for key, v in after_keys.items():
        if key not in before_keys:
            desc = f"{v.get('id', 'unknown')}: {v.get('description', 'No description')}"
            introduced.append(desc)

    # Find unchanged violations (in both)
    for key, v in after_keys.items():
        if key in before_keys:
            desc = f"{v.get('id', 'unknown')}: {v.get('description', 'No description')}"
            unchanged.append(desc)

    # Status: pass if no new violations introduced (or no baseline to compare)
    if not baseline_available:
        status = "pass"  # Can't fail without baseline
    else:
        status = "pass" if len(introduced) == 0 else "fail"

    return {
        "status": status,
        "baselineAvailable": baseline_available,
        "beforeViolations": len(before_violations),
        "afterViolations": len(after_violations),
        "fixed": fixed,
        "introduced": introduced,
        "unchanged": unchanged,
    }


def run_verification(
    url: str,
    session_id: str,
    include_visual: bool = True,
    include_a11y: bool = True,
    threshold: float = DEFAULT_VISUAL_DIFF_THRESHOLD,
) -> dict:
    """
    Run verification against a session baseline.

    Args:
        url: URL to verify
        session_id: Session ID to compare against
        include_visual: Include visual diff
        include_a11y: Include a11y comparison
        threshold: Visual diff threshold percentage (default: 5.0)

    Returns:
        Verification result dict
    """
    from playwright.sync_api import sync_playwright

    # Load session
    session = load_session(session_id)
    if not session:
        return {"ok": False, "error": f"Session not found: {session_id}"}

    result = {
        "ok": True,
        "sessionId": session.get("sessionId", session_id),
        "url": url,
        "verification": {},
        "overallStatus": "pass",
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        try:
            # Navigate to URL
            page.goto(url, wait_until="networkidle", timeout=30000)

            # Force browser window to foreground (critical for subprocess execution)
            page.bring_to_front()

            # Import agent_eyes functions
            from agent_eyes import take_screenshot, run_a11y_scan, inject_canvas_bus

            # Inject canvas bus for consistency
            inject_canvas_bus(page)

            # Visual verification
            if include_visual:
                # Take current screenshot
                screenshot_result = take_screenshot(page, as_base64=True)
                if screenshot_result.get("ok"):
                    after_screenshot = screenshot_result.get("base64")
                    before_screenshot = get_before_screenshot_b64(session)

                    visual_result = compare_screenshots(
                        before_screenshot, after_screenshot, threshold=threshold
                    )
                    result["verification"]["visual"] = visual_result

                    if visual_result["status"] == "fail":
                        result["overallStatus"] = "fail"
                else:
                    result["verification"]["visual"] = {
                        "status": "skip",
                        "note": f"Screenshot failed: {screenshot_result.get('error')}",
                    }

            # A11y verification
            if include_a11y:
                # Run current a11y scan
                a11y_result = run_a11y_scan(page)
                if a11y_result.get("ok"):
                    after_violations = a11y_result.get("violations", [])

                    # Get before violations from session (if stored)
                    before_a11y = session.get("beforeA11y", {})
                    before_violations = before_a11y.get("violations", [])
                    baseline_available = bool(before_a11y)

                    a11y_diff = compare_a11y(
                        before_violations,
                        after_violations,
                        baseline_available=baseline_available,
                    )
                    result["verification"]["a11y"] = a11y_diff

                    if a11y_diff["status"] == "fail":
                        result["overallStatus"] = "fail"
                else:
                    result["verification"]["a11y"] = {
                        "status": "skip",
                        "note": f"A11y scan failed: {a11y_result.get('error')}",
                    }

        except Exception as e:
            result["ok"] = False
            result["error"] = str(e)
        finally:
            browser.close()

    return result


def print_verification_result(
    result: dict, threshold: float = DEFAULT_VISUAL_DIFF_THRESHOLD
) -> None:
    """Print verification result in human-readable format."""
    if not result.get("ok"):
        print(f"Error: {result.get('error')}", file=sys.stderr)
        return

    print(f"Session: {result['sessionId']}")
    print(f"URL: {result['url']}")
    print()

    verification = result.get("verification", {})

    # Visual result
    if "visual" in verification:
        visual = verification["visual"]
        status_emoji = {"pass": "✅", "fail": "❌", "skip": "⏭️"}.get(
            visual["status"], "❓"
        )
        print(f"Visual Comparison: {status_emoji} {visual['status'].upper()}")

        if visual.get("diffPercentage") is not None:
            print(f"  Pixels changed: {visual['diffPercentage']}%")
            print(f"  Threshold: {threshold}%")

        if visual.get("note"):
            print(f"  Note: {visual['note']}")
        print()

    # A11y result
    if "a11y" in verification:
        a11y = verification["a11y"]
        status_emoji = {"pass": "✅", "fail": "❌", "skip": "⏭️"}.get(
            a11y["status"], "❓"
        )
        print(f"Accessibility: {status_emoji} {a11y['status'].upper()}")

        if a11y.get("beforeViolations") is not None:
            print(f"  Before: {a11y['beforeViolations']} violations")
            print(f"  After: {a11y['afterViolations']} violations")

        if a11y.get("fixed"):
            print(f"  Fixed ({len(a11y['fixed'])}):")
            for v in a11y["fixed"][:3]:
                print(f"    ✅ {v}")
            if len(a11y["fixed"]) > 3:
                print(f"    ... and {len(a11y['fixed']) - 3} more")

        if a11y.get("introduced"):
            print(f"  Introduced ({len(a11y['introduced'])}):")
            for v in a11y["introduced"][:3]:
                print(f"    ❌ {v}")
            if len(a11y["introduced"]) > 3:
                print(f"    ... and {len(a11y['introduced']) - 3} more")

        if a11y.get("note"):
            print(f"  Note: {a11y['note']}")
        print()

    # Overall status
    overall = result.get("overallStatus", "unknown")
    overall_emoji = {"pass": "✅", "fail": "❌"}.get(overall, "❓")
    print(f"Overall: {overall_emoji} {overall.upper()}")


def save_verification_result(session_id: str, result: dict) -> bool:
    """
    Save verification result to the session.json file.

    Args:
        session_id: Session ID to update
        result: Verification result dict

    Returns:
        True if saved successfully, False otherwise
    """
    session_dir = find_session_dir(session_id)
    if not session_dir:
        print(f"Error: Session directory not found: {session_id}", file=sys.stderr)
        return False

    session_file = session_dir / "session.json"
    if not session_file.exists():
        print(f"Error: Session file not found: {session_file}", file=sys.stderr)
        return False

    try:
        # Load existing session
        session_data = json.loads(session_file.read_text())

        # Add/update verification result
        session_data["verification"] = {
            "timestamp": result.get("timestamp")
            or __import__("datetime").datetime.now().isoformat(),
            "overallStatus": result.get("overallStatus"),
            "visual": result.get("verification", {}).get("visual"),
            "a11y": result.get("verification", {}).get("a11y"),
        }

        # Write back
        session_file.write_text(json.dumps(session_data, indent=2))
        return True

    except Exception as e:
        print(f"Error saving verification result: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Verify that applied canvas changes worked correctly.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  canvas_verify.py --list                              # List sessions
  canvas_verify.py http://localhost:3000 --session ses-abc123    # Full verification
  canvas_verify.py http://localhost:3000 --session ses-abc123 --visual  # Visual only
  canvas_verify.py http://localhost:3000 --session ses-abc123 --a11y    # A11y only
  canvas_verify.py http://localhost:3000 --session ses-abc123 --json    # JSON output
        """,
    )

    parser.add_argument("url", nargs="?", help="URL to verify")
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available canvas sessions with verification status",
    )
    parser.add_argument(
        "--session",
        "-s",
        help="Session ID to verify against (e.g., ses-abc123 or just abc123)",
    )
    parser.add_argument(
        "--visual",
        action="store_true",
        help="Run visual comparison only",
    )
    parser.add_argument(
        "--a11y",
        action="store_true",
        help="Run accessibility comparison only",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run full verification (visual + a11y) - this is the default",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as JSON",
    )
    parser.add_argument(
        "--threshold",
        "-t",
        type=float,
        default=DEFAULT_VISUAL_DIFF_THRESHOLD,
        help=f"Visual diff threshold percentage (default: {DEFAULT_VISUAL_DIFF_THRESHOLD}%%)",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save verification results to the session.json file",
    )

    args = parser.parse_args()

    # List mode
    if args.list:
        sessions = list_sessions()
        if args.json:
            print(json.dumps(sessions, indent=2))
        else:
            print_sessions(sessions)
        return 0

    # Verify mode
    if not args.url:
        parser.error("URL is required for verification")
    if not args.session:
        parser.error("--session is required for verification")

    # Determine what to verify
    include_visual = True
    include_a11y = True

    if args.visual and not args.a11y and not args.full:
        include_a11y = False
    elif args.a11y and not args.visual and not args.full:
        include_visual = False

    # Run verification
    result = run_verification(
        url=args.url,
        session_id=args.session,
        include_visual=include_visual,
        include_a11y=include_a11y,
        threshold=args.threshold,
    )

    # Output
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_verification_result(result, threshold=args.threshold)

    # Save verification result if requested
    if args.save and result.get("ok"):
        if save_verification_result(args.session, result):
            if not args.json:
                print(f"\nVerification result saved to session {args.session}")
        else:
            print("Warning: Failed to save verification result", file=sys.stderr)

    # Exit code
    if not result.get("ok"):
        return 1
    if result.get("overallStatus") == "fail":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
