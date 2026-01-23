/**
 * Annotation Layer - Badge & Highlight System for Design Review Issues
 * 
 * Creates numbered badges positioned on page elements with hover popovers
 * showing issue details. Includes element highlights and native popover API.
 * 
 * Features:
 * - Numbered badges with severity-colored borders
 * - Position algorithm: top-right of target element with boundary detection
 * - Element highlight overlay on badge hover
 * - Native popover API for issue details
 * - Badge appearance and pulse animations
 * - Handles multiple badges on same element
 * - Repositions on window resize
 * - Canvas bus integration
 * 
 * @version 1.0.0
 */
(() => {
    // Prevent double initialization
    if (window.__annotationLayerActive) return;
    window.__annotationLayerActive = true;

    // =========================================================================
    // Configuration & Constants
    // =========================================================================
    
    const CONFIG = {
        LAYER_ID: '__annotation_layer',
        BADGE_SIZE: 24,
        BADGE_OFFSET: 12, // How much badge overlaps with element
        MARGIN: 8, // Minimum distance from viewport edges
        MULTI_BADGE_OFFSET: 20, // Offset for stacking badges on same element
    };

    // Severity color mapping
    const SEVERITY_COLORS = {
        blocking: '#f85149',
        critical: '#f85149',
        error: '#f85149',
        major: '#d29922',
        warning: '#d29922',
        minor: '#58a6ff',
        info: '#58a6ff',
    };

    // =========================================================================
    // Canvas Bus Integration
    // =========================================================================
    
    const bus = window.__canvasBus;
    if (!bus) {
        console.warn('[AnnotationLayer] Canvas bus not found, running in standalone mode');
    }

    // Register this tool with the bus
    if (bus) {
        bus.state.activeTools.add('annotation-layer');
    }

    // =========================================================================
    // State Management
    // =========================================================================
    
    const state = {
        issues: new Map(), // id -> { issue, badge, popover }
        badgeCounter: 0,
        visible: true,
        elementBadgeCounts: new Map(), // selector -> count (for stacking)
    };

    // =========================================================================
    // CSS Styles
    // =========================================================================
    
    const LAYER_STYLES = `
        /* CSS Variables (Fluent 2 Inspired) */
        :root {
            --annotation-duration-faster: 100ms;
            --annotation-duration-fast: 150ms;
            --annotation-duration-normal: 250ms;
            --annotation-duration-slow: 300ms;
            --annotation-ease-out: cubic-bezier(0.33, 0, 0.1, 1);
            --annotation-ease-in: cubic-bezier(0.9, 0, 0.67, 1);
            --annotation-ease-in-out: cubic-bezier(0.85, 0, 0.15, 1);
        }

        /* Annotation Layer Container */
        #${CONFIG.LAYER_ID} {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: 2147483646; /* One below toolbar */
        }

        /* ==========================================================================
           Badge Component
           ========================================================================== */

        .annotation-badge {
            position: fixed;
            display: flex;
            align-items: center;
            justify-content: center;
            width: ${CONFIG.BADGE_SIZE}px;
            height: ${CONFIG.BADGE_SIZE}px;
            border-radius: 50%;
            background: #292929;
            border: 2px solid currentColor;
            color: #e0e0e0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            pointer-events: auto;
            z-index: 2147483646;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);
            transition: transform var(--annotation-duration-faster) var(--annotation-ease-out);
        }

        .annotation-badge:hover {
            transform: scale(1.1);
        }

        .annotation-badge:focus-visible {
            outline: 2px solid #58a6ff;
            outline-offset: 2px;
        }

        /* Severity Colors */
        .annotation-badge.severity-blocking,
        .annotation-badge.severity-critical,
        .annotation-badge.severity-error {
            border-color: #f85149;
        }

        .annotation-badge.severity-major,
        .annotation-badge.severity-warning {
            border-color: #d29922;
        }

        .annotation-badge.severity-minor,
        .annotation-badge.severity-info {
            border-color: #58a6ff;
        }

        /* Badge Appearance Animation */
        @keyframes badgeAppear {
            0% {
                opacity: 0;
                transform: scale(0.5);
            }
            100% {
                opacity: 1;
                transform: scale(1);
            }
        }

        .annotation-badge.appearing {
            animation: badgeAppear var(--annotation-duration-fast) var(--annotation-ease-out) forwards;
        }

        /* Badge Pulse Animation (for new issues) */
        @keyframes badgePulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.15); }
        }

        .annotation-badge.new {
            animation: badgePulse var(--annotation-duration-slow) var(--annotation-ease-in-out) 2;
        }

        /* Hidden state */
        .annotation-badge.hidden {
            opacity: 0;
            pointer-events: none;
        }

        /* ==========================================================================
           Highlight Overlay
           ========================================================================== */

        .annotation-highlight {
            position: fixed;
            pointer-events: none;
            background: rgba(248, 81, 73, 0.1);
            border: 2px solid #f85149;
            border-radius: 4px;
            opacity: 0;
            transition: opacity var(--annotation-duration-fast) var(--annotation-ease-out);
            z-index: 2147483645; /* Below badges */
        }

        .annotation-highlight.visible {
            opacity: 1;
        }

        /* Severity-specific highlight colors */
        .annotation-highlight.severity-blocking,
        .annotation-highlight.severity-critical,
        .annotation-highlight.severity-error {
            background: rgba(248, 81, 73, 0.1);
            border-color: #f85149;
        }

        .annotation-highlight.severity-major,
        .annotation-highlight.severity-warning {
            background: rgba(210, 153, 34, 0.1);
            border-color: #d29922;
        }

        .annotation-highlight.severity-minor,
        .annotation-highlight.severity-info {
            background: rgba(88, 166, 255, 0.1);
            border-color: #58a6ff;
        }

        /* ==========================================================================
           Popover Component
           ========================================================================== */

        .annotation-popover {
            position: fixed;
            background: #292929;
            border: 1px solid #3d3d3d;
            border-radius: 8px;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(255, 255, 255, 0.05);
            color: #e0e0e0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            font-size: 13px;
            min-width: 280px;
            max-width: 400px;
            padding: 0;
            margin: 0;
            border: none;
            z-index: 2147483647;
            pointer-events: auto;
        }

        /* Popover open state animation */
        .annotation-popover {
            opacity: 0;
            transform: translateY(-8px);
            transition: 
                opacity var(--annotation-duration-fast) var(--annotation-ease-out),
                transform var(--annotation-duration-fast) var(--annotation-ease-out);
        }

        .annotation-popover:popover-open {
            opacity: 1;
            transform: translateY(0);
        }

        /* Popover Header */
        .popover-header {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 12px;
            padding: 12px 16px;
            border-bottom: 1px solid #3d3d3d;
        }

        .popover-title {
            font-size: 14px;
            font-weight: 600;
            color: #e0e0e0;
            line-height: 1.4;
            flex: 1;
        }

        .severity-badge {
            display: inline-flex;
            align-items: center;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            flex-shrink: 0;
        }

        .severity-badge.blocking,
        .severity-badge.critical,
        .severity-badge.error {
            background: rgba(248, 81, 73, 0.2);
            color: #f85149;
        }

        .severity-badge.major,
        .severity-badge.warning {
            background: rgba(210, 153, 34, 0.2);
            color: #d29922;
        }

        .severity-badge.minor,
        .severity-badge.info {
            background: rgba(88, 166, 255, 0.2);
            color: #58a6ff;
        }

        /* Popover Body */
        .popover-body {
            padding: 12px 16px;
        }

        .popover-description {
            margin: 0 0 12px 0;
            color: #a0a0a0;
            line-height: 1.5;
        }

        /* Popover Meta */
        .popover-meta {
            display: grid;
            grid-template-columns: auto 1fr;
            gap: 6px 12px;
            margin: 0;
            font-size: 12px;
        }

        .popover-meta dt {
            color: #666666;
            font-weight: 500;
        }

        .popover-meta dd {
            color: #a0a0a0;
            margin: 0;
        }

        .popover-meta code {
            background: #333333;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'SF Mono', Monaco, 'Consolas', monospace;
            font-size: 11px;
            color: #e0e0e0;
        }

        /* Popover Recommendation */
        .popover-recommendation {
            margin-top: 12px;
            padding: 10px 12px;
            background: #333333;
            border-radius: 6px;
            border-left: 3px solid #58a6ff;
        }

        .popover-recommendation strong {
            color: #58a6ff;
            font-weight: 600;
        }

        .popover-recommendation p {
            margin: 4px 0 0 0;
            color: #a0a0a0;
            line-height: 1.4;
        }

        /* Visibility toggle */
        .annotation-badge.annotations-hidden,
        .annotation-highlight.annotations-hidden,
        .annotation-popover.annotations-hidden {
            display: none !important;
        }
    `;

    // =========================================================================
    // Create Layer Container
    // =========================================================================
    
    // Inject styles
    const styleSheet = document.createElement('style');
    styleSheet.id = `${CONFIG.LAYER_ID}_styles`;
    styleSheet.textContent = LAYER_STYLES;
    document.head.appendChild(styleSheet);

    // Create layer container
    const layer = document.createElement('div');
    layer.id = CONFIG.LAYER_ID;
    layer.setAttribute('data-agent-visible', 'true'); // Annotations should be visible to agent-eyes
    document.body.appendChild(layer);

    // Create highlight element (reused)
    const highlight = document.createElement('div');
    highlight.className = 'annotation-highlight';
    layer.appendChild(highlight);

    // =========================================================================
    // Badge Positioning Algorithm
    // =========================================================================
    
    function positionBadge(element, badgeNumber, sameElementIndex = 0) {
        const rect = element.getBoundingClientRect();
        const scrollX = window.scrollX || window.pageXOffset;
        const scrollY = window.scrollY || window.pageYOffset;
        
        // Default: top-right corner of element with offset for stacking
        let left = rect.right - CONFIG.BADGE_OFFSET + (sameElementIndex * CONFIG.MULTI_BADGE_OFFSET);
        let top = rect.top - CONFIG.BADGE_OFFSET - (sameElementIndex * CONFIG.MULTI_BADGE_OFFSET);
        
        // Boundary detection: keep badge on screen
        const margin = CONFIG.MARGIN;
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;
        
        // Horizontal bounds
        if (left + CONFIG.BADGE_SIZE > viewportWidth - margin) {
            // Move to left side of element
            left = rect.left - CONFIG.BADGE_OFFSET;
        }
        if (left < margin) {
            left = margin;
        }
        
        // Vertical bounds
        if (top < margin) {
            top = margin;
        }
        if (top + CONFIG.BADGE_SIZE > viewportHeight - margin) {
            top = viewportHeight - CONFIG.BADGE_SIZE - margin;
        }
        
        return { left, top };
    }

    // =========================================================================
    // Highlight Element
    // =========================================================================
    
    function showHighlight(element, severity) {
        const rect = element.getBoundingClientRect();
        
        highlight.style.left = `${rect.left}px`;
        highlight.style.top = `${rect.top}px`;
        highlight.style.width = `${rect.width}px`;
        highlight.style.height = `${rect.height}px`;
        
        // Update severity class
        highlight.className = `annotation-highlight severity-${severity} visible`;
    }

    function hideHighlight() {
        highlight.classList.remove('visible');
    }

    // =========================================================================
    // Popover Creation
    // =========================================================================
    
    function createPopover(issue, badgeNumber) {
        const popover = document.createElement('div');
        popover.className = 'annotation-popover';
        popover.id = `annotation-popover-${issue.id}`;
        popover.setAttribute('popover', 'auto');
        
        const severity = issue.severity || 'minor';
        const pillar = issue.pillar || 'General';
        const checkId = issue.checkId || issue.check || 'unknown';
        const selector = issue.cssSelector || issue.selector || issue.element || 'unknown';
        const description = issue.description || 'No description provided';
        const recommendation = issue.recommendation || issue.fix || null;
        const title = issue.title || description.split('\n')[0].substring(0, 60);
        
        popover.innerHTML = `
            <div class="popover-header">
                <span class="popover-title">${escapeHtml(title)}</span>
                <span class="severity-badge ${severity}">${severity}</span>
            </div>
            <div class="popover-body">
                <p class="popover-description">${escapeHtml(description)}</p>
                <dl class="popover-meta">
                    <dt>Pillar</dt>
                    <dd>${escapeHtml(pillar)}</dd>
                    <dt>Check</dt>
                    <dd>${escapeHtml(checkId)}</dd>
                    <dt>Selector</dt>
                    <dd><code>${escapeHtml(selector)}</code></dd>
                </dl>
                ${recommendation ? `
                <div class="popover-recommendation">
                    <strong>Fix:</strong>
                    <p>${escapeHtml(recommendation)}</p>
                </div>
                ` : ''}
            </div>
        `;
        
        return popover;
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // =========================================================================
    // Badge Creation
    // =========================================================================
    
    function createBadge(issue) {
        const severity = issue.severity || 'minor';
        const badgeNumber = ++state.badgeCounter;
        
        // Create badge button
        const badge = document.createElement('button');
        badge.className = `annotation-badge severity-${severity} appearing`;
        badge.setAttribute('aria-label', `Issue ${badgeNumber}: ${issue.description || 'Design issue'}`);
        badge.setAttribute('data-issue-id', issue.id);
        badge.setAttribute('data-badge-number', badgeNumber);
        badge.textContent = badgeNumber;
        
        // Create popover
        const popover = createPopover(issue, badgeNumber);
        
        // Link badge to popover
        badge.setAttribute('popovertarget', popover.id);
        badge.setAttribute('aria-describedby', popover.id);
        
        // Track element badge count for stacking
        const selector = issue.cssSelector || issue.selector || issue.element;
        const currentCount = state.elementBadgeCounts.get(selector) || 0;
        state.elementBadgeCounts.set(selector, currentCount + 1);
        
        // Find target element and position badge
        const targetElement = findTargetElement(issue);
        if (targetElement) {
            const position = positionBadge(targetElement, badgeNumber, currentCount);
            badge.style.left = `${position.left}px`;
            badge.style.top = `${position.top}px`;
        } else {
            // Fallback: position at top-left with offset
            badge.style.left = `${CONFIG.MARGIN + (badgeNumber - 1) * 30}px`;
            badge.style.top = `${CONFIG.MARGIN}px`;
        }
        
        // Add to layer
        layer.appendChild(badge);
        layer.appendChild(popover);
        
        // Event handlers
        badge.addEventListener('mouseenter', () => {
            if (targetElement) {
                showHighlight(targetElement, severity);
            }
            emitEvent('annotation.hovered', { id: issue.id, badgeNumber });
        });
        
        badge.addEventListener('mouseleave', () => {
            hideHighlight();
        });
        
        badge.addEventListener('click', () => {
            emitEvent('annotation.clicked', { id: issue.id, badgeNumber, issue });
        });
        
        // Popover focus management
        popover.addEventListener('toggle', (e) => {
            if (e.newState === 'closed') {
                // Return focus to badge
                badge.focus();
            }
        });
        
        // Remove appearing class after animation
        setTimeout(() => {
            badge.classList.remove('appearing');
            badge.classList.add('new');
            // Remove pulse after animation completes
            setTimeout(() => {
                badge.classList.remove('new');
            }, 600); // 300ms * 2 pulses
        }, 150);
        
        return { badge, popover, targetElement };
    }

    function findTargetElement(issue) {
        const selector = issue.cssSelector || issue.selector || issue.element;
        if (!selector) return null;
        
        try {
            return document.querySelector(selector);
        } catch (e) {
            console.warn(`[AnnotationLayer] Invalid selector: ${selector}`);
            return null;
        }
    }

    // =========================================================================
    // Public API Methods
    // =========================================================================
    
    function addIssue(issue) {
        // Generate ID if not provided
        if (!issue.id) {
            issue.id = `issue-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
        }
        
        // Don't add duplicates
        if (state.issues.has(issue.id)) {
            console.warn(`[AnnotationLayer] Issue already exists: ${issue.id}`);
            return state.badgeCounter;
        }
        
        const { badge, popover, targetElement } = createBadge(issue);
        
        state.issues.set(issue.id, {
            issue,
            badge,
            popover,
            targetElement,
            selector: issue.cssSelector || issue.selector || issue.element
        });
        
        emitEvent('annotation.added', { 
            id: issue.id, 
            badgeNumber: state.badgeCounter,
            totalCount: state.issues.size
        });
        
        return state.badgeCounter;
    }

    function removeIssue(id) {
        const entry = state.issues.get(id);
        if (!entry) {
            console.warn(`[AnnotationLayer] Issue not found: ${id}`);
            return false;
        }
        
        // Remove badge and popover from DOM
        entry.badge.remove();
        entry.popover.remove();
        
        // Update element badge count
        const selector = entry.selector;
        if (selector && state.elementBadgeCounts.has(selector)) {
            const count = state.elementBadgeCounts.get(selector) - 1;
            if (count <= 0) {
                state.elementBadgeCounts.delete(selector);
            } else {
                state.elementBadgeCounts.set(selector, count);
            }
        }
        
        state.issues.delete(id);
        
        emitEvent('annotation.removed', { id, totalCount: state.issues.size });
        
        return true;
    }

    function clearAll() {
        state.issues.forEach((entry, id) => {
            entry.badge.remove();
            entry.popover.remove();
        });
        
        state.issues.clear();
        state.elementBadgeCounts.clear();
        state.badgeCounter = 0;
        
        hideHighlight();
        
        emitEvent('annotations.cleared', { totalCount: 0 });
    }

    function setVisibility(visible) {
        state.visible = visible;
        
        state.issues.forEach((entry) => {
            if (visible) {
                entry.badge.classList.remove('annotations-hidden');
                entry.popover.classList.remove('annotations-hidden');
            } else {
                entry.badge.classList.add('annotations-hidden');
                entry.popover.classList.add('annotations-hidden');
            }
        });
        
        if (!visible) {
            hideHighlight();
        }
    }

    function repositionAll() {
        state.issues.forEach((entry) => {
            if (entry.targetElement) {
                const selector = entry.selector;
                let sameElementIndex = 0;
                
                // Find this badge's index among badges on same element
                state.issues.forEach((otherEntry) => {
                    if (otherEntry.selector === selector && 
                        otherEntry.issue.id !== entry.issue.id &&
                        Number(otherEntry.badge.dataset.badgeNumber) < Number(entry.badge.dataset.badgeNumber)) {
                        sameElementIndex++;
                    }
                });
                
                const position = positionBadge(
                    entry.targetElement, 
                    Number(entry.badge.dataset.badgeNumber),
                    sameElementIndex
                );
                entry.badge.style.left = `${position.left}px`;
                entry.badge.style.top = `${position.top}px`;
            }
        });
    }

    // =========================================================================
    // Event Emission
    // =========================================================================
    
    function emitEvent(type, payload) {
        const event = bus
            ? bus.emit(type, 'annotation-layer', payload)
            : {
                schemaVersion: '1.0',
                sessionId: 'standalone',
                seq: Date.now(),
                type: type,
                source: 'annotation-layer',
                timestamp: new Date().toISOString(),
                payload: payload
            };
        
        return event;
    }

    // =========================================================================
    // Canvas Bus Subscriptions
    // =========================================================================
    
    if (bus) {
        // Listen for visibility toggle from toolbar
        bus.subscribe('annotations.visibility_changed', (event) => {
            setVisibility(event.payload.visible);
        });
        
        // Listen for dismiss from toolbar
        bus.subscribe('toolbar.dismiss_requested', () => {
            clearAll();
            cleanup();
        });
        
        // Listen for issues from design-review
        bus.subscribe('review.issue_found', (event) => {
            addIssue(event.payload);
        });
        
        // Listen for review completion
        bus.subscribe('review.completed', (event) => {
            repositionAll();
        });
    }

    // =========================================================================
    // Window Events
    // =========================================================================
    
    let resizeTimeout;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(repositionAll, 100);
    });

    // Keyboard handler for Escape to close popovers
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            // Native popover API handles Escape automatically, but we ensure
            // focus returns to the badge (handled in toggle event)
        }
    });

    // =========================================================================
    // Cleanup
    // =========================================================================
    
    function cleanup() {
        window.__annotationLayerActive = false;
        layer.remove();
        styleSheet.remove();
        
        if (bus) {
            bus.state.activeTools.delete('annotation-layer');
        }
    }

    // =========================================================================
    // Expose Public API
    // =========================================================================
    
    window.__annotationLayer = {
        // Issue management
        addIssue,
        removeIssue,
        clearAll,
        
        // State queries
        getIssueCount: () => state.issues.size,
        getIssues: () => Array.from(state.issues.values()).map(e => e.issue),
        hasIssue: (id) => state.issues.has(id),
        
        // Visibility
        show: () => setVisibility(true),
        hide: () => setVisibility(false),
        isVisible: () => state.visible,
        
        // Positioning
        repositionAll,
        
        // Cleanup
        destroy: cleanup,
        
        // Direct access for debugging
        _state: state,
        _layer: layer,
    };

    // =========================================================================
    // Initialize
    // =========================================================================
    
    console.log('[AnnotationLayer] Initialized with session:', bus?.sessionId || 'standalone');
    
    emitEvent('annotation_layer.initialized', { timestamp: new Date().toISOString() });
})();
