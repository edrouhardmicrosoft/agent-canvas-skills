#!/usr/bin/env python3
"""
DOM Sub-Agent - Analyzes DOM structure and returns compact representation.

Output Budget: ~5K tokens

Usage:
    python dom_agent.py <url> [--selector SELECTOR] [--depth N]
"""

import argparse
import json
import sys
from typing import Optional


class DomAgent:
    """
    Token-efficient DOM analysis agent.

    Returns compact DOM structure instead of full HTML,
    keeping output under ~5K tokens.
    """

    def analyze(
        self,
        url: str,
        selector: Optional[str] = None,
        max_depth: int = 4,
        max_children: int = 10,
        max_text_length: int = 50,
        viewport: tuple[int, int] = (1280, 720),
    ) -> dict:
        """
        Analyze DOM structure and return compact representation.

        Args:
            url: URL to analyze
            selector: Optional CSS selector to scope the analysis
            max_depth: Maximum depth to traverse
            max_children: Maximum children per node
            max_text_length: Maximum text content length
            viewport: Viewport dimensions (width, height)

        Returns:
            {
                "ok": True,
                "rootSelector": "body" or selector,
                "stats": {
                    "totalElements": 150,
                    "maxDepth": 4,
                    "byTag": {"div": 45, "span": 30, ...}
                },
                "structure": {
                    "tag": "main",
                    "id": "app",
                    "classes": ["container"],
                    "children": [...]
                }
            }
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return {
                "ok": False,
                "error": "Playwright not installed. Run: pip install playwright && playwright install chromium",
            }

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                page = browser.new_page(
                    viewport={"width": viewport[0], "height": viewport[1]}
                )

                page.goto(url, wait_until="networkidle")

                # Force browser window to foreground (critical for subprocess execution)
                page.bring_to_front()

                # Get DOM structure via JavaScript
                root_selector = selector or "body"

                dom_data = page.evaluate(
                    f"""
                    (config) => {{
                        const {{ rootSelector, maxDepth, maxChildren, maxTextLength }} = config;
                        
                        const tagCounts = {{}};
                        let totalElements = 0;
                        let actualMaxDepth = 0;
                        
                        function processNode(element, depth) {{
                            if (!element || depth > maxDepth) return null;
                            
                            totalElements++;
                            actualMaxDepth = Math.max(actualMaxDepth, depth);
                            
                            const tag = element.tagName.toLowerCase();
                            tagCounts[tag] = (tagCounts[tag] || 0) + 1;
                            
                            const node = {{
                                tag: tag,
                            }};
                            
                            // Add ID if present
                            if (element.id) {{
                                node.id = element.id;
                            }}
                            
                            // Add classes if present (limit to 5)
                            const classes = Array.from(element.classList).slice(0, 5);
                            if (classes.length > 0) {{
                                node.classes = classes;
                            }}
                            
                            // Add important attributes
                            const importantAttrs = ['role', 'aria-label', 'type', 'name', 'href'];
                            for (const attr of importantAttrs) {{
                                const value = element.getAttribute(attr);
                                if (value) {{
                                    node[attr] = value.length > 50 ? value.slice(0, 47) + '...' : value;
                                }}
                            }}
                            
                            // Add text content for leaf nodes
                            const directText = Array.from(element.childNodes)
                                .filter(n => n.nodeType === 3)
                                .map(n => n.textContent.trim())
                                .filter(t => t.length > 0)
                                .join(' ');
                            
                            if (directText && directText.length > 0) {{
                                node.text = directText.length > maxTextLength 
                                    ? directText.slice(0, maxTextLength - 3) + '...'
                                    : directText;
                            }}
                            
                            // Process children
                            const childElements = Array.from(element.children);
                            if (childElements.length > 0 && depth < maxDepth) {{
                                const processedChildren = [];
                                for (let i = 0; i < Math.min(childElements.length, maxChildren); i++) {{
                                    const child = processNode(childElements[i], depth + 1);
                                    if (child) processedChildren.push(child);
                                }}
                                if (processedChildren.length > 0) {{
                                    node.children = processedChildren;
                                }}
                                if (childElements.length > maxChildren) {{
                                    node.truncated = childElements.length - maxChildren;
                                }}
                            }}
                            
                            return node;
                        }}
                        
                        const root = document.querySelector(rootSelector);
                        if (!root) {{
                            return {{ error: 'Selector not found: ' + rootSelector }};
                        }}
                        
                        const structure = processNode(root, 0);
                        
                        return {{
                            rootSelector: rootSelector,
                            stats: {{
                                totalElements: totalElements,
                                maxDepth: actualMaxDepth,
                                byTag: tagCounts
                            }},
                            structure: structure
                        }};
                    }}
                """,
                    {
                        "rootSelector": root_selector,
                        "maxDepth": max_depth,
                        "maxChildren": max_children,
                        "maxTextLength": max_text_length,
                    },
                )

                browser.close()

            if "error" in dom_data:
                return {"ok": False, "error": dom_data["error"]}

            return {"ok": True, **dom_data}

        except Exception as e:
            return {"ok": False, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(
        description="DOM Sub-Agent - Token-efficient DOM analysis"
    )
    parser.add_argument("url", help="URL to analyze")
    parser.add_argument("--selector", "-s", help="CSS selector to scope the analysis")
    parser.add_argument(
        "--depth", "-d", type=int, default=4, help="Max depth to traverse (default: 4)"
    )
    parser.add_argument(
        "--max-children",
        "-c",
        type=int,
        default=10,
        help="Max children per node (default: 10)",
    )
    parser.add_argument(
        "--max-text",
        "-t",
        type=int,
        default=50,
        help="Max text content length (default: 50)",
    )
    parser.add_argument(
        "--width", type=int, default=1280, help="Viewport width (default: 1280)"
    )
    parser.add_argument(
        "--height", type=int, default=720, help="Viewport height (default: 720)"
    )

    args = parser.parse_args()

    agent = DomAgent()
    result = agent.analyze(
        url=args.url,
        selector=args.selector,
        max_depth=args.depth,
        max_children=args.max_children,
        max_text_length=args.max_text,
        viewport=(args.width, args.height),
    )

    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    main()
