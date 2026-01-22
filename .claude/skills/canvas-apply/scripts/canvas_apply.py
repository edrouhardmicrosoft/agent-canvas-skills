#!/usr/bin/env python3
"""
Canvas Apply - Convert visual UI edit sessions into actual code changes.

Usage:
    canvas_apply.py <session_id>              # Show proposed changes (default)
    canvas_apply.py <session_id> --diff       # Preview diff only
    canvas_apply.py <session_id> --apply      # Apply changes to files
    canvas_apply.py <session_id> --verbose    # Verbose mode with confidence scores
    canvas_apply.py --list                    # List all available sessions
"""

import argparse
import json
import sys
from pathlib import Path

from session_parser import parse_session, find_project_root, find_session_dir
from diff_generator import generate_diffs, format_unified_diff, result_to_dict


CONFIDENCE_THRESHOLD = 0.70


def list_sessions() -> list[dict]:
    """List all available canvas sessions."""
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
                        }
                    )
                except Exception:
                    sessions.append(
                        {
                            "id": session_path.name,
                            "url": "",
                            "startTime": "",
                            "hasChanges": False,
                        }
                    )

    return sorted(sessions, key=lambda s: s.get("startTime", ""), reverse=True)


def print_sessions(sessions: list[dict]) -> None:
    """Print sessions in a formatted table."""
    if not sessions:
        print("No canvas sessions found.", file=sys.stderr)
        print("Run a canvas-edit session first to generate changes.", file=sys.stderr)
        return

    print(f"{'Session ID':<20} {'URL':<40} {'Has Changes':<12}")
    print("-" * 74)
    for s in sessions:
        has_changes = "Yes" if s["hasChanges"] else "No"
        url = s["url"][:38] + ".." if len(s["url"]) > 40 else s["url"]
        print(f"{s['id']:<20} {url:<40} {has_changes:<12}")


def print_diff_preview(result: dict, verbose: bool = False) -> None:
    """Print diff preview to stdout."""
    if not result["fileDiffs"]:
        print("No changes to apply.", file=sys.stderr)
        if result["unmappedChanges"]:
            print(
                "\nUnmapped changes (couldn't find source location):", file=sys.stderr
            )
            for change in result["unmappedChanges"]:
                print(f"  - {change}", file=sys.stderr)
        return

    print(f"Session: {result['sessionId']}")
    print(f"Files to modify: {result['summary']['filesModified']}")
    print()

    for diff in result["fileDiffs"]:
        confidence = diff["confidence"]
        confidence_str = f" (confidence: {confidence:.0%})" if verbose else ""

        if confidence < CONFIDENCE_THRESHOLD:
            print(
                f"⚠️  LOW CONFIDENCE{confidence_str}: {diff['filePath']}",
                file=sys.stderr,
            )
        else:
            print(f"📝 {diff['filePath']}{confidence_str}")

        if verbose:
            print("   Changes:")
            for change in diff["changes"]:
                print(f"     - {change}")

        print()
        print(diff["unifiedDiff"])
        print()

    if result["warnings"]:
        print("Warnings:", file=sys.stderr)
        for warning in result["warnings"]:
            print(f"  ⚠️  {warning}", file=sys.stderr)

    if result["unmappedChanges"]:
        print("\nUnmapped changes (couldn't find source location):", file=sys.stderr)
        for change in result["unmappedChanges"]:
            print(f"  - {change}", file=sys.stderr)


def apply_changes(result: dict, dry_run: bool = False) -> bool:
    """Apply the changes to files. Returns True if successful."""
    if not result["fileDiffs"]:
        print("No changes to apply.", file=sys.stderr)
        return False

    low_confidence = [
        d for d in result["fileDiffs"] if d["confidence"] < CONFIDENCE_THRESHOLD
    ]

    if low_confidence and not dry_run:
        print("⚠️  Some changes have low confidence:", file=sys.stderr)
        for diff in low_confidence:
            print(
                f"   - {diff['filePath']} ({diff['confidence']:.0%})", file=sys.stderr
            )
        print(
            "\nUse --verbose to see details, or --force to apply anyway.",
            file=sys.stderr,
        )
        return False

    from diff_generator import generate_diffs
    from session_parser import parse_session

    manifest = parse_session(result["sessionId"])
    if not manifest:
        print(f"Could not reload session: {result['sessionId']}", file=sys.stderr)
        return False

    diff_result = generate_diffs(manifest)

    applied = 0
    for file_diff in diff_result.file_diffs:
        if dry_run:
            print(f"Would modify: {file_diff.file_path}")
            continue

        try:
            Path(file_diff.file_path).write_text(file_diff.modified_content)
            print(f"✅ Modified: {file_diff.file_path}")
            applied += 1
        except Exception as e:
            print(f"❌ Failed to modify {file_diff.file_path}: {e}", file=sys.stderr)

    if not dry_run:
        print(f"\nApplied changes to {applied} file(s).")

    return applied > 0


def main():
    parser = argparse.ArgumentParser(
        description="Apply canvas session changes to source files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  canvas_apply.py ses-abc123          # Preview changes
  canvas_apply.py ses-abc123 --diff   # Show unified diff
  canvas_apply.py ses-abc123 --apply  # Apply changes
  canvas_apply.py --list              # List sessions
        """,
    )

    parser.add_argument(
        "session_id",
        nargs="?",
        help="Session ID to apply (e.g., ses-abc123 or just abc123)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available canvas sessions",
    )
    parser.add_argument(
        "--diff",
        action="store_true",
        help="Show unified diff preview",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes to source files",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be applied without making changes",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed information including confidence scores",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Apply changes even with low confidence scores",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as JSON",
    )

    args = parser.parse_args()

    if args.list:
        sessions = list_sessions()
        if args.json:
            print(json.dumps(sessions, indent=2))
        else:
            print_sessions(sessions)
        return 0

    if not args.session_id:
        parser.error("session_id is required (unless using --list)")

    manifest = parse_session(args.session_id)
    if not manifest:
        print(f"Session not found: {args.session_id}", file=sys.stderr)

        session_dir = find_session_dir(args.session_id)
        if not session_dir:
            print("\nAvailable sessions:", file=sys.stderr)
            sessions = list_sessions()
            for s in sessions[:5]:
                print(f"  - {s['id']}", file=sys.stderr)
        return 1

    result = generate_diffs(manifest)
    result_dict = result_to_dict(result)

    if args.json:
        print(json.dumps(result_dict, indent=2))
        return 0

    if args.apply:
        if args.force:
            for diff in result_dict["fileDiffs"]:
                diff["confidence"] = 1.0
        success = apply_changes(result_dict, dry_run=args.dry_run)
        return 0 if success else 1

    print_diff_preview(result_dict, verbose=args.verbose)

    if result_dict["fileDiffs"] and not args.diff:
        print("\nTo apply these changes, run:")
        print(f"  canvas_apply.py {args.session_id} --apply")

    return 0


if __name__ == "__main__":
    sys.exit(main())
