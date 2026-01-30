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

  // ==========================================================================
  // MODAL COMPONENTS (Shadow DOM + Popover API)
  // ==========================================================================

  // Create container for modals with closed Shadow DOM for isolation
  const modalContainer = document.createElement('div');
  modalContainer.id = '__canvas-issue-modals';
  const shadow = modalContainer.attachShadow({ mode: 'closed' });
  document.body.appendChild(modalContainer);

  // Inject styles into Shadow DOM
  const styleSheet = document.createElement('style');
  styleSheet.textContent = `
    :host {
      all: initial;
    }
    
    [popover] {
      background: ${ISSUE_TOKENS.colors.background};
      color: ${ISSUE_TOKENS.colors.text};
      border: 1px solid ${ISSUE_TOKENS.colors.border};
      border-radius: 6px;
      padding: 0;
      margin: auto;
      box-shadow: 0 8px 24px rgba(0,0,0,0.5);
      font-family: ${ISSUE_TOKENS.fonts.family};
      font-size: ${ISSUE_TOKENS.fonts.sizes.md};
      max-width: 400px;
      width: 100%;
    }
    
    [popover]::backdrop {
      background: rgba(0, 0, 0, 0.6);
      backdrop-filter: blur(2px);
    }

    .modal-header {
      padding: ${ISSUE_TOKENS.spacing.md};
      border-bottom: 1px solid ${ISSUE_TOKENS.colors.border};
      font-weight: 600;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .modal-body {
      padding: ${ISSUE_TOKENS.spacing.md};
      display: flex;
      flex-direction: column;
      gap: ${ISSUE_TOKENS.spacing.sm};
    }

    .modal-footer {
      padding: ${ISSUE_TOKENS.spacing.md};
      border-top: 1px solid ${ISSUE_TOKENS.colors.border};
      display: flex;
      justify-content: flex-end;
      gap: ${ISSUE_TOKENS.spacing.sm};
    }

    input, textarea {
      background: #010409;
      border: 1px solid ${ISSUE_TOKENS.colors.border};
      color: ${ISSUE_TOKENS.colors.text};
      border-radius: 4px;
      padding: 6px 8px;
      font-family: inherit;
      font-size: inherit;
      width: 100%;
      box-sizing: border-box;
    }

    input:focus, textarea:focus {
      border-color: ${ISSUE_TOKENS.colors.primary};
      outline: none;
    }

    textarea {
      min-height: 100px;
      resize: vertical;
    }

    button {
      padding: 6px 12px;
      border-radius: 4px;
      border: 1px solid ${ISSUE_TOKENS.colors.border};
      background: ${ISSUE_TOKENS.colors.background};
      color: ${ISSUE_TOKENS.colors.primary};
      font-size: ${ISSUE_TOKENS.fonts.sizes.sm};
      cursor: pointer;
      font-family: inherit;
      font-weight: 500;
    }

    button:hover {
      background: ${ISSUE_TOKENS.colors.hover};
    }

    button.primary {
      background: #238636;
      color: white;
      border-color: rgba(240, 246, 252, 0.1);
    }

    button.primary:hover {
      background: #2ea043;
    }
    
    .status-icon {
      font-size: 24px;
      margin-right: 8px;
    }
    
    .success { color: ${ISSUE_TOKENS.colors.status.success}; }
    .error { color: ${ISSUE_TOKENS.colors.status.error}; }
    
    a {
      color: ${ISSUE_TOKENS.colors.primary};
      text-decoration: none;
    }
    a:hover {
      text-decoration: underline;
    }
  `;
  shadow.appendChild(styleSheet);

  // --------------------------------------------------------------------------
  // 1. REPO CONFIG MODAL
  // --------------------------------------------------------------------------
  const repoModal = document.createElement('div');
  repoModal.setAttribute('popover', 'auto');
  repoModal.id = 'repo-config-modal';
  repoModal.innerHTML = `
    <div class="modal-header">
      <span>Configure Repository</span>
    </div>
    <div class="modal-body">
      <label for="repo-input" style="font-size: ${ISSUE_TOKENS.fonts.sizes.sm}; color: #8b949e;">
        Enter GitHub repository (owner/repo):
      </label>
      <input type="text" id="repo-input" placeholder="owner/repo (e.g. myorg/project)">
    </div>
    <div class="modal-footer">
      <button id="repo-cancel">Cancel</button>
      <button id="repo-save" class="primary">Save</button>
    </div>
  `;
  shadow.appendChild(repoModal);

  // Repo Modal Logic
  const repoInput = repoModal.querySelector('#repo-input');
  const repoSaveBtn = repoModal.querySelector('#repo-save');
  const repoCancelBtn = repoModal.querySelector('#repo-cancel');

  repoSaveBtn.addEventListener('click', () => {
    const repo = repoInput.value.trim();
    if (repo) {
      window.__canvasBus.emit('issue.repo_configured', 'issue-overlay', { repo });
      repoModal.hidePopover();
    }
  });

  repoCancelBtn.addEventListener('click', () => {
    repoModal.hidePopover();
  });

  // --------------------------------------------------------------------------
  // 2. ISSUE CREATION MODAL
  // --------------------------------------------------------------------------
  const createModal = document.createElement('div');
  createModal.setAttribute('popover', 'auto');
  createModal.id = 'issue-create-modal';
  createModal.innerHTML = `
    <div class="modal-header">
      <span>New Issue</span>
    </div>
    <div class="modal-body">
      <input type="text" id="issue-title" placeholder="Title">
      <textarea id="issue-description" placeholder="Leave a description"></textarea>
    </div>
    <div class="modal-footer">
      <button id="issue-cancel">Cancel</button>
      <button id="issue-create" class="primary">Create issue</button>
    </div>
  `;
  shadow.appendChild(createModal);

  // Issue Modal Logic
  const issueTitle = createModal.querySelector('#issue-title');
  const issueDesc = createModal.querySelector('#issue-description');
  const issueCreateBtn = createModal.querySelector('#issue-create');
  const issueCancelBtn = createModal.querySelector('#issue-cancel');

  issueCreateBtn.addEventListener('click', () => {
    const title = issueTitle.value.trim();
    const description = issueDesc.value.trim();
    
    if (title) {
      window.__canvasBus.emit('issue.create_requested', 'issue-overlay', { 
        title, 
        description 
      });
      createModal.hidePopover();
    }
  });

  issueCancelBtn.addEventListener('click', () => {
    createModal.hidePopover();
  });

  // --------------------------------------------------------------------------
  // 3. CONFIRMATION OVERLAY
  // --------------------------------------------------------------------------
  const confirmModal = document.createElement('div');
  confirmModal.setAttribute('popover', 'auto');
  confirmModal.id = 'confirmation-modal';
  // Dynamic content structure
  confirmModal.innerHTML = `
    <div class="modal-body" style="flex-direction: row; align-items: center;">
      <span id="confirm-icon" class="status-icon"></span>
      <div id="confirm-message" style="flex: 1;"></div>
    </div>
    <div class="modal-footer" style="padding-top: 0; border: none;">
      <button id="confirm-dismiss">Dismiss</button>
    </div>
  `;
  shadow.appendChild(confirmModal);

  const confirmIcon = confirmModal.querySelector('#confirm-icon');
  const confirmMsg = confirmModal.querySelector('#confirm-message');
  const confirmDismiss = confirmModal.querySelector('#confirm-dismiss');

  confirmDismiss.addEventListener('click', () => {
    confirmModal.hidePopover();
  });

  // --------------------------------------------------------------------------
  // EVENT LISTENERS (Python -> JS)
  // --------------------------------------------------------------------------
  if (window.__canvasBus) {
    
    // 1. Repo Prompt
    window.__canvasBus.subscribe('issue.repo_prompt', (event) => {
      if (event.payload && event.payload.existing) {
        repoInput.value = event.payload.existing;
      }
      repoModal.showPopover();
      repoInput.focus();
    });

    // 2. Create Modal
    window.__canvasBus.subscribe('issue.create_modal', (event) => {
      const { suggestedTitle, selections } = event.payload || {};
      
      issueTitle.value = suggestedTitle || '';
      issueDesc.value = selections ? 
        `Context:\n\`\`\`\n${JSON.stringify(selections, null, 2)}\n\`\`\`` : '';
        
      createModal.showPopover();
      issueTitle.focus();
    });

    // 3. Issue Created (Success)
    window.__canvasBus.subscribe('issue.created', (event) => {
      const { url } = event.payload;
      confirmIcon.textContent = '✓';
      confirmIcon.className = 'status-icon success';
      confirmMsg.innerHTML = `Issue created! <a href="${url}" target="_blank">View on GitHub</a>`;
      
      confirmModal.showPopover();
      
      // Auto-close after 5s
      setTimeout(() => confirmModal.hidePopover(), 5000);
    });

    // 4. Issue Failed (Error)
    window.__canvasBus.subscribe('issue.failed', (event) => {
      const { error, fallbackUrl } = event.payload;
      confirmIcon.textContent = '⚠';
      confirmIcon.className = 'status-icon error';
      confirmMsg.innerHTML = `
        <div>Could not create issue.</div>
        <div style="font-size: 12px; margin-top: 4px; color: #8b949e;">${error}</div>
        ${fallbackUrl ? `<div style="margin-top: 4px;"><a href="${fallbackUrl}" target="_blank">Open manually</a></div>` : ''}
      `;
      
      confirmModal.showPopover();
    });
  }

})();
