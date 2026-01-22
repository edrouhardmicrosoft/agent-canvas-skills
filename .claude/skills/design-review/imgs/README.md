# Reference Images

Add design reference images here for visual comparison.

## Usage

Place PNG, JPG, or WebP images in this directory, then reference them:

```bash
uv run design_review.py compare http://localhost:3000 --reference imgs/homepage.png
```

## Naming Conventions

| Pattern | Example |
|---------|---------|
| Page references | `homepage.png`, `settings.png` |
| Component references | `button-primary.png`, `card-hero.png` |
| State references | `form-error.png`, `loading-state.png` |
| Viewport references | `mobile-nav.png`, `tablet-sidebar.png` |

## Supported Formats

- PNG (recommended for UI)
- JPG/JPEG
- WebP

## Tips

1. **Capture at consistent viewport** - Use same browser size for reference and live
2. **Avoid dynamic content** - Crop or mask timestamps, avatars, etc.
3. **Document the source** - Note where reference came from (Figma, prod, etc.)

## Figma Integration

If you have Figma MCP connected, you can compare directly:

```bash
uv run design_review.py compare http://localhost:3000 \
  --figma "https://figma.com/file/xxx" \
  --frame "Homepage"
```

Without Figma MCP, export frames as PNG and place them here.
