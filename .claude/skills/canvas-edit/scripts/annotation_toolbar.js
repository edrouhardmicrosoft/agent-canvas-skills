/**
 * Annotation Toolbar - Live Annotation Feedback Toolbar
 * 
 * A floating toolbar that displays agent findings (issues) directly on watched
 * webpages in real-time. Uses Shadow DOM to be invisible to agent-eyes screenshots.
 * 
 * Features:
 * - Shadow DOM encapsulation (invisible to agent-eyes)
 * - Fluent 2 inspired mono-tone dark grey palette
 * - Drag to reposition (mouse and touch)
 * - Issue count with severity badges
 * - Three states: Issues Found, All Clear, Scanning
 * - Visibility toggle, screenshot, orientation toggle, dismiss
 * - Canvas bus integration for cross-skill coordination
 * 
 * @version 1.0.0
 */
(() => {
    // Prevent double initialization
    if (window.__annotationToolbarActive) return;
    window.__annotationToolbarActive = true;

    // =========================================================================
    // Configuration & Constants
    // =========================================================================
    
    const CONFIG = {
        HOST_ID: '__annotation_toolbar_host',
        DEFAULT_POSITION: { top: 8, right: 8 },
        MARGIN: 8,
        HORIZONTAL_DIMENSIONS: { width: 400, height: 48 },
        VERTICAL_DIMENSIONS: { width: 64, height: 280 },
    };

    // Success messages for "All Clear" state (randomized)
    const SUCCESS_MESSAGES = [
        { message: "All looks good!", emoji: "✓" },
        { message: "Ship it!", emoji: "🚀" },
        { message: "Pixel perfect", emoji: "✨" },
        { message: "Zero issues found", emoji: "0️⃣" },
        { message: "Looking sharp!", emoji: "👌" }
    ];

    // =========================================================================
    // Canvas Bus Integration
    // =========================================================================
    
    const bus = window.__canvasBus;
    if (!bus) {
        console.warn('[AnnotationToolbar] Canvas bus not found, running in standalone mode');
    }

    // Register this tool with the bus
    if (bus) {
        bus.state.activeTools.add('annotation-toolbar');
    }

    // =========================================================================
    // State Management
    // =========================================================================
    
    const state = {
        issues: [],
        severityCounts: { blocking: 0, major: 0, minor: 0 },
        toolbarState: 'issues', // 'issues' | 'success' | 'scanning'
        orientation: 'horizontal', // 'horizontal' | 'vertical'
        annotationsVisible: true,
        position: { ...CONFIG.DEFAULT_POSITION },
        isDragging: false,
        dragOffset: { x: 0, y: 0 }
    };

    // =========================================================================
    // CSS Variables & Styles (Fluent 2 Inspired)
    // =========================================================================
    
    const CSS_VARIABLES = `
        /* Primary Surface (Mono-tone Dark Grey) */
        --toolbar-bg: #292929;
        --toolbar-border: #3d3d3d;
        --toolbar-elevated: #333333;
        
        /* Text */
        --text-primary: #e0e0e0;
        --text-secondary: #a0a0a0;
        --text-disabled: #666666;
        
        /* Severity Indicators (the ONLY colors) */
        --severity-error: #f85149;
        --severity-warning: #d29922;
        --severity-info: #58a6ff;
        --severity-success: #3fb950;
        
        /* Interaction States */
        --hover-bg: #3d3d3d;
        --active-bg: #454545;
        --focus-ring: #58a6ff;
        
        /* Motion Tokens (Fluent 2) */
        --duration-faster: 100ms;
        --duration-fast: 150ms;
        --duration-normal: 250ms;
        --duration-slow: 300ms;
        --ease-out: cubic-bezier(0.33, 0, 0.1, 1);
        --ease-in: cubic-bezier(0.9, 0, 0.67, 1);
        --ease-in-out: cubic-bezier(0.85, 0, 0.15, 1);
    `;

    const TOOLBAR_STYLES = `
        :host {
            ${CSS_VARIABLES}
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        .toolbar {
            position: fixed;
            background: var(--toolbar-bg);
            border: 1px solid var(--toolbar-border);
            border-radius: 8px;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(255, 255, 255, 0.05);
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            font-size: 13px;
            color: var(--text-primary);
            user-select: none;
            z-index: 2147483647;
            transition: 
                width var(--duration-normal) var(--ease-out),
                height var(--duration-normal) var(--ease-out),
                opacity var(--duration-fast) var(--ease-out);
        }

        .toolbar.horizontal {
            display: flex;
            flex-direction: row;
            align-items: center;
            gap: 4px;
            padding: 6px 8px;
            min-width: 200px;
            height: 48px;
        }

        .toolbar.vertical {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 4px;
            padding: 8px 6px;
            width: 64px;
            min-height: 200px;
        }

        .toolbar.correcting {
            transition: 
                top var(--duration-fast) var(--ease-out),
                left var(--duration-fast) var(--ease-out);
        }

        /* Drag Handle */
        .drag-handle {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 28px;
            height: 28px;
            cursor: grab;
            color: var(--text-secondary);
            font-size: 16px;
            border-radius: 4px;
            transition: background var(--duration-faster) var(--ease-out);
            flex-shrink: 0;
        }

        .drag-handle:hover {
            background: var(--hover-bg);
        }

        .drag-handle:active {
            cursor: grabbing;
            background: var(--active-bg);
        }

        /* Divider */
        .divider {
            width: 1px;
            height: 24px;
            background: var(--toolbar-border);
            flex-shrink: 0;
        }

        .toolbar.vertical .divider {
            width: 32px;
            height: 1px;
        }

        /* Status Section */
        .status-section {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 0 4px;
        }

        .toolbar.vertical .status-section {
            flex-direction: column;
            padding: 4px 0;
        }

        .issue-count {
            font-weight: 500;
            white-space: nowrap;
        }

        .issue-count.success {
            color: var(--severity-success);
        }

        .issue-count.scanning {
            color: var(--text-secondary);
        }

        /* Severity Badges */
        .severity-badges {
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .toolbar.vertical .severity-badges {
            flex-direction: column;
            gap: 4px;
        }

        .severity-badge {
            display: flex;
            align-items: center;
            gap: 3px;
            font-size: 12px;
            font-weight: 500;
        }

        .severity-badge .dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }

        .severity-badge.blocking .dot { background: var(--severity-error); }
        .severity-badge.major .dot { background: var(--severity-warning); }
        .severity-badge.minor .dot { background: var(--severity-info); }

        .severity-badge .count {
            min-width: 12px;
            text-align: center;
        }

        /* Buttons */
        .btn {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 32px;
            height: 32px;
            border: none;
            border-radius: 6px;
            background: transparent;
            color: var(--text-primary);
            cursor: pointer;
            font-size: 16px;
            transition: 
                background var(--duration-faster) var(--ease-out),
                color var(--duration-faster) var(--ease-out);
            flex-shrink: 0;
        }

        .btn:hover {
            background: var(--hover-bg);
        }

        .btn:active {
            background: var(--active-bg);
        }

        .btn:focus-visible {
            outline: 2px solid var(--focus-ring);
            outline-offset: 2px;
        }

        .btn[aria-pressed="true"] {
            background: var(--hover-bg);
            color: var(--severity-info);
        }

        .btn[aria-pressed="false"] {
            color: var(--text-secondary);
        }

        .btn.dismiss {
            color: var(--text-secondary);
        }

        .btn.dismiss:hover {
            color: var(--severity-error);
            background: rgba(248, 81, 73, 0.15);
        }

        /* Action Group */
        .action-group {
            display: flex;
            align-items: center;
            gap: 2px;
            margin-left: auto;
        }

        .toolbar.vertical .action-group {
            flex-direction: column;
            margin-left: 0;
            margin-top: auto;
        }

        /* Spinner Animation */
        @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }

        .spinner {
            animation: spin 1s linear infinite;
            display: inline-block;
        }

        /* Accessibility: Status region for screen readers */
        .sr-only {
            position: absolute;
            width: 1px;
            height: 1px;
            padding: 0;
            margin: -1px;
            overflow: hidden;
            clip: rect(0, 0, 0, 0);
            white-space: nowrap;
            border: 0;
        }
    `;

    // =========================================================================
    // Create Shadow DOM Host
    // =========================================================================
    
    const host = document.createElement('div');
    host.id = CONFIG.HOST_ID;
    host.setAttribute('data-agent-ignore', 'true'); // Signal to agent-eyes to ignore
    host.style.cssText = 'position: fixed; top: 0; left: 0; z-index: 2147483647; pointer-events: none;';
    document.body.appendChild(host);

    // Create closed Shadow DOM (invisible to external queries and screenshots)
    const shadow = host.attachShadow({ mode: 'closed' });

    // =========================================================================
    // Build Toolbar HTML
    // =========================================================================
    
    function buildToolbarHTML() {
        return `
            <style>${TOOLBAR_STYLES}</style>
            <div class="toolbar horizontal" role="toolbar" aria-label="Design Review Annotations">
                <!-- Drag Handle -->
                <div class="drag-handle" aria-label="Drag to reposition" tabindex="0">
                    ☰
                </div>
                
                <div class="divider"></div>
                
                <!-- Status Section -->
                <div class="status-section" aria-live="polite">
                    <span class="issue-count" id="issueCount">0 Issues</span>
                    <div class="severity-badges" id="severityBadges">
                        <span class="severity-badge blocking">
                            <span class="dot"></span>
                            <span class="count" id="blockingCount">0</span>
                        </span>
                        <span class="severity-badge major">
                            <span class="dot"></span>
                            <span class="count" id="majorCount">0</span>
                        </span>
                        <span class="severity-badge minor">
                            <span class="dot"></span>
                            <span class="count" id="minorCount">0</span>
                        </span>
                    </div>
                </div>
                
                <div class="divider"></div>
                
                <!-- Action Buttons -->
                <div class="action-group">
                    <button class="btn" id="visibilityBtn" 
                            aria-label="Toggle issue visibility" 
                            aria-pressed="true"
                            title="Toggle visibility">
                        👁
                    </button>
                    <button class="btn" id="screenshotBtn" 
                            aria-label="Capture screenshot"
                            title="Take screenshot">
                        📸
                    </button>
                    <button class="btn" id="orientationBtn" 
                            aria-label="Toggle orientation: currently horizontal"
                            title="Toggle orientation">
                        ↕
                    </button>
                    <button class="btn dismiss" id="dismissBtn" 
                            aria-label="Dismiss all annotations"
                            title="Dismiss">
                        ✕
                    </button>
                </div>
            </div>
            
            <!-- Screen reader announcements -->
            <div aria-live="polite" class="sr-only" id="announcements"></div>
        `;
    }

    shadow.innerHTML = buildToolbarHTML();

    // =========================================================================
    // Get DOM References
    // =========================================================================
    
    const toolbar = shadow.querySelector('.toolbar');
    const dragHandle = shadow.querySelector('.drag-handle');
    const issueCount = shadow.getElementById('issueCount');
    const severityBadges = shadow.getElementById('severityBadges');
    const blockingCount = shadow.getElementById('blockingCount');
    const majorCount = shadow.getElementById('majorCount');
    const minorCount = shadow.getElementById('minorCount');
    const visibilityBtn = shadow.getElementById('visibilityBtn');
    const screenshotBtn = shadow.getElementById('screenshotBtn');
    const orientationBtn = shadow.getElementById('orientationBtn');
    const dismissBtn = shadow.getElementById('dismissBtn');
    const announcements = shadow.getElementById('announcements');

    // =========================================================================
    // Position Management
    // =========================================================================
    
    function setInitialPosition() {
        const { right, top } = CONFIG.DEFAULT_POSITION;
        toolbar.style.top = `${top}px`;
        toolbar.style.right = `${right}px`;
        toolbar.style.left = 'auto';
        state.position = { top, right };
    }

    function correctToolbarPosition() {
        const rect = toolbar.getBoundingClientRect();
        const viewport = {
            width: window.innerWidth,
            height: window.innerHeight
        };
        const margin = CONFIG.MARGIN;
        let needsCorrection = false;

        // Calculate corrections
        let newLeft = parseFloat(toolbar.style.left) || (viewport.width - rect.width - margin);
        let newTop = parseFloat(toolbar.style.top) || margin;

        // Horizontal bounds
        if (rect.right > viewport.width - margin) {
            newLeft = viewport.width - rect.width - margin;
            needsCorrection = true;
        }
        if (rect.left < margin) {
            newLeft = margin;
            needsCorrection = true;
        }

        // Vertical bounds
        if (rect.bottom > viewport.height - margin) {
            newTop = viewport.height - rect.height - margin;
            needsCorrection = true;
        }
        if (rect.top < margin) {
            newTop = margin;
            needsCorrection = true;
        }

        if (needsCorrection) {
            toolbar.classList.add('correcting');
            toolbar.style.left = `${newLeft}px`;
            toolbar.style.top = `${newTop}px`;
            toolbar.style.right = 'auto';
            
            setTimeout(() => toolbar.classList.remove('correcting'), 150);
        }
    }

    // =========================================================================
    // Drag Functionality
    // =========================================================================
    
    function startDrag(clientX, clientY) {
        state.isDragging = true;
        const rect = toolbar.getBoundingClientRect();
        state.dragOffset = {
            x: clientX - rect.left,
            y: clientY - rect.top
        };
        toolbar.style.right = 'auto';
        dragHandle.style.cursor = 'grabbing';
    }

    function onDrag(clientX, clientY) {
        if (!state.isDragging) return;
        
        const newLeft = clientX - state.dragOffset.x;
        const newTop = clientY - state.dragOffset.y;
        
        toolbar.style.left = `${newLeft}px`;
        toolbar.style.top = `${newTop}px`;
        
        state.position = { left: newLeft, top: newTop };
    }

    function endDrag() {
        if (!state.isDragging) return;
        
        state.isDragging = false;
        dragHandle.style.cursor = 'grab';
        correctToolbarPosition();
    }

    // Mouse drag events
    dragHandle.addEventListener('mousedown', (e) => {
        e.preventDefault();
        startDrag(e.clientX, e.clientY);
    });

    document.addEventListener('mousemove', (e) => {
        onDrag(e.clientX, e.clientY);
    });

    document.addEventListener('mouseup', endDrag);

    // Touch drag events
    dragHandle.addEventListener('touchstart', (e) => {
        e.preventDefault();
        const touch = e.touches[0];
        startDrag(touch.clientX, touch.clientY);
    }, { passive: false });

    document.addEventListener('touchmove', (e) => {
        if (state.isDragging) {
            const touch = e.touches[0];
            onDrag(touch.clientX, touch.clientY);
        }
    }, { passive: true });

    document.addEventListener('touchend', endDrag);

    // Window resize - correct position
    window.addEventListener('resize', () => {
        correctToolbarPosition();
    });

    // =========================================================================
    // State Updates
    // =========================================================================
    
    function updateIssueCount() {
        const total = state.issues.length;
        
        if (state.toolbarState === 'scanning') {
            issueCount.innerHTML = '<span class="spinner">⟳</span> Analyzing...';
            issueCount.classList.remove('success');
            issueCount.classList.add('scanning');
            severityBadges.style.display = 'none';
        } else if (total === 0 && state.toolbarState === 'success') {
            const success = SUCCESS_MESSAGES[Math.floor(Math.random() * SUCCESS_MESSAGES.length)];
            issueCount.textContent = `${success.emoji} ${success.message}`;
            issueCount.classList.add('success');
            issueCount.classList.remove('scanning');
            severityBadges.style.display = 'none';
        } else {
            issueCount.textContent = `${total} Issue${total !== 1 ? 's' : ''}`;
            issueCount.classList.remove('success', 'scanning');
            severityBadges.style.display = 'flex';
            
            // Update severity counts
            blockingCount.textContent = state.severityCounts.blocking;
            majorCount.textContent = state.severityCounts.major;
            minorCount.textContent = state.severityCounts.minor;
        }
    }

    function setToolbarState(newState) {
        state.toolbarState = newState;
        updateIssueCount();
        
        // Announce state change for screen readers
        if (newState === 'scanning') {
            announce('Analyzing page for issues');
        } else if (newState === 'success') {
            announce('Review complete, no issues found');
        }
    }

    function announce(message) {
        announcements.textContent = message;
        setTimeout(() => announcements.textContent = '', 1000);
    }

    // =========================================================================
    // Button Event Handlers
    // =========================================================================
    
    // Visibility toggle
    visibilityBtn.addEventListener('click', () => {
        state.annotationsVisible = !state.annotationsVisible;
        visibilityBtn.setAttribute('aria-pressed', state.annotationsVisible.toString());
        visibilityBtn.textContent = state.annotationsVisible ? '👁' : '👁‍🗨';
        
        // Emit event for annotation layer
        emitEvent('annotations.visibility_changed', { visible: state.annotationsVisible });
        announce(state.annotationsVisible ? 'Annotations visible' : 'Annotations hidden');
    });

    // Screenshot button (placeholder - full implementation in Phase 4)
    screenshotBtn.addEventListener('click', () => {
        emitEvent('screenshot.requested', { issueCount: state.issues.length });
        announce('Screenshot requested');
    });

    // Orientation toggle (placeholder - full implementation in Phase 4)
    orientationBtn.addEventListener('click', () => {
        const newOrientation = state.orientation === 'horizontal' ? 'vertical' : 'horizontal';
        
        // Check if we can toggle without going off-screen
        const rect = toolbar.getBoundingClientRect();
        const newDimensions = newOrientation === 'vertical' 
            ? CONFIG.VERTICAL_DIMENSIONS 
            : CONFIG.HORIZONTAL_DIMENSIONS;
        
        const wouldOverflow = {
            right: rect.left + newDimensions.width > window.innerWidth - CONFIG.MARGIN,
            bottom: rect.top + newDimensions.height > window.innerHeight - CONFIG.MARGIN
        };

        // Pre-correct position if needed
        if (wouldOverflow.right || wouldOverflow.bottom) {
            const safeLeft = Math.min(rect.left, window.innerWidth - newDimensions.width - CONFIG.MARGIN);
            const safeTop = Math.min(rect.top, window.innerHeight - newDimensions.height - CONFIG.MARGIN);
            
            toolbar.classList.add('correcting');
            toolbar.style.left = `${Math.max(CONFIG.MARGIN, safeLeft)}px`;
            toolbar.style.top = `${Math.max(CONFIG.MARGIN, safeTop)}px`;
            toolbar.style.right = 'auto';
            
            setTimeout(() => {
                toolbar.classList.remove('correcting');
                performOrientationToggle(newOrientation);
            }, 150);
        } else {
            performOrientationToggle(newOrientation);
        }
    });

    function performOrientationToggle(newOrientation) {
        state.orientation = newOrientation;
        toolbar.classList.remove('horizontal', 'vertical');
        toolbar.classList.add(newOrientation);
        
        orientationBtn.textContent = newOrientation === 'horizontal' ? '↕' : '↔';
        orientationBtn.setAttribute('aria-label', 
            `Toggle orientation: currently ${newOrientation}`);
        
        emitEvent('toolbar.orientation_changed', { orientation: newOrientation });
        announce(`Toolbar orientation: ${newOrientation}`);
    }

    // Dismiss button
    dismissBtn.addEventListener('click', () => {
        emitEvent('toolbar.dismiss_requested', {});
        
        // Remove all annotations and toolbar
        state.issues = [];
        state.severityCounts = { blocking: 0, major: 0, minor: 0 };
        
        // Clean up
        host.remove();
        window.__annotationToolbarActive = false;
        
        // Notify bus if available
        if (bus) {
            bus.state.activeTools.delete('annotation-toolbar');
        }
    });

    // =========================================================================
    // Event Emission
    // =========================================================================
    
    function emitEvent(type, payload) {
        const event = bus
            ? bus.emit(type, 'annotation-toolbar', payload)
            : {
                schemaVersion: '1.0',
                sessionId: 'standalone',
                seq: Date.now(),
                type: type,
                source: 'annotation-toolbar',
                timestamp: new Date().toISOString(),
                payload: payload
            };
        
        return event;
    }

    // =========================================================================
    // Canvas Bus Integration
    // =========================================================================
    
    if (bus) {
        // Hide toolbar during capture mode (but keep annotations visible)
        bus.subscribe('capture_mode.changed', (event) => {
            toolbar.style.display = event.payload.enabled ? 'none' : 'flex';
        });

        // Listen for review events
        bus.subscribe('review.started', () => {
            setToolbarState('scanning');
        });

        bus.subscribe('review.issue_found', (event) => {
            const issue = event.payload;
            state.issues.push(issue);
            
            // Update severity counts
            const severity = issue.severity || 'minor';
            if (severity === 'blocking' || severity === 'error' || severity === 'critical') {
                state.severityCounts.blocking++;
            } else if (severity === 'major' || severity === 'warning') {
                state.severityCounts.major++;
            } else {
                state.severityCounts.minor++;
            }
            
            setToolbarState('issues');
            updateIssueCount();
        });

        bus.subscribe('review.completed', (event) => {
            if (state.issues.length === 0) {
                setToolbarState('success');
            } else {
                setToolbarState('issues');
            }
            updateIssueCount();
        });
    }

    // =========================================================================
    // Public API
    // =========================================================================
    
    window.__annotationToolbar = {
        // State queries
        getState: () => ({ ...state }),
        getIssueCount: () => state.issues.length,
        
        // State updates
        addIssue: (issue) => {
            state.issues.push(issue);
            const severity = issue.severity || 'minor';
            if (severity === 'blocking' || severity === 'error' || severity === 'critical') {
                state.severityCounts.blocking++;
            } else if (severity === 'major' || severity === 'warning') {
                state.severityCounts.major++;
            } else {
                state.severityCounts.minor++;
            }
            setToolbarState('issues');
            updateIssueCount();
            return state.issues.length;
        },
        
        clearIssues: () => {
            state.issues = [];
            state.severityCounts = { blocking: 0, major: 0, minor: 0 };
            updateIssueCount();
        },
        
        setScanning: () => setToolbarState('scanning'),
        setComplete: () => {
            if (state.issues.length === 0) {
                setToolbarState('success');
            } else {
                setToolbarState('issues');
            }
            updateIssueCount();
        },
        
        // Visibility
        show: () => { toolbar.style.display = 'flex'; },
        hide: () => { toolbar.style.display = 'none'; },
        toggleVisibility: () => visibilityBtn.click(),
        
        // Orientation
        setOrientation: (orientation) => {
            if (orientation !== state.orientation) {
                orientationBtn.click();
            }
        },
        
        // Cleanup
        dismiss: () => dismissBtn.click()
    };

    // =========================================================================
    // Initialize
    // =========================================================================
    
    setInitialPosition();
    updateIssueCount();
    
    console.log('[AnnotationToolbar] Initialized with session:', bus?.sessionId || 'standalone');
    
    // Emit initialization event
    emitEvent('toolbar.initialized', { 
        orientation: state.orientation,
        position: state.position
    });
})();
