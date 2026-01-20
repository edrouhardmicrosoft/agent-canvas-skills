#!/usr/bin/env -S python3 -u
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "playwright",
# ]
# ///
"""
Canvas Edit - Floating DevTools-like panel for live UI editing.

Injects a draggable edit panel into web pages. Users can select elements
and modify styles visually. Changes are streamed as JSON events for the
AI agent to implement in code.

The panel uses Shadow DOM to be invisible to agent-eyes screenshots.

Features:
- Integrates with shared canvas bus for cross-skill coordination
- Subscribes to selection.changed events for auto-handoff
- Separate event queue (transient) and changeLog (durable)
- Undo/redo support for style and text changes
- Capture mode awareness (hides during screenshots)

Usage:
    uv run canvas_edit.py edit <url> [--output PATH]
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.sync_api import sync_playwright


# =============================================================================
# Shared module imports (with fallback for standalone operation)
# =============================================================================


def _setup_shared_imports():
    """Add shared module to path for imports."""
    shared_path = Path(__file__).parent.parent.parent / "shared"
    if shared_path.exists() and str(shared_path) not in sys.path:
        sys.path.insert(0, str(shared_path))


_setup_shared_imports()

try:
    from canvas_bus import (
        CANVAS_BUS_JS,
        get_bus_change_log,
        reset_bus_change_log,
        drain_bus_events,
    )

    HAS_CANVAS_BUS = True
except ImportError:
    HAS_CANVAS_BUS = False
    CANVAS_BUS_JS = ""


def get_timestamp() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S-%f")[:-3] + "Z"


# The edit panel JS - uses Shadow DOM to hide from DOM snapshots
# Updated with:
# - Canvas bus integration
# - Selection auto-handoff
# - Undo/redo support
# - Capture mode awareness
# - Separate eventQueue vs changeLog
EDIT_PANEL_JS = """
(() => {
    if (window.__canvasEditActive) return;
    window.__canvasEditActive = true;
    
    // Get canvas bus (must be initialized first)
    const bus = window.__canvasBus;
    if (!bus) {
        console.warn('[CanvasEdit] Canvas bus not found, running in standalone mode');
    }
    
    // Register this tool
    if (bus) {
        bus.state.activeTools.add('edit');
    }
    
    // Legacy event queue (TRANSIENT - drained by Python polling)
    // This is for backward compatibility
    window.__canvasEditEvents = [];
    
    // The bus handles the durable changeLog, but we also maintain local state
    window.__canvasEditSelectedElement = null;
    
    // Undo/redo stacks
    const undoStack = [];
    const redoStack = [];
    const MAX_UNDO_HISTORY = 50;

    // Create host element with Shadow DOM (invisible to DOM queries)
    const host = document.createElement('div');
    host.id = '__canvas_edit_host';
    host.style.cssText = 'position: fixed; top: 0; left: 0; z-index: 2147483647; pointer-events: none;';
    document.body.appendChild(host);
    
    const shadow = host.attachShadow({ mode: 'closed' });
    
    // Subscribe to capture mode changes (hide panel during screenshots)
    if (bus) {
        bus.subscribe('capture_mode.changed', (event) => {
            host.style.display = event.payload.enabled ? 'none' : 'block';
        });
    }
    
    // Inject styles into shadow DOM
    const styles = document.createElement('style');
    styles.textContent = `
        * { box-sizing: border-box; margin: 0; padding: 0; }
        
        .panel {
            position: fixed;
            top: 20px;
            right: 20px;
            width: 300px;
            background: #1a1a2e;
            border-radius: 12px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.4);
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            font-size: 12px;
            color: #e0e0e0;
            pointer-events: auto;
            user-select: none;
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 12px 16px;
            cursor: move;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .header h3 {
            font-size: 13px;
            font-weight: 600;
            color: white;
        }
        
        .header .badge {
            background: rgba(255,255,255,0.2);
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 10px;
            color: white;
        }
        
        .content {
            padding: 12px;
            max-height: 550px;
            overflow-y: auto;
        }
        
        .section {
            margin-bottom: 16px;
        }
        
        .section-title {
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #888;
            margin-bottom: 8px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .confidence-badge {
            font-size: 9px;
            padding: 2px 6px;
            border-radius: 4px;
            text-transform: uppercase;
        }
        
        .confidence-high { background: #34C759; color: white; }
        .confidence-medium { background: #FF9500; color: white; }
        .confidence-low { background: #FF3B30; color: white; }
        
        .selected-info {
            background: #252538;
            border-radius: 6px;
            padding: 8px 10px;
            font-family: 'SF Mono', Monaco, monospace;
            font-size: 11px;
            color: #a0a0ff;
            word-break: break-all;
        }
        
        .no-selection {
            color: #666;
            font-style: italic;
            text-align: center;
            padding: 20px;
        }
        
        .control-group {
            margin-bottom: 12px;
        }
        
        .control-label {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 4px;
        }
        
        .control-label span {
            color: #aaa;
        }
        
        .control-label .value {
            color: #fff;
            font-family: 'SF Mono', Monaco, monospace;
            font-size: 11px;
        }
        
        .color-row {
            display: flex;
            gap: 8px;
            align-items: center;
        }
        
        .color-input {
            width: 36px;
            height: 28px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            padding: 0;
            background: transparent;
        }
        
        .color-input::-webkit-color-swatch-wrapper { padding: 2px; }
        .color-input::-webkit-color-swatch { border-radius: 3px; border: none; }
        
        .text-input {
            flex: 1;
            background: #252538;
            border: 1px solid #333;
            border-radius: 4px;
            padding: 6px 8px;
            color: #fff;
            font-size: 11px;
            font-family: 'SF Mono', Monaco, monospace;
        }
        
        .text-input:focus {
            outline: none;
            border-color: #667eea;
        }
        
        .slider-row {
            display: flex;
            gap: 8px;
            align-items: center;
        }
        
        .slider {
            flex: 1;
            -webkit-appearance: none;
            height: 4px;
            background: #333;
            border-radius: 2px;
            outline: none;
        }
        
        .slider::-webkit-slider-thumb {
            -webkit-appearance: none;
            width: 14px;
            height: 14px;
            background: #667eea;
            border-radius: 50%;
            cursor: pointer;
        }
        
        .slider-value {
            width: 50px;
            text-align: right;
            color: #fff;
            font-family: 'SF Mono', Monaco, monospace;
            font-size: 11px;
        }
        
        .btn-row {
            display: flex;
            gap: 8px;
            margin-top: 12px;
        }
        
        .btn {
            flex: 1;
            padding: 8px 12px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 11px;
            font-weight: 500;
            transition: all 0.15s;
        }
        
        .btn-small {
            flex: none;
            padding: 6px 10px;
            font-size: 10px;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        .btn-primary:hover { opacity: 0.9; }
        .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
        
        .btn-secondary {
            background: #333;
            color: #ccc;
        }
        
        .btn-secondary:hover { background: #444; }
        .btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }
        
        .history {
            max-height: 120px;
            overflow-y: auto;
        }
        
        .history-item {
            background: #252538;
            border-radius: 4px;
            padding: 6px 8px;
            margin-bottom: 4px;
            font-size: 10px;
            display: flex;
            justify-content: space-between;
        }
        
        .history-item .prop { color: #a0a0ff; }
        .history-item .val { color: #7fff7f; }
        
        .text-edit-area {
            width: 100%;
            min-height: 60px;
            max-height: 120px;
            background: #252538;
            border: 1px solid #333;
            border-radius: 4px;
            padding: 8px;
            color: #fff;
            font-size: 12px;
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            resize: vertical;
            line-height: 1.4;
        }
        
        .text-edit-area:focus {
            outline: none;
            border-color: #667eea;
        }
        
        .edit-mode-toggle {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 8px;
        }
        
        .toggle-switch {
            position: relative;
            width: 36px;
            height: 20px;
            background: #333;
            border-radius: 10px;
            cursor: pointer;
            transition: background 0.2s;
        }
        
        .toggle-switch.active {
            background: #667eea;
        }
        
        .toggle-switch::after {
            content: '';
            position: absolute;
            top: 2px;
            left: 2px;
            width: 16px;
            height: 16px;
            background: white;
            border-radius: 50%;
            transition: transform 0.2s;
        }
        
        .toggle-switch.active::after {
            transform: translateX(16px);
        }
        
        .toggle-label {
            color: #aaa;
            font-size: 11px;
        }
        
        .btn-success {
            background: linear-gradient(135deg, #34C759 0%, #30B350 100%);
            color: white;
        }
        
        .btn-success:hover { opacity: 0.9; }
        
        .save-row {
            margin-top: 16px;
            padding-top: 12px;
            border-top: 1px solid #333;
        }
        
        .undo-redo-row {
            display: flex;
            gap: 4px;
            margin-left: auto;
        }
    `;
    shadow.appendChild(styles);
    
    // Create panel HTML
    const panel = document.createElement('div');
    panel.className = 'panel';
    panel.innerHTML = `
        <div class="header">
            <h3>Canvas Edit</h3>
            <span class="badge">Shadow DOM</span>
        </div>
        <div class="content">
            <div class="section">
                <div class="section-title">
                    <span>Selected Element</span>
                    <span class="confidence-badge confidence-low" id="confidenceBadge" style="display: none;">low</span>
                </div>
                <div class="selected-info" id="selectedInfo">
                    <div class="no-selection">Click an element to select</div>
                </div>
            </div>
            
            <div class="section" id="editControls" style="display: none;">
                <div class="section-title">
                    <span>Text Content</span>
                    <div class="undo-redo-row">
                        <button class="btn btn-secondary btn-small" id="undoBtn" disabled title="Undo (Ctrl+Z)">↩</button>
                        <button class="btn btn-secondary btn-small" id="redoBtn" disabled title="Redo (Ctrl+Y)">↪</button>
                    </div>
                </div>
                <div class="control-group">
                    <div class="edit-mode-toggle">
                        <div class="toggle-switch" id="editModeToggle"></div>
                        <span class="toggle-label">Edit text directly on page</span>
                    </div>
                    <textarea class="text-edit-area" id="textContent" placeholder="Select an element with text..."></textarea>
                </div>
                
                <div class="section-title" style="margin-top: 16px;">Colors</div>
                <div class="control-group">
                    <div class="control-label">
                        <span>Background</span>
                        <span class="value" id="bgValue">#ffffff</span>
                    </div>
                    <div class="color-row">
                        <input type="color" class="color-input" id="bgColor" value="#ffffff">
                        <input type="text" class="text-input" id="bgColorText" placeholder="#ffffff">
                    </div>
                </div>
                
                <div class="control-group">
                    <div class="control-label">
                        <span>Text Color</span>
                        <span class="value" id="textValue">#000000</span>
                    </div>
                    <div class="color-row">
                        <input type="color" class="color-input" id="textColor" value="#000000">
                        <input type="text" class="text-input" id="textColorText" placeholder="#000000">
                    </div>
                </div>
                
                <div class="section-title" style="margin-top: 16px;">Typography</div>
                <div class="control-group">
                    <div class="control-label">
                        <span>Font Size</span>
                        <span class="value" id="fontSizeValue">16px</span>
                    </div>
                    <div class="slider-row">
                        <input type="range" class="slider" id="fontSize" min="8" max="72" value="16">
                        <span class="slider-value" id="fontSizeDisplay">16px</span>
                    </div>
                </div>
                
                <div class="control-group">
                    <div class="control-label">
                        <span>Font Weight</span>
                        <span class="value" id="fontWeightValue">400</span>
                    </div>
                    <div class="slider-row">
                        <input type="range" class="slider" id="fontWeight" min="100" max="900" step="100" value="400">
                        <span class="slider-value" id="fontWeightDisplay">400</span>
                    </div>
                </div>
                
                <div class="section-title" style="margin-top: 16px;">Spacing</div>
                <div class="control-group">
                    <div class="control-label">
                        <span>Padding</span>
                        <span class="value" id="paddingValue">0px</span>
                    </div>
                    <div class="slider-row">
                        <input type="range" class="slider" id="padding" min="0" max="64" value="0">
                        <span class="slider-value" id="paddingDisplay">0px</span>
                    </div>
                </div>
                
                <div class="control-group">
                    <div class="control-label">
                        <span>Border Radius</span>
                        <span class="value" id="radiusValue">0px</span>
                    </div>
                    <div class="slider-row">
                        <input type="range" class="slider" id="borderRadius" min="0" max="50" value="0">
                        <span class="slider-value" id="radiusDisplay">0px</span>
                    </div>
                </div>
                
                <div class="btn-row">
                    <button class="btn btn-secondary" id="resetBtn">Reset</button>
                    <button class="btn btn-primary" id="applyBtn">Apply & Log</button>
                </div>
                
                <div class="btn-row save-row">
                    <button class="btn btn-success" id="saveAllBtn">Save All to Code</button>
                </div>
            </div>
            
            <div class="section">
                <div class="section-title">Change History</div>
                <div class="history" id="history">
                    <div class="no-selection" style="padding: 10px;">No changes yet</div>
                </div>
            </div>
        </div>
    `;
    shadow.appendChild(panel);
    
    // Make panel draggable
    const header = panel.querySelector('.header');
    let isDragging = false;
    let dragOffset = { x: 0, y: 0 };
    
    header.addEventListener('mousedown', (e) => {
        isDragging = true;
        dragOffset.x = e.clientX - panel.offsetLeft;
        dragOffset.y = e.clientY - panel.offsetTop;
    });
    
    document.addEventListener('mousemove', (e) => {
        if (!isDragging) return;
        panel.style.left = (e.clientX - dragOffset.x) + 'px';
        panel.style.top = (e.clientY - dragOffset.y) + 'px';
        panel.style.right = 'auto';
    });
    
    document.addEventListener('mouseup', () => isDragging = false);
    
    // Get panel elements
    const selectedInfo = shadow.getElementById('selectedInfo');
    const editControls = shadow.getElementById('editControls');
    const history = shadow.getElementById('history');
    const confidenceBadge = shadow.getElementById('confidenceBadge');
    
    const bgColor = shadow.getElementById('bgColor');
    const bgColorText = shadow.getElementById('bgColorText');
    const bgValue = shadow.getElementById('bgValue');
    const textColor = shadow.getElementById('textColor');
    const textColorText = shadow.getElementById('textColorText');
    const textValue = shadow.getElementById('textValue');
    const fontSize = shadow.getElementById('fontSize');
    const fontSizeDisplay = shadow.getElementById('fontSizeDisplay');
    const fontWeight = shadow.getElementById('fontWeight');
    const fontWeightDisplay = shadow.getElementById('fontWeightDisplay');
    const padding = shadow.getElementById('padding');
    const paddingDisplay = shadow.getElementById('paddingDisplay');
    const borderRadius = shadow.getElementById('borderRadius');
    const radiusDisplay = shadow.getElementById('radiusDisplay');
    const textContent = shadow.getElementById('textContent');
    const editModeToggle = shadow.getElementById('editModeToggle');
    const undoBtn = shadow.getElementById('undoBtn');
    const redoBtn = shadow.getElementById('redoBtn');
    
    let originalStyles = {};
    let originalText = '';
    let currentChanges = {};
    let textChanges = {};
    let editModeActive = false;
    let currentSelectorInfo = null;
    
    function rgbToHex(rgb) {
        if (!rgb || rgb === 'transparent' || rgb === 'rgba(0, 0, 0, 0)') return '#ffffff';
        const match = rgb.match(/^rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)/);
        if (!match) return rgb.startsWith('#') ? rgb : '#ffffff';
        return '#' + [match[1], match[2], match[3]].map(x => {
            const hex = parseInt(x).toString(16);
            return hex.length === 1 ? '0' + hex : hex;
        }).join('');
    }
    
    function updateUndoRedoButtons() {
        undoBtn.disabled = undoStack.length === 0;
        redoBtn.disabled = redoStack.length === 0;
    }
    
    function pushUndo(action) {
        undoStack.push(action);
        if (undoStack.length > MAX_UNDO_HISTORY) {
            undoStack.shift();
        }
        redoStack.length = 0;  // Clear redo on new action
        updateUndoRedoButtons();
    }
    
    function performUndo() {
        if (undoStack.length === 0) return;
        
        const action = undoStack.pop();
        redoStack.push(action);
        
        const el = window.__canvasEditSelectedElement;
        if (!el) return;
        
        // Restore previous value
        if (action.type === 'style') {
            el.style[action.property] = action.oldValue;
        } else if (action.type === 'text') {
            el.textContent = action.oldText;
            textContent.value = action.oldText;
        }
        
        // Emit undo event
        emitEvent('edit.undo', {
            action: action.type,
            property: action.property,
            selector: currentSelectorInfo?.selector
        });
        
        updateUndoRedoButtons();
    }
    
    function performRedo() {
        if (redoStack.length === 0) return;
        
        const action = redoStack.pop();
        undoStack.push(action);
        
        const el = window.__canvasEditSelectedElement;
        if (!el) return;
        
        // Apply new value
        if (action.type === 'style') {
            el.style[action.property] = action.newValue;
        } else if (action.type === 'text') {
            el.textContent = action.newText;
            textContent.value = action.newText;
        }
        
        // Emit redo event
        emitEvent('edit.redo', {
            action: action.type,
            property: action.property,
            selector: currentSelectorInfo?.selector
        });
        
        updateUndoRedoButtons();
    }
    
    // Keyboard shortcuts for undo/redo
    document.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) {
            e.preventDefault();
            performUndo();
        } else if ((e.ctrlKey || e.metaKey) && (e.key === 'y' || (e.key === 'z' && e.shiftKey))) {
            e.preventDefault();
            performRedo();
        }
    });
    
    undoBtn.addEventListener('click', performUndo);
    redoBtn.addEventListener('click', performRedo);
    
    /**
     * Emit an event through the bus (if available) and legacy queue
     */
    function emitEvent(type, payload) {
        const event = bus ? 
            bus.emit(type, 'edit', payload) :
            {
                schemaVersion: '1.0',
                sessionId: 'standalone',
                seq: Date.now(),
                type: type,
                source: 'edit',
                timestamp: new Date().toISOString(),
                payload: payload
            };
        
        // Also push to legacy queue for backward compatibility
        window.__canvasEditEvents.push(event);
        
        return event;
    }
    
    function selectElement(el, fromBus = false) {
        if (el.id && el.id.startsWith('__canvas')) return;
        
        window.__canvasEditSelectedElement = el;
        
        // Use bus selector generation if available
        currentSelectorInfo = bus ? 
            bus.generateSelector(el) : 
            { selector: el.id ? '#' + el.id : el.tagName.toLowerCase(), confidence: 'low', alternatives: [] };
        
        const styles = window.getComputedStyle(el);
        
        // Store original styles for undo
        originalStyles = {
            backgroundColor: styles.backgroundColor,
            color: styles.color,
            fontSize: styles.fontSize,
            fontWeight: styles.fontWeight,
            padding: styles.padding,
            borderRadius: styles.borderRadius
        };
        
        // Update panel UI
        selectedInfo.innerHTML = `<div style="color: #a0a0ff;">${currentSelectorInfo.selector}</div>`;
        
        // Show confidence badge
        confidenceBadge.style.display = 'inline-block';
        confidenceBadge.textContent = currentSelectorInfo.confidence;
        confidenceBadge.className = 'confidence-badge confidence-' + currentSelectorInfo.confidence;
        
        editControls.style.display = 'block';
        
        // Set current values
        const bgHex = rgbToHex(styles.backgroundColor);
        bgColor.value = bgHex;
        bgColorText.value = bgHex;
        bgValue.textContent = bgHex;
        
        const textHex = rgbToHex(styles.color);
        textColor.value = textHex;
        textColorText.value = textHex;
        textValue.textContent = textHex;
        
        const fs = parseInt(styles.fontSize) || 16;
        fontSize.value = fs;
        fontSizeDisplay.textContent = fs + 'px';
        
        const fw = parseInt(styles.fontWeight) || 400;
        fontWeight.value = fw;
        fontWeightDisplay.textContent = fw;
        
        const pd = parseInt(styles.padding) || 0;
        padding.value = pd;
        paddingDisplay.textContent = pd + 'px';
        
        const br = parseInt(styles.borderRadius) || 0;
        borderRadius.value = br;
        radiusDisplay.textContent = br + 'px';
        
        // Store and display text content
        originalText = el.textContent || '';
        textContent.value = originalText;
        
        // Disable edit mode when selecting new element
        if (editModeActive) {
            editModeActive = false;
            editModeToggle.classList.remove('active');
            el.contentEditable = 'false';
        }
        
        currentChanges = {};
        
        // Emit selection event (only if not already from bus to avoid loops)
        if (!fromBus) {
            emitEvent('edit.element_selected', {
                selector: currentSelectorInfo.selector,
                selectorConfidence: currentSelectorInfo.confidence,
                selectorAlternatives: currentSelectorInfo.alternatives
            });
        }
    }
    
    // Subscribe to selection.changed events from picker (auto-handoff)
    if (bus) {
        bus.subscribe('selection.changed', (event) => {
            // Auto-select the element when picker selects it
            if (event.source === 'picker' && event.payload?.element?.selector) {
                const selector = event.payload.element.selector;
                try {
                    const el = document.querySelector(selector);
                    if (el) {
                        selectElement(el, true);  // fromBus=true to avoid event loop
                    }
                } catch (e) {
                    console.warn('[CanvasEdit] Could not select element:', selector);
                }
            }
        });
    }
    
    function applyChange(prop, value, skipUndo = false) {
        const el = window.__canvasEditSelectedElement;
        if (!el) return;
        
        if (!skipUndo) {
            const oldValue = el.style[prop] || originalStyles[prop] || '';
            pushUndo({
                type: 'style',
                property: prop,
                oldValue: oldValue,
                newValue: value
            });
        }
        
        el.style[prop] = value;
        currentChanges[prop] = value;
    }
    
    function logChange(prop, value) {
        const el = window.__canvasEditSelectedElement;
        if (!el) return;
        
        emitEvent('style.changed', {
            selector: currentSelectorInfo?.selector,
            selectorConfidence: currentSelectorInfo?.confidence,
            property: prop,
            oldValue: originalStyles[prop] || 'unset',
            newValue: value
        });
        
        // Update history UI
        const item = document.createElement('div');
        item.className = 'history-item';
        item.innerHTML = `<span class="prop">${prop}</span><span class="val">${value}</span>`;
        
        if (history.querySelector('.no-selection')) {
            history.innerHTML = '';
        }
        history.insertBefore(item, history.firstChild);
    }
    
    // Event listeners for controls
    bgColor.addEventListener('input', (e) => {
        bgColorText.value = e.target.value;
        bgValue.textContent = e.target.value;
        applyChange('backgroundColor', e.target.value);
    });
    
    bgColorText.addEventListener('change', (e) => {
        bgColor.value = e.target.value;
        bgValue.textContent = e.target.value;
        applyChange('backgroundColor', e.target.value);
    });
    
    textColor.addEventListener('input', (e) => {
        textColorText.value = e.target.value;
        textValue.textContent = e.target.value;
        applyChange('color', e.target.value);
    });
    
    textColorText.addEventListener('change', (e) => {
        textColor.value = e.target.value;
        textValue.textContent = e.target.value;
        applyChange('color', e.target.value);
    });
    
    fontSize.addEventListener('input', (e) => {
        const val = e.target.value + 'px';
        fontSizeDisplay.textContent = val;
        applyChange('fontSize', val);
    });
    
    fontWeight.addEventListener('input', (e) => {
        fontWeightDisplay.textContent = e.target.value;
        applyChange('fontWeight', e.target.value);
    });
    
    padding.addEventListener('input', (e) => {
        const val = e.target.value + 'px';
        paddingDisplay.textContent = val;
        applyChange('padding', val);
    });
    
    borderRadius.addEventListener('input', (e) => {
        const val = e.target.value + 'px';
        radiusDisplay.textContent = val;
        applyChange('borderRadius', val);
    });
    
    // Reset button
    shadow.getElementById('resetBtn').addEventListener('click', () => {
        const el = window.__canvasEditSelectedElement;
        if (!el) return;
        
        Object.keys(originalStyles).forEach(prop => {
            el.style[prop] = '';
        });
        
        selectElement(el);
        currentChanges = {};
        
        emitEvent('edit.reset', {
            selector: currentSelectorInfo?.selector
        });
    });
    
    // Apply & Log button
    shadow.getElementById('applyBtn').addEventListener('click', () => {
        Object.keys(currentChanges).forEach(prop => {
            logChange(prop, currentChanges[prop]);
        });
        currentChanges = {};
    });
    
    // Text content change from textarea
    textContent.addEventListener('input', (e) => {
        const el = window.__canvasEditSelectedElement;
        if (!el) return;
        
        const newText = e.target.value;
        const oldText = el.textContent;
        
        pushUndo({
            type: 'text',
            oldText: oldText,
            newText: newText
        });
        
        el.textContent = newText;
        
        // Track the text change
        const selector = currentSelectorInfo?.selector;
        textChanges[selector] = {
            selector: selector,
            oldText: originalText,
            newText: newText
        };
    });
    
    // Edit mode toggle - enables contenteditable on the page
    editModeToggle.addEventListener('click', () => {
        const el = window.__canvasEditSelectedElement;
        if (!el) return;
        
        editModeActive = !editModeActive;
        editModeToggle.classList.toggle('active', editModeActive);
        
        if (editModeActive) {
            el.contentEditable = 'true';
            el.focus();
            
            // Listen for changes directly on the element
            const onInput = () => {
                const newText = el.textContent || '';
                textContent.value = newText;
                
                const selector = currentSelectorInfo?.selector;
                textChanges[selector] = {
                    selector: selector,
                    oldText: originalText,
                    newText: newText
                };
            };
            
            el.addEventListener('input', onInput);
            el._canvasEditInputHandler = onInput;
            
            // Style to indicate edit mode
            el.style.outline = '2px dashed #667eea';
            el.style.outlineOffset = '2px';
        } else {
            el.contentEditable = 'false';
            el.style.outline = '';
            el.style.outlineOffset = '';
            
            if (el._canvasEditInputHandler) {
                el.removeEventListener('input', el._canvasEditInputHandler);
                delete el._canvasEditInputHandler;
            }
        }
    });
    
    // Save All to Code button - reads from durable changeLog
    shadow.getElementById('saveAllBtn').addEventListener('click', () => {
        const allChanges = {
            styles: [],
            texts: []
        };
        
        // Get ALL changes from the bus changeLog (durable, not drained)
        const changeLog = bus ? bus.getChangeLog() : [];
        
        // Collect style changes from changeLog
        changeLog.forEach(evt => {
            if (evt.type === 'style.changed') {
                allChanges.styles.push({
                    selector: evt.payload.selector,
                    selectorConfidence: evt.payload.selectorConfidence,
                    property: evt.payload.property,
                    oldValue: evt.payload.oldValue,
                    newValue: evt.payload.newValue
                });
            }
        });
        
        // Also include any pending changes not yet logged
        if (currentSelectorInfo) {
            Object.keys(currentChanges).forEach(prop => {
                allChanges.styles.push({
                    selector: currentSelectorInfo.selector,
                    selectorConfidence: currentSelectorInfo.confidence,
                    property: prop,
                    oldValue: originalStyles[prop] || 'unset',
                    newValue: currentChanges[prop]
                });
            });
        }
        
        // Collect all text changes
        Object.values(textChanges).forEach(change => {
            if (change.oldText !== change.newText) {
                allChanges.texts.push(change);
            }
        });
        
        // Emit save request event
        emitEvent('save_request', {
            changes: allChanges,
            summary: {
                styleChanges: allChanges.styles.length,
                textChanges: allChanges.texts.length
            }
        });
        
        // Visual feedback
        const btn = shadow.getElementById('saveAllBtn');
        const originalBtnText = btn.textContent;
        btn.textContent = 'Saved!';
        btn.style.background = '#34C759';
        setTimeout(() => {
            btn.textContent = originalBtnText;
            btn.style.background = '';
        }, 1500);
        
        // Add to history
        const item = document.createElement('div');
        item.className = 'history-item';
        item.innerHTML = '<span class="prop">SAVE</span><span class="val">' + 
            allChanges.styles.length + ' styles, ' + allChanges.texts.length + ' texts</span>';
        
        if (history.querySelector('.no-selection')) {
            history.innerHTML = '';
        }
        history.insertBefore(item, history.firstChild);
    });
    
    // Element selection via click (with Ctrl/Cmd key to avoid conflicts)
    document.addEventListener('click', (e) => {
        if (e.target.id && e.target.id.startsWith('__canvas')) return;
        if (host.contains(e.target)) return;
        
        // Select element on regular click if canvas picker is active
        if (window.__agentCanvasActive) {
            selectElement(e.target);
        }
    }, true);
    
    console.log('[CanvasEdit] Panel loaded with session:', bus?.sessionId || 'standalone');
})();
"""


def run_edit_session(
    url: str,
    output_path: Optional[str] = None,
) -> dict:
    """Launch browser with edit panel, stream edit events until window closes."""

    all_events = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        try:
            page.goto(url, wait_until="networkidle", timeout=30000)

            # Inject shared canvas bus FIRST
            session_info = {"sessionId": "standalone", "seq": 0}
            if HAS_CANVAS_BUS:
                page.evaluate(CANVAS_BUS_JS)
                session_info = page.evaluate(
                    "() => ({ sessionId: window.__canvasBus.sessionId, seq: window.__canvasBus.getSeq() })"
                )

            # Inject edit panel
            page.evaluate(EDIT_PANEL_JS)

            # Emit session start
            start_event = {
                "schemaVersion": "1.0",
                "sessionId": session_info.get("sessionId", "standalone"),
                "seq": 0,
                "type": "session.started",
                "source": "edit",
                "timestamp": get_timestamp(),
                "payload": {
                    "url": url,
                },
            }
            print(json.dumps(start_event))
            sys.stdout.flush()

            # Poll for events until browser closes
            while True:
                try:
                    if page.is_closed():
                        break

                    # Drain events from bus (preferred) or legacy queue
                    if HAS_CANVAS_BUS:
                        events = drain_bus_events(page)
                    else:
                        events = page.evaluate("""
                            () => {
                                const events = window.__canvasEditEvents || [];
                                window.__canvasEditEvents = [];
                                return events;
                            }
                        """)

                    for event in events:
                        all_events.append(event)
                        print(json.dumps(event))
                        sys.stdout.flush()

                    time.sleep(0.1)

                except Exception:
                    break

            # Emit session end
            end_event = {
                "schemaVersion": "1.0",
                "sessionId": session_info.get("sessionId", "standalone"),
                "seq": len(all_events) + 1,
                "type": "session.ended",
                "source": "edit",
                "timestamp": get_timestamp(),
                "payload": {
                    "total_changes": len(all_events),
                },
            }
            print(json.dumps(end_event))
            sys.stdout.flush()

            result = {
                "ok": True,
                "url": url,
                "sessionId": session_info.get("sessionId"),
                "changes": all_events,
                "total": len(all_events),
            }

            if output_path:
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                Path(output_path).write_text(json.dumps(result, indent=2))

            return result

        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            browser.close()


def get_panel_js() -> str:
    """Return the panel injection JS for use by other skills."""
    # Return both bus and panel JS together for proper initialization
    if HAS_CANVAS_BUS:
        return CANVAS_BUS_JS + "\n" + EDIT_PANEL_JS
    return EDIT_PANEL_JS


def main():
    parser = argparse.ArgumentParser(
        description="Canvas Edit - Floating DevTools panel for live UI editing",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Edit command
    edit_parser = subparsers.add_parser("edit", help="Open edit panel")
    edit_parser.add_argument("url", help="URL to edit")
    edit_parser.add_argument("--output", "-o", help="Save changes to file")

    # Get JS command (for integration)
    subparsers.add_parser("get-js", help="Output panel injection JS")

    args = parser.parse_args()

    if args.command == "edit":
        result = run_edit_session(args.url, output_path=args.output)
        sys.exit(0 if result.get("ok") else 1)

    elif args.command == "get-js":
        print(get_panel_js())


if __name__ == "__main__":
    main()
