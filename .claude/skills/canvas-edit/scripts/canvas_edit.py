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


def get_timestamp() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S-%f")[:-3] + "Z"


# The edit panel JS - uses Shadow DOM to hide from DOM snapshots
EDIT_PANEL_JS = """
(() => {
    if (window.__canvasEditActive) return;
    window.__canvasEditActive = true;
    window.__canvasEditEvents = [];
    window.__canvasEditSelectedElement = null;

    // Create host element with Shadow DOM (invisible to DOM queries)
    const host = document.createElement('div');
    host.id = '__canvas_edit_host';
    host.style.cssText = 'position: fixed; top: 0; left: 0; z-index: 2147483647; pointer-events: none;';
    document.body.appendChild(host);
    
    const shadow = host.attachShadow({ mode: 'closed' });
    
    // Inject styles into shadow DOM
    const styles = document.createElement('style');
    styles.textContent = `
        * { box-sizing: border-box; margin: 0; padding: 0; }
        
        .panel {
            position: fixed;
            top: 20px;
            right: 20px;
            width: 280px;
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
            max-height: 500px;
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
        }
        
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
        
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        .btn-primary:hover { opacity: 0.9; }
        
        .btn-secondary {
            background: #333;
            color: #ccc;
        }
        
        .btn-secondary:hover { background: #444; }
        
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
                <div class="section-title">Selected Element</div>
                <div class="selected-info" id="selectedInfo">
                    <div class="no-selection">Click an element to select</div>
                </div>
            </div>
            
            <div class="section" id="editControls" style="display: none;">
                <div class="section-title">Text Content</div>
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
    
    let originalStyles = {};
    let originalText = '';
    let currentChanges = {};
    let textChanges = {};
    let editModeActive = false;
    
    function getSelector(el) {
        if (el.id) return '#' + el.id;
        if (el.className && typeof el.className === 'string') {
            const classes = el.className.trim().split(/\\s+/).filter(c => c && !c.startsWith('__'));
            if (classes.length) return el.tagName.toLowerCase() + '.' + classes.join('.');
        }
        return el.tagName.toLowerCase();
    }
    
    function rgbToHex(rgb) {
        if (!rgb || rgb === 'transparent' || rgb === 'rgba(0, 0, 0, 0)') return '#ffffff';
        const match = rgb.match(/^rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)/);
        if (!match) return rgb.startsWith('#') ? rgb : '#ffffff';
        return '#' + [match[1], match[2], match[3]].map(x => {
            const hex = parseInt(x).toString(16);
            return hex.length === 1 ? '0' + hex : hex;
        }).join('');
    }
    
    function selectElement(el) {
        if (el.id && el.id.startsWith('__canvas')) return;
        
        window.__canvasEditSelectedElement = el;
        const selector = getSelector(el);
        const styles = window.getComputedStyle(el);
        
        // Store original styles
        originalStyles = {
            backgroundColor: styles.backgroundColor,
            color: styles.color,
            fontSize: styles.fontSize,
            fontWeight: styles.fontWeight,
            padding: styles.padding,
            borderRadius: styles.borderRadius
        };
        
        // Update panel
        selectedInfo.innerHTML = `<div style="color: #a0a0ff;">${selector}</div>`;
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
    }
    
    function applyChange(prop, value) {
        const el = window.__canvasEditSelectedElement;
        if (!el) return;
        
        el.style[prop] = value;
        currentChanges[prop] = value;
    }
    
    function logChange(prop, value) {
        const el = window.__canvasEditSelectedElement;
        if (!el) return;
        
        const event = {
            event: 'style_change',
            timestamp: new Date().toISOString(),
            selector: getSelector(el),
            property: prop,
            oldValue: originalStyles[prop] || 'unset',
            newValue: value
        };
        
        window.__canvasEditEvents.push(event);
        
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
        el.textContent = newText;
        
        // Track the text change
        const selector = getSelector(el);
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
            el.addEventListener('input', function onInput() {
                const newText = el.textContent || '';
                textContent.value = newText;
                
                const selector = getSelector(el);
                textChanges[selector] = {
                    selector: selector,
                    oldText: originalText,
                    newText: newText
                };
            });
            
            // Style to indicate edit mode
            el.style.outline = '2px dashed #667eea';
            el.style.outlineOffset = '2px';
        } else {
            el.contentEditable = 'false';
            el.style.outline = '';
            el.style.outlineOffset = '';
        }
    });
    
    // Save All to Code button
    shadow.getElementById('saveAllBtn').addEventListener('click', () => {
        const allChanges = {
            styles: [],
            texts: []
        };
        
        // Collect all logged style changes from history
        window.__canvasEditEvents.forEach(evt => {
            if (evt.event === 'style_change') {
                allChanges.styles.push({
                    selector: evt.selector,
                    property: evt.property,
                    oldValue: evt.oldValue,
                    newValue: evt.newValue
                });
            }
        });
        
        // Collect all text changes
        Object.values(textChanges).forEach(change => {
            if (change.oldText !== change.newText) {
                allChanges.texts.push(change);
            }
        });
        
        // Emit save request event
        const saveEvent = {
            event: 'save_request',
            timestamp: new Date().toISOString(),
            changes: allChanges,
            summary: {
                styleChanges: allChanges.styles.length,
                textChanges: allChanges.texts.length
            }
        };
        
        window.__canvasEditEvents.push(saveEvent);
        
        // Visual feedback
        const btn = shadow.getElementById('saveAllBtn');
        const originalText = btn.textContent;
        btn.textContent = 'Saved!';
        btn.style.background = '#34C759';
        setTimeout(() => {
            btn.textContent = originalText;
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
    
    console.log('[Canvas Edit] Panel loaded (Shadow DOM - invisible to screenshots)');
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

            # Inject edit panel
            page.evaluate(EDIT_PANEL_JS)

            # Emit session start
            start_event = {
                "event": "edit_session_started",
                "url": url,
                "timestamp": get_timestamp(),
            }
            print(json.dumps(start_event))
            sys.stdout.flush()

            # Poll for events until browser closes
            while True:
                try:
                    if page.is_closed():
                        break

                    # Drain event queue
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
                "event": "edit_session_ended",
                "timestamp": get_timestamp(),
                "total_changes": len(all_events),
            }
            print(json.dumps(end_event))
            sys.stdout.flush()

            result = {
                "ok": True,
                "url": url,
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
        print(EDIT_PANEL_JS)


if __name__ == "__main__":
    main()
