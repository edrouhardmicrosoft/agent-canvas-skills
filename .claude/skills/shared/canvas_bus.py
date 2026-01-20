#!/usr/bin/env python3
"""
Shared Canvas Bus - Event bus infrastructure for skill integration.

Provides:
- Unified event schema with schemaVersion, sessionId, seq, type, source, timestamp, payload
- Shared event bus: window.__canvasBus with emit(), drain(), subscribe(), state, seq
- Standardized selector generation with confidence scoring
- Capture mode coordination for screenshot isolation

This module is imported by agent-eyes, agent-canvas, and canvas-edit.
"""

import json
from datetime import datetime
from typing import Optional


def get_timestamp() -> str:
    """Generate ISO 8601 timestamp."""
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def generate_session_id() -> str:
    """Generate a unique session ID."""
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")[:-3]
    return f"ses_{ts}"


# Schema version for all events
SCHEMA_VERSION = "1.0"


def create_event(
    event_type: str,
    source: str,
    payload: dict,
    session_id: Optional[str] = None,
    seq: Optional[int] = None,
) -> dict:
    """Create a standardized event object."""
    return {
        "schemaVersion": SCHEMA_VERSION,
        "sessionId": session_id or "unknown",
        "seq": seq or 0,
        "type": event_type,
        "source": source,
        "timestamp": get_timestamp(),
        "payload": payload,
    }


# JavaScript code for the shared event bus
# This is injected into pages and provides cross-skill coordination
CANVAS_BUS_JS = """
(() => {
    // Only initialize once
    if (window.__canvasBus) return window.__canvasBus;
    
    const SCHEMA_VERSION = '1.0';
    const sessionId = 'ses_' + Date.now().toString(36) + Math.random().toString(36).substr(2, 5);
    let seq = 0;
    
    // Subscribers map: eventType -> [callback, ...]
    const subscribers = new Map();
    
    // Transient event queue (drained by Python polling)
    let eventQueue = [];
    
    // Durable change log (append-only, persists until explicit reset)
    let changeLog = [];
    
    // Shared state
    const state = {
        selection: null,          // Current selected element info
        captureMode: false,       // When true, overlays should hide
        activeTools: new Set(),   // Which tools are currently active
    };
    
    /**
     * Standardized selector generation with priority-based strategy
     * Priority: #id > [data-testid] > [data-cy] > CSS path with nth-of-type
     */
    function generateSelector(el) {
        if (!el || el === document.body || el === document.documentElement) {
            return { selector: 'body', confidence: 'high', alternatives: [] };
        }
        
        const alternatives = [];
        let primary = null;
        let confidence = 'low';
        
        // Priority 1: ID (if unique)
        if (el.id && !el.id.startsWith('__')) {
            const idSelector = '#' + CSS.escape(el.id);
            const matches = document.querySelectorAll(idSelector);
            if (matches.length === 1) {
                primary = idSelector;
                confidence = 'high';
            } else {
                alternatives.push({ selector: idSelector, note: 'id not unique' });
            }
        }
        
        // Priority 2: data-testid or data-cy
        const testId = el.getAttribute('data-testid');
        const cyId = el.getAttribute('data-cy');
        
        if (testId) {
            const testIdSelector = `[data-testid="${CSS.escape(testId)}"]`;
            const matches = document.querySelectorAll(testIdSelector);
            if (matches.length === 1) {
                if (!primary) {
                    primary = testIdSelector;
                    confidence = 'high';
                } else {
                    alternatives.push({ selector: testIdSelector, note: 'data-testid' });
                }
            }
        }
        
        if (cyId) {
            const cySelector = `[data-cy="${CSS.escape(cyId)}"]`;
            const matches = document.querySelectorAll(cySelector);
            if (matches.length === 1) {
                if (!primary) {
                    primary = cySelector;
                    confidence = 'high';
                } else {
                    alternatives.push({ selector: cySelector, note: 'data-cy' });
                }
            }
        }
        
        // Priority 3: Class-based selector (if unique enough)
        if (!primary && el.className && typeof el.className === 'string') {
            const classes = el.className.trim().split(/\\s+/)
                .filter(c => c && !c.startsWith('__') && !c.startsWith('_'));
            if (classes.length > 0) {
                const classSelector = el.tagName.toLowerCase() + '.' + classes.map(c => CSS.escape(c)).join('.');
                const matches = document.querySelectorAll(classSelector);
                if (matches.length === 1) {
                    primary = classSelector;
                    confidence = 'medium';
                } else if (matches.length <= 5) {
                    alternatives.push({ selector: classSelector, note: `${matches.length} matches` });
                }
            }
        }
        
        // Priority 4: CSS path with :nth-of-type for uniqueness
        if (!primary) {
            const path = [];
            let current = el;
            let depth = 0;
            const maxDepth = 5;
            
            while (current && current !== document.body && depth < maxDepth) {
                let segment = current.tagName.toLowerCase();
                
                // Add nth-of-type if there are siblings of the same type
                const parent = current.parentElement;
                if (parent) {
                    const siblings = Array.from(parent.children).filter(
                        c => c.tagName === current.tagName
                    );
                    if (siblings.length > 1) {
                        const index = siblings.indexOf(current) + 1;
                        segment += `:nth-of-type(${index})`;
                    }
                }
                
                path.unshift(segment);
                current = parent;
                depth++;
            }
            
            if (path.length > 0) {
                primary = path.join(' > ');
                confidence = 'medium';
                
                // Verify uniqueness
                try {
                    const matches = document.querySelectorAll(primary);
                    if (matches.length !== 1) {
                        confidence = 'low';
                    }
                } catch (e) {
                    confidence = 'low';
                }
            }
        }
        
        // Fallback: tag name only
        if (!primary) {
            primary = el.tagName.toLowerCase();
            confidence = 'low';
        }
        
        return {
            selector: primary,
            confidence: confidence,
            alternatives: alternatives.slice(0, 3)  // Max 3 alternatives
        };
    }
    
    /**
     * Get detailed element information
     */
    function getElementInfo(el) {
        if (!el) return null;
        
        const rect = el.getBoundingClientRect();
        const styles = window.getComputedStyle(el);
        const selectorInfo = generateSelector(el);
        
        return {
            tag: el.tagName.toLowerCase(),
            id: el.id || null,
            className: typeof el.className === 'string' ? el.className : null,
            selector: selectorInfo.selector,
            selectorConfidence: selectorInfo.confidence,
            selectorAlternatives: selectorInfo.alternatives,
            text: el.textContent?.trim().slice(0, 200) || null,
            boundingBox: {
                x: Math.round(rect.x),
                y: Math.round(rect.y),
                width: Math.round(rect.width),
                height: Math.round(rect.height)
            },
            attributes: {
                role: el.getAttribute('role'),
                ariaLabel: el.getAttribute('aria-label'),
                dataTestid: el.getAttribute('data-testid'),
                dataCy: el.getAttribute('data-cy'),
                href: el.getAttribute('href'),
                src: el.getAttribute('src')
            },
            styles: {
                display: styles.display,
                position: styles.position,
                backgroundColor: styles.backgroundColor,
                color: styles.color,
                fontSize: styles.fontSize,
                fontWeight: styles.fontWeight,
                padding: styles.padding,
                margin: styles.margin,
                borderRadius: styles.borderRadius
            }
        };
    }
    
    /**
     * Emit an event through the bus
     */
    function emit(type, source, payload) {
        seq++;
        const event = {
            schemaVersion: SCHEMA_VERSION,
            sessionId: sessionId,
            seq: seq,
            type: type,
            source: source,
            timestamp: new Date().toISOString(),
            payload: payload
        };
        
        // Add to transient queue (for Python polling)
        eventQueue.push(event);
        
        // Add to durable change log (for save_request aggregation)
        changeLog.push(event);
        
        // Notify subscribers
        const typeSubscribers = subscribers.get(type) || [];
        const wildcardSubscribers = subscribers.get('*') || [];
        
        [...typeSubscribers, ...wildcardSubscribers].forEach(callback => {
            try {
                callback(event);
            } catch (e) {
                console.error('[CanvasBus] Subscriber error:', e);
            }
        });
        
        return event;
    }
    
    /**
     * Subscribe to events
     * @param type Event type to subscribe to, or '*' for all events
     * @param callback Function to call when event occurs
     * @returns Unsubscribe function
     */
    function subscribe(type, callback) {
        if (!subscribers.has(type)) {
            subscribers.set(type, []);
        }
        subscribers.get(type).push(callback);
        
        // Return unsubscribe function
        return () => {
            const subs = subscribers.get(type);
            if (subs) {
                const idx = subs.indexOf(callback);
                if (idx !== -1) subs.splice(idx, 1);
            }
        };
    }
    
    /**
     * Drain the transient event queue (used by Python polling)
     * This clears the queue and returns all events
     */
    function drain() {
        const events = eventQueue;
        eventQueue = [];
        return events;
    }
    
    /**
     * Get durable change log (does NOT clear it)
     * Used for save_request to get ALL changes since session start
     */
    function getChangeLog() {
        return [...changeLog];
    }
    
    /**
     * Reset/clear the change log (call after successful save)
     */
    function resetChangeLog() {
        const oldLog = changeLog;
        changeLog = [];
        return oldLog;
    }
    
    /**
     * Set capture mode (overlays should hide when true)
     */
    function setCaptureMode(enabled) {
        state.captureMode = enabled;
        // Emit event so overlays can respond
        emit('capture_mode.changed', 'bus', { enabled: enabled });
    }
    
    /**
     * Update current selection state
     */
    function setSelection(elementInfo) {
        state.selection = elementInfo;
        emit('selection.changed', 'bus', { element: elementInfo });
    }
    
    // Create the bus object
    const bus = {
        // Core API
        emit: emit,
        subscribe: subscribe,
        drain: drain,
        
        // Change log API
        getChangeLog: getChangeLog,
        resetChangeLog: resetChangeLog,
        
        // State management
        state: state,
        setSelection: setSelection,
        setCaptureMode: setCaptureMode,
        
        // Utilities
        generateSelector: generateSelector,
        getElementInfo: getElementInfo,
        
        // Metadata
        sessionId: sessionId,
        getSeq: () => seq,
        SCHEMA_VERSION: SCHEMA_VERSION
    };
    
    window.__canvasBus = bus;
    
    console.log('[CanvasBus] Initialized with session:', sessionId);
    return bus;
})();
"""


def get_canvas_bus_js() -> str:
    """Return the canvas bus injection JavaScript."""
    return CANVAS_BUS_JS


def inject_canvas_bus(page) -> dict:
    """
    Inject the canvas bus into a Playwright page.
    Returns the session info.
    """
    page.evaluate(CANVAS_BUS_JS)
    return page.evaluate(
        "() => ({ sessionId: window.__canvasBus.sessionId, seq: window.__canvasBus.getSeq() })"
    )


def drain_bus_events(page) -> list:
    """Drain events from the canvas bus."""
    return page.evaluate("() => window.__canvasBus ? window.__canvasBus.drain() : []")


def get_bus_change_log(page) -> list:
    """Get the durable change log from the bus."""
    return page.evaluate(
        "() => window.__canvasBus ? window.__canvasBus.getChangeLog() : []"
    )


def reset_bus_change_log(page) -> list:
    """Reset and return the change log."""
    return page.evaluate(
        "() => window.__canvasBus ? window.__canvasBus.resetChangeLog() : []"
    )


def set_capture_mode(page, enabled: bool) -> None:
    """Set capture mode on the bus (hides overlays)."""
    page.evaluate(
        f"() => window.__canvasBus && window.__canvasBus.setCaptureMode({str(enabled).lower()})"
    )


def get_bus_state(page) -> dict:
    """Get the current bus state."""
    return page.evaluate("""
        () => window.__canvasBus ? {
            sessionId: window.__canvasBus.sessionId,
            seq: window.__canvasBus.getSeq(),
            selection: window.__canvasBus.state.selection,
            captureMode: window.__canvasBus.state.captureMode,
            activeTools: Array.from(window.__canvasBus.state.activeTools || [])
        } : null
    """)
