#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Agent Canvas Setup Checker

Checks if all dependencies for agent-canvas, agent-eyes, and canvas-edit are installed.
Returns JSON with status of each dependency and overall readiness.

Usage:
    uv run check_setup.py check
    uv run check_setup.py install --scope <global|local|temporary>
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def check_python_version() -> dict:
    """Check if Python version is 3.10+."""
    version = sys.version_info
    ok = version >= (3, 10)
    return {
        "name": "Python 3.10+",
        "ok": ok,
        "version": f"{version.major}.{version.minor}.{version.micro}",
        "message": f"Python {version.major}.{version.minor}"
        if ok
        else f"Python {version.major}.{version.minor} (need 3.10+)",
    }


def check_uv_installed() -> dict:
    """Check if uv package manager is installed."""
    uv_path = shutil.which("uv")
    ok = uv_path is not None
    return {
        "name": "uv package manager",
        "ok": ok,
        "path": uv_path,
        "message": "installed" if ok else "not found",
        "install_hint": "curl -LsSf https://astral.sh/uv/install.sh | sh"
        if not ok
        else None,
    }


def check_playwright_browsers() -> dict:
    """Check if Playwright Chromium browser is installed."""
    # Check common locations for playwright browsers
    home = Path.home()
    possible_paths = [
        home / ".cache" / "ms-playwright",  # Linux/Mac default
        home / "Library" / "Caches" / "ms-playwright",  # Mac alternate
        Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", ""))
        if os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
        else None,
    ]

    chromium_found = False
    browser_path = None

    for base_path in possible_paths:
        if base_path and base_path.exists():
            # Look for chromium directory
            for item in base_path.iterdir():
                if item.is_dir() and "chromium" in item.name.lower():
                    chromium_found = True
                    browser_path = str(item)
                    break
        if chromium_found:
            break

    return {
        "name": "Playwright Chromium",
        "ok": chromium_found,
        "path": browser_path,
        "message": "installed" if chromium_found else "not found",
        "install_hint": "playwright install chromium" if not chromium_found else None,
    }


def check_playwright_module() -> dict:
    """Check if playwright Python module can be imported via uv."""
    # We'll check by trying to run a simple Python script via uv
    # that imports playwright
    test_script = """
import sys
try:
    import playwright
    print(playwright.__version__)
except ImportError:
    sys.exit(1)
"""

    try:
        result = subprocess.run(
            ["uv", "run", "--with", "playwright", "python", "-c", test_script],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            return {
                "name": "playwright module",
                "ok": True,
                "version": version,
                "message": f"available (v{version})",
            }
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return {
        "name": "playwright module",
        "ok": True,  # uv will auto-install, so this is always "ok"
        "message": "will be installed by uv on first run",
    }


def check_all() -> dict:
    """Run all checks and return comprehensive status."""
    checks = [
        check_python_version(),
        check_uv_installed(),
        check_playwright_module(),
        check_playwright_browsers(),
    ]

    all_ok = all(c["ok"] for c in checks)
    critical_ok = checks[0]["ok"] and checks[1]["ok"]  # Python and uv are critical
    browsers_ok = checks[3]["ok"]

    return {
        "ok": all_ok,
        "ready": critical_ok and browsers_ok,
        "checks": checks,
        "summary": {
            "critical_dependencies": critical_ok,
            "browsers_installed": browsers_ok,
            "message": get_summary_message(checks, all_ok, critical_ok, browsers_ok),
        },
    }


def get_summary_message(
    checks: list, all_ok: bool, critical_ok: bool, browsers_ok: bool
) -> str:
    """Generate human-readable summary message."""
    if all_ok:
        return "All dependencies satisfied. Ready to use agent-canvas skills."

    if not critical_ok:
        missing = [c["name"] for c in checks[:2] if not c["ok"]]
        return f"Missing critical dependencies: {', '.join(missing)}"

    if not browsers_ok:
        return "Playwright browsers not installed. Run: playwright install chromium"

    return "Some optional dependencies missing but core functionality available."


def install_dependencies(scope: str) -> dict:
    """
    Install dependencies based on scope.

    Scopes:
    - global: Install uv and playwright globally
    - local: Create .venv in project and install there
    - temporary: Just verify uv works (deps installed on-demand)
    """
    results = {"scope": scope, "actions": [], "ok": True}

    # Check uv first
    uv_check = check_uv_installed()
    if not uv_check["ok"]:
        results["actions"].append(
            {
                "action": "install_uv",
                "status": "needed",
                "command": "curl -LsSf https://astral.sh/uv/install.sh | sh",
            }
        )
        results["ok"] = False
        results["message"] = "uv must be installed first. Run the suggested command."
        return results

    # Check Python
    py_check = check_python_version()
    if not py_check["ok"]:
        results["actions"].append(
            {
                "action": "upgrade_python",
                "status": "needed",
                "message": f"Python 3.10+ required, found {py_check['version']}",
            }
        )
        results["ok"] = False
        results["message"] = "Python 3.10+ is required."
        return results

    if scope == "global":
        # Install playwright browsers globally
        browser_check = check_playwright_browsers()
        if not browser_check["ok"]:
            try:
                result = subprocess.run(
                    [
                        "uv",
                        "run",
                        "--with",
                        "playwright",
                        "playwright",
                        "install",
                        "chromium",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=300,  # Browser install can take a while
                )
                if result.returncode == 0:
                    results["actions"].append(
                        {
                            "action": "install_chromium",
                            "status": "success",
                            "message": "Playwright Chromium installed globally",
                        }
                    )
                else:
                    results["actions"].append(
                        {
                            "action": "install_chromium",
                            "status": "failed",
                            "error": result.stderr,
                        }
                    )
                    results["ok"] = False
            except subprocess.TimeoutExpired:
                results["actions"].append(
                    {
                        "action": "install_chromium",
                        "status": "timeout",
                        "message": "Installation timed out",
                    }
                )
                results["ok"] = False
        else:
            results["actions"].append(
                {
                    "action": "install_chromium",
                    "status": "skipped",
                    "message": "Already installed",
                }
            )

    elif scope == "local":
        # Create local venv with playwright
        project_root = Path.cwd()
        venv_path = project_root / ".venv"

        # Create venv if needed
        if not venv_path.exists():
            try:
                result = subprocess.run(
                    ["uv", "venv", str(venv_path)],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if result.returncode == 0:
                    results["actions"].append(
                        {
                            "action": "create_venv",
                            "status": "success",
                            "path": str(venv_path),
                        }
                    )
                else:
                    results["actions"].append(
                        {
                            "action": "create_venv",
                            "status": "failed",
                            "error": result.stderr,
                        }
                    )
                    results["ok"] = False
                    return results
            except subprocess.TimeoutExpired:
                results["actions"].append(
                    {"action": "create_venv", "status": "timeout"}
                )
                results["ok"] = False
                return results
        else:
            results["actions"].append(
                {
                    "action": "create_venv",
                    "status": "skipped",
                    "message": "Already exists",
                }
            )

        # Install playwright in venv
        try:
            result = subprocess.run(
                ["uv", "pip", "install", "playwright", "axe-playwright-python"],
                capture_output=True,
                text=True,
                timeout=120,
                env={**os.environ, "VIRTUAL_ENV": str(venv_path)},
            )
            if result.returncode == 0:
                results["actions"].append(
                    {"action": "install_playwright", "status": "success"}
                )
            else:
                results["actions"].append(
                    {
                        "action": "install_playwright",
                        "status": "failed",
                        "error": result.stderr,
                    }
                )
        except subprocess.TimeoutExpired:
            results["actions"].append(
                {"action": "install_playwright", "status": "timeout"}
            )

        # Install browsers (still global but required)
        browser_check = check_playwright_browsers()
        if not browser_check["ok"]:
            try:
                result = subprocess.run(
                    [
                        "uv",
                        "run",
                        "--with",
                        "playwright",
                        "playwright",
                        "install",
                        "chromium",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                if result.returncode == 0:
                    results["actions"].append(
                        {"action": "install_chromium", "status": "success"}
                    )
                else:
                    results["actions"].append(
                        {
                            "action": "install_chromium",
                            "status": "failed",
                            "error": result.stderr,
                        }
                    )
                    results["ok"] = False
            except subprocess.TimeoutExpired:
                results["actions"].append(
                    {"action": "install_chromium", "status": "timeout"}
                )
                results["ok"] = False

    elif scope == "temporary":
        # For temporary scope, we just ensure browsers are installed
        # uv will handle Python deps on-demand via inline script metadata
        browser_check = check_playwright_browsers()
        if not browser_check["ok"]:
            try:
                result = subprocess.run(
                    [
                        "uv",
                        "run",
                        "--with",
                        "playwright",
                        "playwright",
                        "install",
                        "chromium",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                if result.returncode == 0:
                    results["actions"].append(
                        {
                            "action": "install_chromium",
                            "status": "success",
                            "message": "Browsers installed. Python deps will be cached by uv on first run.",
                        }
                    )
                else:
                    results["actions"].append(
                        {
                            "action": "install_chromium",
                            "status": "failed",
                            "error": result.stderr,
                        }
                    )
                    results["ok"] = False
            except subprocess.TimeoutExpired:
                results["actions"].append(
                    {"action": "install_chromium", "status": "timeout"}
                )
                results["ok"] = False
        else:
            results["actions"].append(
                {
                    "action": "install_chromium",
                    "status": "skipped",
                    "message": "Already installed",
                }
            )

        results["note"] = (
            "Using temporary scope: Python dependencies managed by uv on-demand (cached in ~/.cache/uv)"
        )

    if results["ok"]:
        results["message"] = (
            f"Setup complete ({scope} scope). Ready to use agent-canvas skills."
        )

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Check and install dependencies for agent-canvas skills"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Check command
    check_parser = subparsers.add_parser("check", help="Check dependency status")
    check_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Install command
    install_parser = subparsers.add_parser("install", help="Install dependencies")
    install_parser.add_argument(
        "--scope",
        choices=["global", "local", "temporary"],
        required=True,
        help="Installation scope: global (system-wide), local (project .venv), temporary (uv on-demand)",
    )
    install_parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if args.command == "check":
        result = check_all()
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print("\n=== Agent Canvas Setup Check ===\n")
            for check in result["checks"]:
                status = "✓" if check["ok"] else "✗"
                print(f"  {status} {check['name']}: {check['message']}")
                if check.get("install_hint"):
                    print(f"    → {check['install_hint']}")
            print(f"\n{result['summary']['message']}\n")

        sys.exit(0 if result["ready"] else 1)

    elif args.command == "install":
        result = install_dependencies(args.scope)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"\n=== Agent Canvas Setup ({args.scope}) ===\n")
            for action in result["actions"]:
                status_icon = {
                    "success": "✓",
                    "skipped": "○",
                    "failed": "✗",
                    "needed": "!",
                }.get(action["status"], "?")
                print(
                    f"  {status_icon} {action['action']}: {action.get('message', action['status'])}"
                )
                if action.get("error"):
                    print(f"    Error: {action['error'][:200]}")
            if result.get("note"):
                print(f"\n  Note: {result['note']}")
            print(f"\n{result.get('message', '')}\n")

        sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
