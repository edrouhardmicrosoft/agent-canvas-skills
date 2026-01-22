/**
 * Design Review Overlay - Interactive browser overlay for spec-driven design review.
 * 
 * Features:
 * - Purple/violet theme (distinct from edit mode's blue)
 * - Compliance indicators on hover (✅ Pass / ⚠️ Warning / ❌ Fail)
 * - Click to show full compliance panel
 * - Navigation: Next Issue, keyboard shortcuts (N/A/Esc)
 * - Integrates with canvas bus for coordination
 * 
 * Injected by design_review.py interactive mode.
 */
(() => {
    if (window.__designReviewActive) return;
    window.__designReviewActive = true;

    // Get or create canvas bus
    const bus = window.__canvasBus;
    if (bus) {
        bus.state.activeTools.add('design-review');
    }

    // Review state
    const reviewState = {
        spec: null,              // Loaded spec checks
        issues: [],              // All detected issues
        currentIssueIndex: -1,   // For navigation
        hoveredElement: null,
        selectedElement: null,
        reviewedElements: new Set(),  // Elements added to review
        elementIssueCache: new Map(), // Cache of element -> issues
    };

    // Expose for Python access
    window.__designReviewState = reviewState;
    window.__designReviewEvents = [];

    // Color palette - Purple/Violet theme
    const COLORS = {
        primary: '#8B5CF6',        // Violet-500
        primaryHover: '#7C3AED',   // Violet-600
        primaryLight: 'rgba(139, 92, 246, 0.1)',
        pass: '#22C55E',           // Green-500
        passLight: 'rgba(34, 197, 94, 0.1)',
        warning: '#F59E0B',        // Amber-500
        warningLight: 'rgba(245, 158, 11, 0.1)',
        fail: '#EF4444',           // Red-500
        failLight: 'rgba(239, 68, 68, 0.1)',
        neutral: '#6B7280',        // Gray-500
        dark: '#1F2937',           // Gray-800
        white: '#FFFFFF',
        overlay: 'rgba(31, 41, 55, 0.95)',
    };

    // Create Shadow DOM host
    const host = document.createElement('div');
    host.id = '__design_review_host';
    host.style.cssText = 'position: fixed; top: 0; left: 0; z-index: 2147483647; pointer-events: none;';
    document.body.appendChild(host);
    const shadow = host.attachShadow({ mode: 'closed' });

    // Inject styles
    const styles = document.createElement('style');
    styles.textContent = `
        * { box-sizing: border-box; margin: 0; padding: 0; }

        .review-overlay {
            position: fixed;
            pointer-events: none;
            border: 2px solid ${COLORS.primary};
            background: ${COLORS.primaryLight};
            z-index: 999999;
            transition: all 0.1s ease-out;
            display: none;
        }

        .review-label {
            position: fixed;
            background: ${COLORS.primary};
            color: white;
            padding: 6px 12px;
            font-size: 12px;
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            border-radius: 6px;
            z-index: 1000000;
            pointer-events: none;
            display: none;
            max-width: 350px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        }

        .compliance-card {
            position: fixed;
            background: ${COLORS.overlay};
            color: white;
            padding: 12px 16px;
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            font-size: 12px;
            border-radius: 8px;
            z-index: 1000001;
            pointer-events: none;
            display: none;
            max-width: 320px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
        }

        .compliance-card-header {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 8px;
            font-weight: 600;
            font-size: 13px;
        }

        .compliance-status {
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 500;
        }

        .compliance-status.pass {
            background: ${COLORS.pass};
        }

        .compliance-status.warning {
            background: ${COLORS.warning};
            color: ${COLORS.dark};
        }

        .compliance-status.fail {
            background: ${COLORS.fail};
        }

        .compliance-rules {
            display: flex;
            flex-direction: column;
            gap: 6px;
        }

        .compliance-rule {
            display: flex;
            align-items: flex-start;
            gap: 8px;
            padding: 6px 8px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 4px;
            font-size: 11px;
        }

        .rule-status-icon {
            flex-shrink: 0;
            font-size: 14px;
        }

        .rule-name {
            color: #A78BFA;
            font-weight: 500;
        }

        .rule-severity {
            margin-left: auto;
            font-size: 10px;
            padding: 1px 6px;
            border-radius: 3px;
            text-transform: uppercase;
        }

        .rule-severity.blocking { background: ${COLORS.fail}; }
        .rule-severity.major { background: ${COLORS.warning}; color: ${COLORS.dark}; }
        .rule-severity.minor { background: ${COLORS.neutral}; }

        /* Instructions bar */
        .instructions-bar {
            position: fixed;
            top: 12px;
            left: 50%;
            transform: translateX(-50%);
            background: ${COLORS.overlay};
            color: white;
            padding: 10px 20px;
            font-size: 13px;
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            border-radius: 8px;
            z-index: 1000002;
            pointer-events: auto;
            display: flex;
            align-items: center;
            gap: 16px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
        }

        .instructions-bar kbd {
            background: rgba(255, 255, 255, 0.1);
            padding: 2px 6px;
            border-radius: 4px;
            font-family: monospace;
            font-size: 11px;
        }

        /* Issue counter badge */
        .issue-counter {
            position: fixed;
            top: 12px;
            right: 12px;
            background: ${COLORS.primary};
            color: white;
            padding: 10px 16px;
            font-size: 13px;
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            border-radius: 8px;
            z-index: 1000002;
            pointer-events: auto;
            display: flex;
            align-items: center;
            gap: 12px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
        }

        .issue-count-badge {
            background: rgba(255, 255, 255, 0.2);
            padding: 4px 10px;
            border-radius: 12px;
            font-weight: 600;
        }

        .nav-btn {
            background: rgba(255, 255, 255, 0.15);
            border: none;
            color: white;
            padding: 6px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
            transition: background 0.15s;
        }

        .nav-btn:hover {
            background: rgba(255, 255, 255, 0.25);
        }

        .nav-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }

        /* Full compliance panel (on click) */
        .compliance-panel {
            position: fixed;
            top: 70px;
            right: 12px;
            width: 360px;
            max-height: calc(100vh - 100px);
            background: ${COLORS.overlay};
            color: white;
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            border-radius: 12px;
            z-index: 1000003;
            pointer-events: auto;
            box-shadow: 0 12px 40px rgba(0, 0, 0, 0.4);
            display: none;
            overflow: hidden;
        }

        .panel-header {
            background: linear-gradient(135deg, ${COLORS.primary} 0%, #6D28D9 100%);
            padding: 16px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .panel-header h3 {
            font-size: 14px;
            font-weight: 600;
        }

        .panel-close {
            background: rgba(255, 255, 255, 0.2);
            border: none;
            color: white;
            width: 28px;
            height: 28px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 16px;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .panel-close:hover {
            background: rgba(255, 255, 255, 0.3);
        }

        .panel-content {
            padding: 16px;
            max-height: calc(100vh - 200px);
            overflow-y: auto;
        }

        .selected-element-info {
            background: rgba(255, 255, 255, 0.05);
            padding: 10px 12px;
            border-radius: 6px;
            margin-bottom: 16px;
            font-family: 'SF Mono', Monaco, monospace;
            font-size: 11px;
            color: #A78BFA;
            word-break: break-all;
        }

        .issue-list {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }

        .issue-item {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 8px;
            padding: 12px;
            border-left: 3px solid ${COLORS.neutral};
        }

        .issue-item.blocking { border-left-color: ${COLORS.fail}; }
        .issue-item.major { border-left-color: ${COLORS.warning}; }
        .issue-item.minor { border-left-color: ${COLORS.neutral}; }

        .issue-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 8px;
        }

        .issue-check-id {
            font-weight: 600;
            font-size: 12px;
            color: #A78BFA;
        }

        .issue-description {
            font-size: 12px;
            line-height: 1.5;
            color: #D1D5DB;
        }

        .issue-recommendation {
            margin-top: 8px;
            padding: 8px;
            background: rgba(139, 92, 246, 0.1);
            border-radius: 4px;
            font-size: 11px;
            color: #C4B5FD;
        }

        .panel-footer {
            padding: 12px 16px;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
            display: flex;
            gap: 8px;
        }

        .add-to-review-btn {
            flex: 1;
            background: linear-gradient(135deg, ${COLORS.pass} 0%, #16A34A 100%);
            border: none;
            color: white;
            padding: 10px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 12px;
            font-weight: 500;
            transition: opacity 0.15s;
        }

        .add-to-review-btn:hover {
            opacity: 0.9;
        }

        .add-to-review-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }

        .add-to-review-btn.added {
            background: ${COLORS.neutral};
        }

        /* Review summary panel */
        .review-summary {
            position: fixed;
            bottom: 12px;
            right: 12px;
            background: ${COLORS.overlay};
            padding: 12px 16px;
            border-radius: 8px;
            z-index: 1000002;
            pointer-events: auto;
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            font-size: 12px;
            min-width: 200px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
        }

        .review-summary-header {
            color: white;
            font-weight: 600;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .review-summary-stats {
            display: flex;
            gap: 12px;
            color: #D1D5DB;
        }

        .stat-item {
            display: flex;
            align-items: center;
            gap: 4px;
        }

        .stat-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }

        .stat-dot.blocking { background: ${COLORS.fail}; }
        .stat-dot.major { background: ${COLORS.warning}; }
        .stat-dot.minor { background: ${COLORS.neutral}; }
    `;
    shadow.appendChild(styles);

    // Create overlay element (for hover highlight)
    const overlay = document.createElement('div');
    overlay.className = 'review-overlay';
    shadow.appendChild(overlay);

    // Create label for selector display
    const label = document.createElement('div');
    label.className = 'review-label';
    shadow.appendChild(label);

    // Create compliance card (mini hover card)
    const complianceCard = document.createElement('div');
    complianceCard.className = 'compliance-card';
    shadow.appendChild(complianceCard);

    // Create instructions bar
    const instructionsBar = document.createElement('div');
    instructionsBar.className = 'instructions-bar';
    instructionsBar.innerHTML = `
        <span>Design Review Mode</span>
        <span><kbd>N</kbd> Next Issue</span>
        <span><kbd>A</kbd> Add to Review</span>
        <span><kbd>Esc</kbd> Close Panel</span>
    `;
    shadow.appendChild(instructionsBar);

    // Create issue counter badge
    const issueCounter = document.createElement('div');
    issueCounter.className = 'issue-counter';
    issueCounter.innerHTML = `
        <span>Issues:</span>
        <span class="issue-count-badge">0</span>
        <button class="nav-btn" id="prevIssueBtn" disabled>← Prev</button>
        <button class="nav-btn" id="nextIssueBtn" disabled>Next →</button>
    `;
    shadow.appendChild(issueCounter);

    // Create full compliance panel (shown on click)
    const compliancePanel = document.createElement('div');
    compliancePanel.className = 'compliance-panel';
    compliancePanel.innerHTML = `
        <div class="panel-header">
            <h3>Element Compliance</h3>
            <button class="panel-close" id="closePanelBtn">×</button>
        </div>
        <div class="panel-content">
            <div class="selected-element-info" id="selectedElementInfo">No element selected</div>
            <div class="issue-list" id="issueList"></div>
        </div>
        <div class="panel-footer">
            <button class="add-to-review-btn" id="addToReviewBtn">Add to Review</button>
        </div>
    `;
    shadow.appendChild(compliancePanel);

    // Create review summary
    const reviewSummary = document.createElement('div');
    reviewSummary.className = 'review-summary';
    reviewSummary.innerHTML = `
        <div class="review-summary-header">
            <span>📋</span>
            <span>Review Progress</span>
        </div>
        <div class="review-summary-stats">
            <div class="stat-item">
                <div class="stat-dot blocking"></div>
                <span id="blockingCount">0</span>
            </div>
            <div class="stat-item">
                <div class="stat-dot major"></div>
                <span id="majorCount">0</span>
            </div>
            <div class="stat-item">
                <div class="stat-dot minor"></div>
                <span id="minorCount">0</span>
            </div>
        </div>
    `;
    shadow.appendChild(reviewSummary);

    // Get panel elements
    const prevIssueBtn = issueCounter.querySelector('#prevIssueBtn');
    const nextIssueBtn = issueCounter.querySelector('#nextIssueBtn');
    const closePanelBtn = compliancePanel.querySelector('#closePanelBtn');
    const selectedElementInfo = compliancePanel.querySelector('#selectedElementInfo');
    const issueList = compliancePanel.querySelector('#issueList');
    const addToReviewBtn = compliancePanel.querySelector('#addToReviewBtn');
    const blockingCountEl = reviewSummary.querySelector('#blockingCount');
    const majorCountEl = reviewSummary.querySelector('#majorCount');
    const minorCountEl = reviewSummary.querySelector('#minorCount');

    // Subscribe to capture mode changes (hide overlay during screenshots)
    if (bus) {
        bus.subscribe('capture_mode.changed', (event) => {
            host.style.display = event.payload.enabled ? 'none' : 'block';
        });
    }

    /**
     * Run quick compliance checks against an element
     * Returns { status: 'pass'|'warning'|'fail', rules: [...] }
     */
    function checkElementCompliance(el) {
        if (!el || !reviewState.spec) {
            return { status: 'pass', rules: [] };
        }

        const rules = [];
        const styles = window.getComputedStyle(el);

        // Check against each spec rule
        for (const check of reviewState.spec.checks || []) {
            let status = 'pass';
            let message = '';

            switch (check.id) {
                case 'color-contrast': {
                    const color = styles.color;
                    const bg = styles.backgroundColor;
                    const ratio = calculateContrastRatio(color, bg);
                    const minRatio = check.config?.minimum_ratio || 4.5;
                    if (ratio && ratio < minRatio) {
                        status = 'fail';
                        message = `Contrast ${ratio.toFixed(1)}:1 (min ${minRatio}:1)`;
                    }
                    break;
                }

                case 'touch-targets': {
                    const rect = el.getBoundingClientRect();
                    const minSize = check.config?.minimum_size || 44;
                    if (el.tagName === 'BUTTON' || el.tagName === 'A' || el.getAttribute('role') === 'button') {
                        if (rect.width < minSize || rect.height < minSize) {
                            status = 'fail';
                            message = `Size ${Math.round(rect.width)}x${Math.round(rect.height)}px (min ${minSize}px)`;
                        }
                    }
                    break;
                }

                case 'focus-indicators': {
                    // Check if element is focusable and has visible focus styles
                    if (el.tabIndex >= 0 || ['BUTTON', 'A', 'INPUT', 'SELECT', 'TEXTAREA'].includes(el.tagName)) {
                        const outline = styles.outlineStyle;
                        const boxShadow = styles.boxShadow;
                        if (outline === 'none' && boxShadow === 'none') {
                            status = 'warning';
                            message = 'No visible focus indicator detected';
                        }
                    }
                    break;
                }

                case 'alt-text': {
                    if (el.tagName === 'IMG') {
                        const alt = el.getAttribute('alt');
                        if (!alt) {
                            status = 'fail';
                            message = 'Missing alt text';
                        } else if (alt.length < 5) {
                            status = 'warning';
                            message = 'Alt text may be insufficient';
                        }
                    }
                    break;
                }

                default:
                    // Skip checks that aren't quick element-level checks
                    continue;
            }

            rules.push({
                id: check.id,
                name: check.id.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
                severity: check.severity,
                status: status,
                message: message || (status === 'pass' ? 'Compliant' : 'Issue detected'),
            });
        }

        // Determine overall status
        let overallStatus = 'pass';
        for (const rule of rules) {
            if (rule.status === 'fail') {
                overallStatus = 'fail';
                break;
            } else if (rule.status === 'warning' && overallStatus !== 'fail') {
                overallStatus = 'warning';
            }
        }

        return { status: overallStatus, rules };
    }

    /**
     * Calculate color contrast ratio
     */
    function calculateContrastRatio(fgColor, bgColor) {
        function parseRgb(str) {
            const match = str.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
            if (!match) return null;
            return [parseInt(match[1]), parseInt(match[2]), parseInt(match[3])];
        }

        function luminance(r, g, b) {
            const [rs, gs, bs] = [r, g, b].map(c => {
                c = c / 255;
                return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
            });
            return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs;
        }

        const fg = parseRgb(fgColor);
        const bg = parseRgb(bgColor);
        if (!fg || !bg) return null;

        const l1 = luminance(...fg);
        const l2 = luminance(...bg);
        const ratio = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
        return ratio;
    }

    /**
     * Update the overlay position and compliance card
     */
    function updateOverlay(el) {
        if (!el || el.id?.startsWith('__') || host.contains(el)) {
            overlay.style.display = 'none';
            label.style.display = 'none';
            complianceCard.style.display = 'none';
            return;
        }

        // Don't show during capture mode
        if (bus?.state.captureMode) {
            overlay.style.display = 'none';
            label.style.display = 'none';
            complianceCard.style.display = 'none';
            return;
        }

        const rect = el.getBoundingClientRect();
        const compliance = checkElementCompliance(el);

        // Set overlay border color based on compliance
        let borderColor = COLORS.primary;
        let bgColor = COLORS.primaryLight;
        if (compliance.status === 'fail') {
            borderColor = COLORS.fail;
            bgColor = COLORS.failLight;
        } else if (compliance.status === 'warning') {
            borderColor = COLORS.warning;
            bgColor = COLORS.warningLight;
        } else if (compliance.status === 'pass' && compliance.rules.length > 0) {
            borderColor = COLORS.pass;
            bgColor = COLORS.passLight;
        }

        // Update overlay
        overlay.style.display = 'block';
        overlay.style.top = rect.top + 'px';
        overlay.style.left = rect.left + 'px';
        overlay.style.width = rect.width + 'px';
        overlay.style.height = rect.height + 'px';
        overlay.style.borderColor = borderColor;
        overlay.style.background = bgColor;

        // Update selector label
        const selector = bus ? bus.generateSelector(el).selector : el.tagName.toLowerCase();
        label.style.display = 'block';
        label.style.top = (rect.top - 32) + 'px';
        label.style.left = rect.left + 'px';
        label.textContent = selector;

        // Adjust label if off screen
        if (rect.top < 40) {
            label.style.top = (rect.bottom + 8) + 'px';
        }

        // Update compliance card if there are rules to show
        if (compliance.rules.length > 0) {
            const statusText = compliance.status === 'pass' ? '✅ Pass' :
                              compliance.status === 'warning' ? '⚠️ Warning' : '❌ Fail';
            const statusClass = compliance.status;

            complianceCard.innerHTML = `
                <div class="compliance-card-header">
                    <span>Compliance</span>
                    <span class="compliance-status ${statusClass}">${statusText}</span>
                </div>
                <div class="compliance-rules">
                    ${compliance.rules.map(rule => `
                        <div class="compliance-rule">
                            <span class="rule-status-icon">${rule.status === 'pass' ? '✅' : rule.status === 'warning' ? '⚠️' : '❌'}</span>
                            <div>
                                <div class="rule-name">${rule.name}</div>
                                <div style="color: #9CA3AF; font-size: 10px;">${rule.message}</div>
                            </div>
                            <span class="rule-severity ${rule.severity}">${rule.severity}</span>
                        </div>
                    `).join('')}
                </div>
            `;

            complianceCard.style.display = 'block';
            complianceCard.style.top = (rect.top + rect.height + 8) + 'px';
            complianceCard.style.left = rect.left + 'px';

            // Adjust if off screen
            const cardRect = complianceCard.getBoundingClientRect();
            if (cardRect.bottom > window.innerHeight) {
                complianceCard.style.top = (rect.top - cardRect.height - 8) + 'px';
            }
            if (cardRect.right > window.innerWidth) {
                complianceCard.style.left = (window.innerWidth - cardRect.width - 12) + 'px';
            }
        } else {
            complianceCard.style.display = 'none';
        }
    }

    /**
     * Show full compliance panel for selected element
     */
    function showCompliancePanel(el) {
        if (!el) return;

        reviewState.selectedElement = el;
        const selector = bus ? bus.generateSelector(el).selector : el.tagName.toLowerCase();
        const compliance = checkElementCompliance(el);

        selectedElementInfo.textContent = selector;

        // Build issue list
        const failingRules = compliance.rules.filter(r => r.status !== 'pass');
        if (failingRules.length === 0) {
            issueList.innerHTML = `
                <div style="text-align: center; color: ${COLORS.pass}; padding: 20px;">
                    ✅ No issues found for this element
                </div>
            `;
        } else {
            issueList.innerHTML = failingRules.map(rule => `
                <div class="issue-item ${rule.severity}">
                    <div class="issue-header">
                        <span class="issue-check-id">${rule.name}</span>
                        <span class="rule-severity ${rule.severity}">${rule.severity}</span>
                    </div>
                    <div class="issue-description">${rule.message}</div>
                </div>
            `).join('');
        }

        // Update add to review button
        const isAdded = reviewState.reviewedElements.has(selector);
        addToReviewBtn.textContent = isAdded ? 'Added to Review ✓' : 'Add to Review';
        addToReviewBtn.classList.toggle('added', isAdded);
        addToReviewBtn.disabled = isAdded;

        compliancePanel.style.display = 'block';
    }

    /**
     * Hide compliance panel
     */
    function hideCompliancePanel() {
        compliancePanel.style.display = 'none';
        reviewState.selectedElement = null;
    }

    /**
     * Add current element to review
     */
    function addToReview() {
        const el = reviewState.selectedElement;
        if (!el) return;

        const selector = bus ? bus.generateSelector(el).selector : el.tagName.toLowerCase();
        const compliance = checkElementCompliance(el);

        if (reviewState.reviewedElements.has(selector)) return;

        reviewState.reviewedElements.add(selector);

        // Create issue entry
        const issue = {
            selector: selector,
            timestamp: new Date().toISOString(),
            element: bus ? bus.getElementInfo(el) : { tag: el.tagName.toLowerCase() },
            compliance: compliance,
            rules: compliance.rules.filter(r => r.status !== 'pass'),
        };

        reviewState.issues.push(issue);

        // Emit event
        const event = {
            type: 'review.element_added',
            source: 'design-review',
            timestamp: new Date().toISOString(),
            payload: issue,
        };
        window.__designReviewEvents.push(event);
        if (bus) {
            bus.emit('review.element_added', 'design-review', issue);
        }

        // Update UI
        updateSummary();
        addToReviewBtn.textContent = 'Added to Review ✓';
        addToReviewBtn.classList.add('added');
        addToReviewBtn.disabled = true;

        // Flash feedback
        addToReviewBtn.style.transform = 'scale(1.05)';
        setTimeout(() => addToReviewBtn.style.transform = '', 150);
    }

    /**
     * Navigate to next/previous issue
     */
    function navigateIssue(direction) {
        if (reviewState.issues.length === 0) return;

        reviewState.currentIssueIndex += direction;

        if (reviewState.currentIssueIndex < 0) {
            reviewState.currentIssueIndex = reviewState.issues.length - 1;
        } else if (reviewState.currentIssueIndex >= reviewState.issues.length) {
            reviewState.currentIssueIndex = 0;
        }

        const issue = reviewState.issues[reviewState.currentIssueIndex];
        try {
            const el = document.querySelector(issue.selector);
            if (el) {
                el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                updateOverlay(el);
                showCompliancePanel(el);
            }
        } catch (e) {
            console.warn('[DesignReview] Could not navigate to element:', issue.selector);
        }

        updateNavButtons();
    }

    /**
     * Update navigation buttons
     */
    function updateNavButtons() {
        const hasIssues = reviewState.issues.length > 0;
        prevIssueBtn.disabled = !hasIssues;
        nextIssueBtn.disabled = !hasIssues;
        issueCounter.querySelector('.issue-count-badge').textContent = reviewState.issues.length;
    }

    /**
     * Update review summary counts
     */
    function updateSummary() {
        let blocking = 0, major = 0, minor = 0;
        for (const issue of reviewState.issues) {
            for (const rule of issue.rules) {
                if (rule.severity === 'blocking') blocking++;
                else if (rule.severity === 'major') major++;
                else minor++;
            }
        }
        blockingCountEl.textContent = blocking;
        majorCountEl.textContent = major;
        minorCountEl.textContent = minor;
    }

    // Event listeners
    document.addEventListener('mousemove', (e) => {
        const el = document.elementFromPoint(e.clientX, e.clientY);
        if (el !== reviewState.hoveredElement) {
            reviewState.hoveredElement = el;
            updateOverlay(el);
        }
    }, true);

    document.addEventListener('click', (e) => {
        if (host.contains(e.target)) return;
        if (e.target.id?.startsWith('__')) return;

        e.preventDefault();
        e.stopPropagation();

        showCompliancePanel(e.target);
    }, true);

    // Panel button listeners
    closePanelBtn.addEventListener('click', hideCompliancePanel);
    addToReviewBtn.addEventListener('click', addToReview);
    prevIssueBtn.addEventListener('click', () => navigateIssue(-1));
    nextIssueBtn.addEventListener('click', () => navigateIssue(1));

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            hideCompliancePanel();
        } else if (e.key === 'n' || e.key === 'N') {
            navigateIssue(1);
        } else if (e.key === 'a' || e.key === 'A') {
            if (reviewState.selectedElement) {
                addToReview();
            }
        }
    });

    /**
     * Initialize review with spec data
     */
    window.__designReviewInit = function(spec) {
        reviewState.spec = spec;
        console.log('[DesignReview] Initialized with spec:', spec?.name || 'unknown');
    };

    /**
     * Get review results for Python
     */
    window.__designReviewGetResults = function() {
        return {
            issues: reviewState.issues,
            reviewedElements: Array.from(reviewState.reviewedElements),
            summary: {
                blocking: parseInt(blockingCountEl.textContent),
                major: parseInt(majorCountEl.textContent),
                minor: parseInt(minorCountEl.textContent),
            }
        };
    };

    console.log('[DesignReview] Overlay initialized', bus ? `with session: ${bus.sessionId}` : 'standalone');
})();
