"""
Unit tests for CSS selector generation in annotator.py.

Run with:
    uv run --with pillow --with pytest -- pytest test_annotator.py -v
"""

import pytest
from annotator import (
    _is_utility_class,
    _build_parent_selector,
    _generate_css_selector,
)


class TestIsUtilityClass:
    """Tests for _is_utility_class helper."""

    def test_tailwind_classes(self):
        """Should identify Tailwind utility classes."""
        assert _is_utility_class("flex") is True
        assert _is_utility_class("grid") is True
        assert _is_utility_class("p-4") is True
        assert _is_utility_class("m-2") is True
        assert _is_utility_class("text-sm") is True
        assert _is_utility_class("bg-blue-500") is True
        assert _is_utility_class("w-full") is True
        assert _is_utility_class("h-screen") is True

    def test_bootstrap_classes(self):
        """Should identify Bootstrap utility classes."""
        assert _is_utility_class("col-md-6") is True
        assert _is_utility_class("row-cols-2") is True
        assert _is_utility_class("d-flex") is True
        assert _is_utility_class("d-none") is True

    def test_css_in_js_classes(self):
        """Should identify CSS-in-JS generated classes."""
        assert _is_utility_class("css-1a2b3c") is True
        assert _is_utility_class("css-abc123") is True

    def test_semantic_classes(self):
        """Should NOT identify semantic/component classes as utility."""
        assert _is_utility_class("hero") is False
        assert _is_utility_class("navbar") is False
        assert _is_utility_class("button") is False
        assert _is_utility_class("card") is False
        assert _is_utility_class("modal") is False
        assert _is_utility_class("sidebar") is False
        assert _is_utility_class("footer") is False
        assert _is_utility_class("header") is False

    def test_component_classes(self):
        """Should NOT identify component-style classes as utility."""
        assert _is_utility_class("Button") is False
        assert _is_utility_class("UserProfile") is False
        assert _is_utility_class("nav-link") is False
        assert _is_utility_class("btn-primary") is False


class TestBuildParentSelector:
    """Tests for _build_parent_selector helper."""

    def test_id_priority(self):
        """ID should take priority over classes."""
        parent = {"id": "main-content", "tag": "div", "classes": ["container", "flex"]}
        assert _build_parent_selector(parent) == "#main-content"

    def test_class_selector(self):
        """Should use first non-utility class with tag."""
        parent = {"tag": "section", "classes": ["hero", "flex", "p-4"]}
        assert _build_parent_selector(parent) == "section.hero"

    def test_skip_utility_classes(self):
        """Should skip utility classes and find semantic class."""
        parent = {"tag": "div", "classes": ["flex", "p-4", "container"]}
        assert _build_parent_selector(parent) == "div.container"

    def test_all_utility_classes(self):
        """Should fall back to tag when all classes are utility."""
        parent = {"tag": "div", "classes": ["flex", "p-4", "m-2"]}
        assert _build_parent_selector(parent) == "div"

    def test_no_classes(self):
        """Should return just tag when no classes."""
        parent = {"tag": "main", "classes": []}
        assert _build_parent_selector(parent) == "main"

    def test_default_tag(self):
        """Should default to 'div' when tag not specified."""
        parent = {"classes": ["container"]}
        assert _build_parent_selector(parent) == "div.container"


class TestGenerateCssSelector:
    """Tests for _generate_css_selector function."""

    def test_id_selector(self):
        """Should use ID when available."""
        element_info = {
            "id": "submit-button",
            "tag": "button",
            "classes": ["btn", "btn-primary"],
        }
        assert _generate_css_selector(element_info) == "#submit-button"

    def test_class_selector(self):
        """Should build tag.class selector."""
        element_info = {
            "tag": "p",
            "classes": ["subtitle", "hero-text"],
        }
        assert _generate_css_selector(element_info) == "p.subtitle.hero-text"

    def test_max_two_classes(self):
        """Should use at most 2 specific classes."""
        element_info = {
            "tag": "div",
            "classes": ["card", "featured", "highlighted", "active"],
        }
        assert _generate_css_selector(element_info) == "div.card.featured"

    def test_skip_utility_classes(self):
        """Should skip utility classes when building selector."""
        element_info = {
            "tag": "button",
            "classes": ["flex", "p-4", "btn-primary", "m-2"],
        }
        # btn-primary is the only non-utility class
        assert _generate_css_selector(element_info) == "button.btn-primary"

    def test_tag_only_when_all_utility(self):
        """Should fall back to tag when all classes are utility."""
        element_info = {
            "tag": "span",
            "classes": ["flex", "text-sm", "p-1"],
        }
        assert _generate_css_selector(element_info) == "span"

    def test_parent_chain(self):
        """Should include parent chain for uniqueness."""
        element_info = {
            "tag": "p",
            "classes": ["description"],
            "parent_chain": [
                {"tag": "div", "classes": ["card"]},
                {"tag": "section", "id": "products"},
            ],
        }
        # Parents are reversed, so closest parent first
        assert (
            _generate_css_selector(element_info)
            == "#products > div.card > p.description"
        )

    def test_parent_chain_max_depth(self):
        """Should limit parent chain to 3 levels."""
        element_info = {
            "tag": "span",
            "classes": ["text"],
            "parent_chain": [
                {"tag": "div", "classes": ["level1"]},
                {"tag": "div", "classes": ["level2"]},
                {"tag": "div", "classes": ["level3"]},
                {"tag": "div", "classes": ["level4"]},  # Should be ignored
            ],
        }
        result = _generate_css_selector(element_info)
        # Only 3 parents should be included
        assert result == "div.level3 > div.level2 > div.level1 > span.text"

    def test_empty_parent_chain(self):
        """Should handle empty parent chain."""
        element_info = {
            "tag": "h1",
            "classes": ["title"],
            "parent_chain": [],
        }
        assert _generate_css_selector(element_info) == "h1.title"

    def test_no_classes_no_id(self):
        """Should return just tag when no classes or id."""
        element_info = {
            "tag": "article",
        }
        assert _generate_css_selector(element_info) == "article"

    def test_default_tag(self):
        """Should default to 'div' when tag not specified."""
        element_info = {
            "classes": ["wrapper"],
        }
        assert _generate_css_selector(element_info) == "div.wrapper"

    def test_real_world_example(self):
        """Test with realistic element info from Playwright."""
        element_info = {
            "tag": "p",
            "classes": ["text-gray-600", "text-lg", "subtitle"],
            "parent_chain": [
                {"tag": "div", "classes": ["flex", "flex-col", "hero-content"]},
                {"tag": "section", "classes": ["hero", "bg-gradient-to-r"]},
                {"tag": "main", "id": "main"},
            ],
        }
        # Should produce: #main > section.hero > div.hero-content > p.subtitle
        result = _generate_css_selector(element_info)
        assert result == "#main > section.hero > div.hero-content > p.subtitle"


class TestEdgeCases:
    """Edge case tests."""

    def test_empty_element_info(self):
        """Should handle empty element info gracefully."""
        element_info = {}
        # Should return default 'div'
        assert _generate_css_selector(element_info) == "div"

    def test_none_values(self):
        """Should handle None values in parent chain."""
        element_info = {
            "tag": "span",
            "classes": ["icon"],
            "parent_chain": [
                {"tag": "button", "classes": None},
            ],
        }
        # Should not crash, classes defaults to empty list
        result = _generate_css_selector(element_info)
        assert "button" in result
        assert "span.icon" in result

    def test_special_characters_in_id(self):
        """Should handle IDs with special characters."""
        element_info = {
            "id": "user-profile-123",
            "tag": "div",
        }
        assert _generate_css_selector(element_info) == "#user-profile-123"

    def test_numeric_class_names(self):
        """Should handle numeric-looking class names."""
        element_info = {
            "tag": "div",
            "classes": ["item-1", "row-2", "col-3"],
        }
        # col-3 is utility (col-), item-1 and row-2 are semantic
        result = _generate_css_selector(element_info)
        assert "item-1" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
