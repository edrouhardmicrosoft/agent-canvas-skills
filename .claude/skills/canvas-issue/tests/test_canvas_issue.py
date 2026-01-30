#!/usr/bin/env python3
"""
Canvas Issue Test Suite

Tests for the Canvas Issue CLI functionality including:
- GitHub CLI detection (installed/authenticated checks)
- JSON output format validation
- Error handling for missing gh CLI
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

try:
    from playwright.sync_api import sync_playwright, Page
except ImportError:
    print(
        "ERROR: Playwright not installed. Run: pip install playwright && playwright install chromium"
    )
    sys.exit(1)


# =============================================================================
# Test Utilities
# =============================================================================


def get_scripts_dir() -> Path:
    """Get the scripts directory path."""
    return Path(__file__).parent.parent / "scripts"


def run_canvas_issue_cli(args: list) -> Optional[dict]:
    """
    Run canvas_issue.py and return parsed JSON output.

    Args:
        args: List of CLI arguments (e.g., ["check-gh"])

    Returns:
        Parsed JSON output as dict, or None if execution failed
    """
    script_path = get_scripts_dir() / "canvas_issue.py"

    try:
        result = subprocess.run(
            ["uv", "run", str(script_path)] + args,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            print(f"CLI error: {result.stderr}", file=sys.stderr)
            return None

        return json.loads(result.stdout.strip())
    except subprocess.TimeoutExpired:
        print("ERROR: CLI command timed out", file=sys.stderr)
        return None
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to parse JSON output: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return None


# =============================================================================
# Test Result Tracking
# =============================================================================


class TestResults:
    """Track test results."""

    def __init__(self):
        self.results = []

    def add(
        self, test_id: str, test_name: str, passed: bool, detail: Optional[str] = None
    ) -> None:
        if detail is None:
            detail = ""
        self.results.append(
            {
                "id": test_id,
                "test": test_name,
                "pass": passed,
                "detail": detail,
            }
        )

    def print_summary(self) -> None:
        pass_count = sum(1 for r in self.results if r["pass"])
        total_count = len(self.results)

        print(f"\n{'=' * 60}")
        print(f"TEST RESULTS: {pass_count}/{total_count} PASSED")
        print(f"{'=' * 60}\n")

        for r in self.results:
            status = "\033[92m PASS\033[0m" if r["pass"] else "\033[91m FAIL\033[0m"
            print(f"[{r['id']}] {status}: {r['test']}")
            if r["detail"]:
                print(f"       {r['detail']}\n")

    def all_passed(self) -> bool:
        return all(r["pass"] for r in self.results)


# =============================================================================
# Test: check-gh Command
# =============================================================================


def test_check_gh_command(results: TestResults) -> None:
    """Test check-gh subcommand."""

    # Test 1.1 - Command executes successfully
    output = run_canvas_issue_cli(["check-gh"])
    command_success = output is not None
    results.add(
        "1.1",
        "check-gh command executes successfully",
        command_success,
        "CLI returns valid JSON",
    )

    if not output:
        return  # Skip remaining tests if output is invalid

    # Test 1.2 - Output contains 'installed' key
    has_installed = "installed" in output
    results.add(
        "1.2",
        "Output contains 'installed' key",
        has_installed,
        "installed field present in JSON",
    )

    # Test 1.3 - Output contains 'authenticated' key
    has_authenticated = "authenticated" in output
    results.add(
        "1.3",
        "Output contains 'authenticated' key",
        has_authenticated,
        "authenticated field present in JSON",
    )

    # Test 1.4 - Output contains 'username' key
    has_username = "username" in output
    results.add(
        "1.4",
        "Output contains 'username' key",
        has_username,
        "username field present in JSON",
    )

    # Test 1.5 - 'installed' is a boolean
    installed_is_bool = isinstance(output.get("installed"), bool)
    results.add(
        "1.5",
        "'installed' is a boolean",
        installed_is_bool,
        f"installed type: {type(output.get('installed')).__name__}",
    )

    # Test 1.6 - 'authenticated' is a boolean
    authenticated_is_bool = isinstance(output.get("authenticated"), bool)
    results.add(
        "1.6",
        "'authenticated' is a boolean",
        authenticated_is_bool,
        f"authenticated type: {type(output.get('authenticated')).__name__}",
    )

    # Test 1.7 - 'username' is either string or null
    username = output.get("username")
    username_valid = username is None or isinstance(username, str)
    results.add(
        "1.7",
        "'username' is string or null",
        username_valid,
        f"username value: {username} (type: {type(username).__name__})",
    )

    # Test 1.8 - authenticated implies installed
    if output.get("authenticated"):
        authenticated_implies_installed = output.get("installed") is True
        results.add(
            "1.8",
            "If authenticated, then installed",
            authenticated_implies_installed,
            "Logical consistency check",
        )

    # Test 1.9 - username present only if authenticated
    if output.get("authenticated"):
        username_implies_authenticated = output.get("username") is not None
        results.add(
            "1.9",
            "If authenticated, username is not null",
            username_implies_authenticated,
            f"username: {username}",
        )
    else:
        username_null_if_not_auth = output.get("username") is None
        results.add(
            "1.9",
            "If not authenticated, username is null",
            username_null_if_not_auth,
            f"username: {username}",
        )


# =============================================================================
# Test: JSON Output Format
# =============================================================================


def test_json_output_format(results: TestResults) -> None:
    """Test JSON output format and schema."""

    output = run_canvas_issue_cli(["check-gh"])
    if output is None:
        results.add(
            "2.1",
            "JSON output is valid",
            False,
            "Failed to get output",
        )
        return

    # Test 2.1 - Output is valid JSON
    results.add(
        "2.1",
        "JSON output is valid",
        True,
        "Successfully parsed as JSON",
    )

    # Test 2.2 - Output is an object (dict)
    is_object = isinstance(output, dict)
    results.add(
        "2.2",
        "Output is a JSON object",
        is_object,
        f"Type: {type(output).__name__}",
    )

    # Test 2.3 - Output has exactly 3 keys
    has_three_keys = len(output) == 3
    results.add(
        "2.3",
        "Output has exactly 3 keys",
        has_three_keys,
        f"Keys: {list(output.keys())}",
    )

    # Test 2.4 - No extra keys
    expected_keys = {"installed", "authenticated", "username"}
    no_extra_keys = set(output.keys()) == expected_keys
    results.add(
        "2.4",
        "Output keys match spec (no extra keys)",
        no_extra_keys,
        f"Keys: {set(output.keys())}",
    )


# =============================================================================
# Test: Edge Cases
# =============================================================================


def test_edge_cases(results: TestResults) -> None:
    """Test edge cases and error handling."""

    # Test 3.1 - Multiple invocations are consistent
    output1 = run_canvas_issue_cli(["check-gh"])
    output2 = run_canvas_issue_cli(["check-gh"])

    consistent = output1 == output2
    results.add(
        "3.1",
        "Multiple invocations return same result",
        consistent,
        f"Run 1: {output1}, Run 2: {output2}",
    )

    # Test 3.2 - Exit code is always 0
    script_path = get_scripts_dir() / "canvas_issue.py"
    try:
        result = subprocess.run(
            ["uv", "run", str(script_path), "check-gh"],
            capture_output=True,
            timeout=10,
        )
        exit_zero = result.returncode == 0
        results.add(
            "3.2",
            "CLI always exits with code 0",
            exit_zero,
            f"Exit code: {result.returncode}",
        )
    except Exception as e:
        results.add(
            "3.2",
            "CLI always exits with code 0",
            False,
            f"Error: {e}",
        )


# =============================================================================
# Main Test Runner
# =============================================================================


def run_all_tests():
    """Run all tests."""
    results = TestResults()

    print("\n Running Canvas Issue Tests...\n")

    print("  [1/3] Testing check-gh command...")
    test_check_gh_command(results)

    print("  [2/3] Testing JSON output format...")
    test_json_output_format(results)

    print("  [3/3] Testing edge cases...")
    test_edge_cases(results)

    # Print results
    results.print_summary()

    return results.all_passed()


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
