#!/usr/bin/env python3
"""
Token Budget Utilities - Estimate and track token usage.

Based on industry patterns from:
- LangChain TextSplitter
- LlamaIndex TreeSummarize
- OpenAI Cookbook recommendations

Usage:
    from token_budget import estimate_tokens, TokenBudget, BUDGETS

    # Simple estimation
    tokens = estimate_tokens(my_text)

    # Budget tracking
    budget = TokenBudget(limit=80000, warn_at=0.8)
    budget.add("screenshot", 1000)
    budget.add("dom", 5000)

    if budget.should_warn:
        print(f"Warning: {budget.summary}")

    if budget.is_exceeded:
        raise TokenBudgetExceeded(budget.summary)
"""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

# Conservative estimate: ~4 chars per token for English
CHARS_PER_TOKEN = 4

# For base64, slightly lower ratio due to limited charset
BASE64_CHARS_PER_TOKEN = 3.5


def estimate_tokens(text: str, is_base64: bool = False) -> int:
    """
    Estimate token count from text length.

    Uses a simple heuristic: ~4 characters per token for English text,
    ~3.5 for base64. This is conservative (tends to overestimate).

    Args:
        text: Input text to estimate
        is_base64: True if content is base64 encoded

    Returns:
        Estimated token count
    """
    if not text:
        return 0
    ratio = BASE64_CHARS_PER_TOKEN if is_base64 else CHARS_PER_TOKEN
    return int(len(text) / ratio)


def estimate_json_tokens(obj: Any) -> int:
    """
    Estimate tokens for a JSON-serializable object.

    Args:
        obj: Any JSON-serializable Python object

    Returns:
        Estimated token count for the JSON representation
    """
    return estimate_tokens(json.dumps(obj, indent=2))


def estimate_file_tokens(file_path: str) -> int:
    """
    Estimate tokens for a file's contents.

    Args:
        file_path: Path to file

    Returns:
        Estimated token count
    """
    try:
        with open(file_path, "r") as f:
            return estimate_tokens(f.read())
    except (IOError, UnicodeDecodeError):
        return 0


@dataclass
class TokenBudget:
    """
    Track token usage against a budget.

    Provides:
    - Category-based tracking
    - Warning thresholds
    - Utilization reporting
    - Overflow prevention

    Usage:
        budget = TokenBudget(limit=80000, warn_at=0.8)
        budget.add("screenshot", 1000)
        budget.add("dom", 5000)

        if budget.is_exceeded:
            raise TokenBudgetExceeded(budget.summary)
    """

    limit: int
    warn_at: float = 0.8  # Warn when 80% consumed
    usage: Dict[str, int] = field(default_factory=dict)

    @property
    def total_used(self) -> int:
        """Total tokens used across all categories."""
        return sum(self.usage.values())

    @property
    def remaining(self) -> int:
        """Tokens remaining in budget."""
        return max(0, self.limit - self.total_used)

    @property
    def utilization(self) -> float:
        """Fraction of budget consumed (0.0 to 1.0+)."""
        return self.total_used / self.limit if self.limit > 0 else 0

    @property
    def is_exceeded(self) -> bool:
        """True if budget has been exceeded."""
        return self.total_used > self.limit

    @property
    def should_warn(self) -> bool:
        """True if usage exceeds warning threshold."""
        return self.utilization >= self.warn_at

    def add(self, category: str, tokens: int) -> None:
        """
        Add token usage for a category.

        Args:
            category: Name of the usage category (e.g., "screenshot", "dom")
            tokens: Number of tokens to add
        """
        self.usage[category] = self.usage.get(category, 0) + tokens

    def set(self, category: str, tokens: int) -> None:
        """
        Set token usage for a category (replaces previous value).

        Args:
            category: Name of the usage category
            tokens: Number of tokens to set
        """
        self.usage[category] = tokens

    def can_afford(self, tokens: int) -> bool:
        """
        Check if we can afford to spend more tokens.

        Args:
            tokens: Number of tokens to check

        Returns:
            True if spending these tokens would stay within budget
        """
        return self.total_used + tokens <= self.limit

    def reset(self) -> None:
        """Reset all usage to zero."""
        self.usage.clear()

    @property
    def summary(self) -> dict:
        """
        Get budget summary.

        Returns:
            Dict with limit, used, remaining, utilization, breakdown, exceeded
        """
        return {
            "limit": self.limit,
            "used": self.total_used,
            "remaining": self.remaining,
            "utilization": f"{self.utilization:.1%}",
            "breakdown": dict(self.usage),
            "exceeded": self.is_exceeded,
            "warning": self.should_warn,
        }

    def __str__(self) -> str:
        return f"TokenBudget({self.total_used}/{self.limit} = {self.utilization:.1%})"


class TokenBudgetExceeded(Exception):
    """Raised when token budget is exceeded."""

    def __init__(self, summary: Optional[dict] = None, message: Optional[str] = None):
        self.summary = summary or {}
        self.message = message or f"Token budget exceeded: {summary}"
        super().__init__(self.message)


# Preset budgets for common scenarios
BUDGETS = {
    # Compact review - minimal output
    "compact_review": TokenBudget(limit=20000),
    # Full review - standard output with all details
    "full_review": TokenBudget(limit=80000),
    # Sub-agent budget - for individual agents
    "sub_agent": TokenBudget(limit=10000),
    # Screenshot agent - path only, very small
    "screenshot": TokenBudget(limit=1000),
    # Accessibility agent - summarized violations
    "a11y": TokenBudget(limit=5000),
    # DOM agent - compact tree structure
    "dom": TokenBudget(limit=5000),
}


def get_budget(name: str) -> TokenBudget:
    """
    Get a preset budget by name.

    Args:
        name: One of: compact_review, full_review, sub_agent, screenshot, a11y, dom

    Returns:
        New TokenBudget instance with preset limits

    Raises:
        KeyError: If name not found
    """
    preset = BUDGETS.get(name)
    if preset is None:
        raise KeyError(
            f"Unknown budget preset: {name}. Available: {list(BUDGETS.keys())}"
        )
    # Return a new instance to avoid shared state
    return TokenBudget(limit=preset.limit, warn_at=preset.warn_at)


# CLI interface
if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Token Budget Utilities")
    parser.add_argument(
        "text", nargs="?", help="Text to estimate tokens for (or - for stdin)"
    )
    parser.add_argument("--base64", action="store_true", help="Text is base64 encoded")
    parser.add_argument("--file", "-f", help="Estimate tokens for a file")
    parser.add_argument("--json", "-j", help="Estimate tokens for JSON file")
    parser.add_argument(
        "--list-budgets", action="store_true", help="List preset budgets"
    )

    args = parser.parse_args()

    if args.list_budgets:
        print("Available budget presets:")
        for name, budget in BUDGETS.items():
            print(f"  {name}: {budget.limit:,} tokens")
        sys.exit(0)

    if args.file:
        tokens = estimate_file_tokens(args.file)
        print(f"{tokens:,} tokens (estimated)")
    elif args.json:
        with open(args.json) as f:
            obj = json.load(f)
        tokens = estimate_json_tokens(obj)
        print(f"{tokens:,} tokens (estimated)")
    elif args.text:
        if args.text == "-":
            text = sys.stdin.read()
        else:
            text = args.text
        tokens = estimate_tokens(text, is_base64=args.base64)
        print(f"{tokens:,} tokens (estimated)")
    else:
        parser.print_help()
