/**
 * Canvas Skills - Unified Design Tokens
 * 
 * Shared design tokens for consistent styling across all canvas skills:
 * - agent-canvas (picker overlay)
 * - canvas-edit (annotation toolbar)
 * - design-review (compliance overlay)
 * 
 * Based on Fluent 2 dark theme with accessibility considerations.
 * 
 * @version 1.0.0
 */

// =============================================================================
// Design Tokens
// =============================================================================

export const tokens = {
  // ---------------------------------------------------------------------------
  // Colors - Fluent 2 Dark Theme Inspired
  // ---------------------------------------------------------------------------
  colors: {
    // Primary accent (interactive elements)
    primary: '#58a6ff',
    primaryHover: '#79b8ff',
    primaryLight: 'rgba(88, 166, 255, 0.15)',
    
    // Surfaces
    background: {
      panel: '#1f1f1f',       // Main panel background
      elevated: '#292929',     // Cards, elevated surfaces
      hover: '#3d3d3d',        // Hover state
      active: '#454545',       // Active/pressed state
      overlay: 'rgba(31, 41, 55, 0.95)', // Modal backdrops
    },
    
    // Borders
    border: {
      default: '#3d3d3d',
      subtle: 'rgba(255, 255, 255, 0.05)',
    },
    
    // Text
    text: {
      primary: '#e0e0e0',
      secondary: '#a0a0a0',
      muted: '#6e6e6e',
      disabled: '#666666',
    },
    
    // Semantic / Status colors (the ONLY vibrant colors)
    status: {
      success: '#3fb950',
      successLight: 'rgba(63, 185, 80, 0.15)',
      warning: '#d29922',
      warningLight: 'rgba(210, 153, 34, 0.15)',
      error: '#f85149',
      errorLight: 'rgba(248, 81, 73, 0.15)',
      info: '#58a6ff',
      infoLight: 'rgba(88, 166, 255, 0.15)',
    },
    
    // Element highlight (selection/hover states)
    highlight: 'rgba(88, 166, 255, 0.2)',
  },
  
  // ---------------------------------------------------------------------------
  // Typography
  // ---------------------------------------------------------------------------
  font: {
    family: {
      sans: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
      mono: "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Monaco, 'Consolas', monospace",
    },
    size: {
      xs: '10px',
      sm: '11px',
      base: '12px',
      md: '13px',
      lg: '14px',
      xl: '16px',
    },
    weight: {
      normal: '400',
      medium: '500',
      semibold: '600',
      bold: '700',
    },
    lineHeight: {
      tight: '1.2',
      normal: '1.4',
      relaxed: '1.5',
    },
  },
  
  // ---------------------------------------------------------------------------
  // Spacing
  // ---------------------------------------------------------------------------
  spacing: {
    xs: '4px',
    sm: '6px',
    md: '8px',
    lg: '12px',
    xl: '16px',
    xxl: '24px',
  },
  
  // ---------------------------------------------------------------------------
  // Border Radius
  // ---------------------------------------------------------------------------
  radius: {
    sm: '3px',
    md: '4px',
    lg: '6px',
    xl: '8px',
    full: '9999px',
  },
  
  // ---------------------------------------------------------------------------
  // Shadows
  // ---------------------------------------------------------------------------
  shadow: {
    sm: '0 1px 2px rgba(0, 0, 0, 0.3)',
    md: '0 4px 12px rgba(0, 0, 0, 0.4)',
    lg: '0 4px 16px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(255, 255, 255, 0.05)',
    xl: '0 8px 24px rgba(0, 0, 0, 0.5)',
  },
  
  // ---------------------------------------------------------------------------
  // Motion / Transitions (Fluent 2)
  // ---------------------------------------------------------------------------
  motion: {
    duration: {
      faster: '100ms',
      fast: '150ms',
      normal: '250ms',
      slow: '300ms',
    },
    easing: {
      out: 'cubic-bezier(0.33, 0, 0.1, 1)',
      in: 'cubic-bezier(0.9, 0, 0.67, 1)',
      inOut: 'cubic-bezier(0.85, 0, 0.15, 1)',
    },
  },
  
  // ---------------------------------------------------------------------------
  // Z-Index Layers
  // ---------------------------------------------------------------------------
  zIndex: {
    base: 2147483640,
    overlay: 2147483645,
    panel: 2147483646,
    tooltip: 2147483647,
  },
};

// =============================================================================
// CSS Custom Properties Generation
// =============================================================================

/**
 * Flatten nested token object to CSS variable declarations
 * @param {object} obj - Token object
 * @param {string} prefix - CSS variable prefix
 * @param {string} path - Current path for nesting
 * @returns {string[]} Array of CSS variable declarations
 */
function flattenTokens(obj, prefix = '--canvas', path = '') {
  const vars = [];
  
  for (const [key, value] of Object.entries(obj)) {
    const varName = path ? `${path}-${key}` : key;
    
    if (typeof value === 'object' && value !== null) {
      vars.push(...flattenTokens(value, prefix, varName));
    } else {
      vars.push(`${prefix}-${varName}: ${value};`);
    }
  }
  
  return vars;
}

/**
 * Generate CSS custom properties string from tokens
 * @param {string} prefix - CSS variable prefix (default: '--canvas')
 * @returns {string} CSS custom properties declarations
 */
export function toCSSVars(prefix = '--canvas') {
  return flattenTokens(tokens, prefix).join('\n  ');
}

/**
 * Generate complete CSS :root/:host block with all tokens
 * @returns {string} Complete CSS block
 */
export function getTokenStyles() {
  return `:host, :root {
  ${toCSSVars()}
}`;
}

// =============================================================================
// Runtime Token Injection
// =============================================================================

/**
 * Inject tokens as CSS variables into a root element
 * @param {Document|ShadowRoot|Element} root - Target root (document, shadow root, or element)
 * @returns {HTMLStyleElement} The injected style element
 */
export function injectTokens(root = document) {
  const style = document.createElement('style');
  style.id = '__canvas_design_tokens';
  style.textContent = getTokenStyles();
  
  // Handle different root types
  if (root.head) {
    // Document
    root.head.appendChild(style);
  } else if (root.appendChild) {
    // ShadowRoot or Element
    root.appendChild(style);
  }
  
  return style;
}

/**
 * Remove injected token styles from a root
 * @param {Document|ShadowRoot|Element} root - Target root
 */
export function removeTokens(root = document) {
  const style = (root.head || root).querySelector('#__canvas_design_tokens');
  if (style) {
    style.remove();
  }
}

// =============================================================================
// Token Access Helpers
// =============================================================================

/**
 * Get a specific token value by path
 * @param {string} path - Dot-notation path (e.g., 'colors.primary', 'spacing.md')
 * @returns {*} Token value or undefined
 */
export function getToken(path) {
  return path.split('.').reduce((obj, key) => obj?.[key], tokens);
}

/**
 * Get CSS variable name for a token path
 * @param {string} path - Dot-notation path (e.g., 'colors.primary')
 * @returns {string} CSS variable reference (e.g., 'var(--canvas-colors-primary)')
 */
export function cssVar(path) {
  const varName = `--canvas-${path.replace(/\./g, '-')}`;
  return `var(${varName})`;
}

// =============================================================================
// Severity Color Helpers
// =============================================================================

/**
 * Severity levels mapped to token paths
 */
export const severityColors = {
  blocking: 'colors.status.error',
  critical: 'colors.status.error',
  error: 'colors.status.error',
  major: 'colors.status.warning',
  warning: 'colors.status.warning',
  minor: 'colors.status.info',
  info: 'colors.status.info',
  success: 'colors.status.success',
};

/**
 * Get color for a severity level
 * @param {string} severity - Severity level
 * @returns {string} Color value
 */
export function getSeverityColor(severity) {
  const path = severityColors[severity] || severityColors.minor;
  return getToken(path);
}

/**
 * Get CSS variable for a severity level
 * @param {string} severity - Severity level
 * @returns {string} CSS variable reference
 */
export function getSeverityCSSVar(severity) {
  const path = severityColors[severity] || severityColors.minor;
  return cssVar(path);
}

// =============================================================================
// Default Export
// =============================================================================

export default tokens;
