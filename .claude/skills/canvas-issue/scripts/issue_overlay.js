(function() {
  // Design tokens duplicated from agent-canvas (as they are not exported)
  const ISSUE_TOKENS = {
    colors: {
      primary: '#58a6ff',
      background: '#0d1117',
      text: '#c9d1d9',
      border: '#30363d',
      status: { success: '#3fb950', error: '#f85149' },
      hover: '#1f242c' // Added for button hover state
    },
    fonts: { 
      family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif', 
      sizes: { sm: '12px', md: '14px' } 
    },
    spacing: { xs: '4px', sm: '8px', md: '12px' },
    shadows: { sm: '0 1px 2px rgba(0,0,0,0.3)' },
    zIndex: { overlay: 2147483640, tooltip: 2147483645 }
  };

  // Check if button already exists to prevent duplicates
  if (document.getElementById('__canvas-issue-btn')) {
    return;
  }

  // Create the "Create Issue" button
  const createIssueBtn = document.createElement('button');
  createIssueBtn.id = '__canvas-issue-btn';
  createIssueBtn.textContent = 'Create Issue';
  
  // Style the button to match the counter badge but interactive
  createIssueBtn.style.cssText = `
    position: fixed;
    top: 10px;
    right: 120px; /* Positioned to the left of the counter badge */
    background: ${ISSUE_TOKENS.colors.background};
    color: ${ISSUE_TOKENS.colors.primary};
    padding: ${ISSUE_TOKENS.spacing.sm} ${ISSUE_TOKENS.spacing.md};
    border-radius: 6px;
    font-family: ${ISSUE_TOKENS.fonts.family};
    font-size: ${ISSUE_TOKENS.fonts.sizes.md};
    font-weight: 500;
    z-index: ${ISSUE_TOKENS.zIndex.tooltip};
    border: 1px solid ${ISSUE_TOKENS.colors.border};
    box-shadow: ${ISSUE_TOKENS.shadows.sm};
    cursor: pointer;
    transition: background-color 0.2s, transform 0.1s;
    outline: none;
    display: flex;
    align-items: center;
    gap: 6px;
  `;

  // Hover effects
  createIssueBtn.onmouseenter = () => {
    createIssueBtn.style.backgroundColor = ISSUE_TOKENS.colors.hover;
    createIssueBtn.style.borderColor = ISSUE_TOKENS.colors.primary;
  };
  createIssueBtn.onmouseleave = () => {
    createIssueBtn.style.backgroundColor = ISSUE_TOKENS.colors.background;
    createIssueBtn.style.borderColor = ISSUE_TOKENS.colors.border;
  };
  
  // Active/Click effect
  createIssueBtn.onmousedown = () => {
    createIssueBtn.style.transform = 'scale(0.96)';
  };
  createIssueBtn.onmouseup = () => {
    createIssueBtn.style.transform = 'scale(1)';
  };

  // Add event listener for click
  createIssueBtn.addEventListener('click', (e) => {
    e.stopPropagation(); // Prevent triggering other overlay clicks
    console.log('[Canvas Issue] Create Issue button clicked');
    
    if (window.__canvasBus) {
      window.__canvasBus.emit('issue.button_clicked', 'issue-overlay', {
        timestamp: Date.now()
      });
    } else {
      console.warn('[Canvas Issue] Canvas Bus not available');
    }
  });

  // Handle capture mode (hide during screenshots)
  if (window.__canvasBus) {
    window.__canvasBus.subscribe('capture_mode.changed', (event) => {
      const isCapturing = event.payload && event.payload.active;
      createIssueBtn.style.display = isCapturing ? 'none' : 'flex';
    });
  }

  // Add to DOM
  document.body.appendChild(createIssueBtn);
  console.log('[Canvas Issue] Issue overlay button injected');

})();
