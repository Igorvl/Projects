/**
 * POPUP.JS — Extension Popup UI Logic
 * =====================================
 *
 * This script controls the popup that appears when the user clicks
 * the extension icon. It communicates with the service worker to:
 * 1. Display connection status (online/offline)
 * 2. Show capture statistics and recent captures
 * 3. Allow project selection from the Project DNA API
 * 4. Toggle auto-capture on/off
 * 5. Configure API URL
 *
 * COMMUNICATION:
 * Popup ↔ Service Worker via chrome.runtime.sendMessage
 * Popup reads state from chrome.storage.local
 *
 * NOTE: The popup is destroyed every time it closes! Unlike background
 * scripts, popup scripts do NOT persist. Each time the user opens the
 * popup, this script runs from scratch. That's why we load all state
 * from chrome.storage and the service worker on every open.
 */

(function () {
  'use strict';

  // =========================================================================
  // DOM ELEMENTS
  // =========================================================================

  const elements = {
    // Status
    statusDot: document.getElementById('statusDot'),
    statusText: document.getElementById('statusText'),

    // Stats
    statCaptures: document.getElementById('statCaptures'),
    statQueue: document.getElementById('statQueue'),
    statLatency: document.getElementById('statLatency'),

    // Toggle
    captureToggle: document.getElementById('captureToggle'),
    toggleDesc: document.getElementById('toggleDesc'),

    // Project
    projectSelect: document.getElementById('projectSelect'),
    refreshProjects: document.getElementById('refreshProjects'),

    // Recent
    recentList: document.getElementById('recentList'),

    // Settings
    settingsToggle: document.getElementById('settingsToggle'),
    settingsSection: document.getElementById('settingsSection'),
    settingsBody: document.getElementById('settingsBody'),
    apiUrlInput: document.getElementById('apiUrlInput'),
    saveApiUrl: document.getElementById('saveApiUrl'),
    retryQueue: document.getElementById('retryQueue'),
  };

  // =========================================================================
  // INITIALIZATION
  // =========================================================================

  /**
   * Initialize the popup: load state, check health, populate UI.
   * Called immediately when the popup opens.
   */
  async function init() {
    // Load current extension state from service worker
    loadState();

    // Check API health
    checkHealth();

    // Load projects list
    loadProjects();

    // Set up event listeners
    setupEventListeners();
  }

  // =========================================================================
  // STATE LOADING
  // =========================================================================

  /**
   * Load extension state from the service worker and update UI.
   */
  function loadState() {
    chrome.runtime.sendMessage({ action: 'GET_STATE' }, (state) => {
      if (chrome.runtime.lastError) {
        console.error('Failed to get state:', chrome.runtime.lastError);
        return;
      }

      if (!state) return;

      // Update stats
      elements.statCaptures.textContent = state.totalCaptures || 0;
      elements.statQueue.textContent = state.queueSize || 0;

      // Update toggle
      updateToggleUI(state.captureEnabled);

      // Update project selector
      if (state.activeProject) {
        elements.projectSelect.value = state.activeProject;
      }

      // Update API URL in settings
      elements.apiUrlInput.value = state.API_URL || '';

      // Update recent captures list
      renderRecentCaptures(state.recentCaptures || []);
    });
  }

  // =========================================================================
  // HEALTH CHECK
  // =========================================================================

  /**
   * Check the Project DNA API health and update the status indicator.
   */
  function checkHealth() {
    chrome.runtime.sendMessage({ action: 'CHECK_HEALTH' }, (result) => {
      if (chrome.runtime.lastError) {
        setStatus('offline', 'Extension error');
        return;
      }

      if (result && result.online) {
        setStatus('online', `Online (${result.latency}ms)`);
        elements.statLatency.textContent = `${result.latency}ms`;
      } else {
        setStatus('offline', 'Offline');
        elements.statLatency.textContent = '—';
      }
    });
  }

  /**
   * Update the connection status indicator.
   *
   * @param {'online'|'offline'} status - Connection status
   * @param {string} text               - Display text
   */
  function setStatus(status, text) {
    elements.statusDot.className = `status-dot ${status}`;
    elements.statusText.textContent = text;
  }

  // =========================================================================
  // PROJECTS
  // =========================================================================

  /**
   * Load the list of projects from Project DNA API.
   */
  function loadProjects() {
    // Add spinning animation to refresh button
    elements.refreshProjects.classList.add('spinning');

    chrome.runtime.sendMessage({ action: 'GET_PROJECTS' }, (projects) => {
      elements.refreshProjects.classList.remove('spinning');

      if (chrome.runtime.lastError || !projects) {
        console.error('Failed to load projects');
        return;
      }

      // Get currently selected project to restore selection
      chrome.storage.local.get('activeProject', (result) => {
        const activeProject = result.activeProject;

        // Clear existing options (keep the placeholder)
        elements.projectSelect.innerHTML = '<option value="">— Select project —</option>';

        // Add project options
        for (const project of projects) {
          const option = document.createElement('option');
          option.value = project.slug;
          option.textContent = project.name || project.slug;

          // Restore previous selection
          if (project.slug === activeProject) {
            option.selected = true;
          }

          elements.projectSelect.appendChild(option);
        }
      });
    });
  }

  /**
   * Handle project selection change.
   */
  function onProjectChange() {
    const slug = elements.projectSelect.value;

    if (!slug) return;

    chrome.runtime.sendMessage(
      { action: 'SET_PROJECT', data: { slug } },
      (response) => {
        if (response && response.success) {
          showToast(`Project set to: ${slug}`);
        }
      }
    );
  }

  // =========================================================================
  // TOGGLE
  // =========================================================================

  /**
   * Toggle auto-capture on/off.
   */
  function onToggleCapture() {
    chrome.runtime.sendMessage({ action: 'TOGGLE_CAPTURE' }, (response) => {
      if (response && response.success) {
        updateToggleUI(response.captureEnabled);
      }
    });
  }

  /**
   * Update the toggle button UI to reflect current state.
   *
   * @param {boolean} enabled - Whether capture is enabled
   */
  function updateToggleUI(enabled) {
    if (enabled) {
      elements.captureToggle.classList.add('active');
      elements.toggleDesc.textContent = 'Capturing AI Studio generations';
    } else {
      elements.captureToggle.classList.remove('active');
      elements.toggleDesc.textContent = 'Capture paused';
    }
  }

  // =========================================================================
  // RECENT CAPTURES
  // =========================================================================

  /**
   * Render the list of recent captures.
   *
   * @param {object[]} captures - Array of recent capture objects
   */
  function renderRecentCaptures(captures) {
    if (!captures || captures.length === 0) {
      elements.recentList.innerHTML = `
        <div class="empty-state">
          <span class="empty-icon">🔬</span>
          <span class="empty-text">No captures yet. Open AI Studio and start generating!</span>
        </div>
      `;
      return;
    }

    elements.recentList.innerHTML = captures.map((capture, index) => `
      <div class="capture-item ${index === 0 ? 'capture-item--new' : ''}">
        <span class="capture-dot"></span>
        <div class="capture-info">
          <span class="capture-model">${escapeHtml(capture.model || 'Unknown')}</span>
          <span class="capture-preview">${escapeHtml(capture.promptPreview || '...')}</span>
        </div>
        <span class="capture-time">${formatTime(capture.timestamp)}</span>
      </div>
    `).join('');
  }

  // =========================================================================
  // SETTINGS
  // =========================================================================

  /**
   * Toggle settings section visibility.
   */
  function onToggleSettings() {
    elements.settingsSection.classList.toggle('section--collapsed');
  }

  /**
   * Save the API URL configuration.
   */
  function onSaveApiUrl() {
    const url = elements.apiUrlInput.value.trim();

    if (!url) {
      showToast('Please enter a valid URL', 'error');
      return;
    }

    chrome.runtime.sendMessage(
      { action: 'SET_API_URL', data: { url } },
      (response) => {
        if (response && response.success) {
          showToast('API URL saved!');
          // Re-check health with new URL
          setTimeout(checkHealth, 500);
        }
      }
    );
  }

  /**
   * Retry sending queued captures.
   */
  function onRetryQueue() {
    elements.retryQueue.textContent = '⏳ Retrying...';
    elements.retryQueue.disabled = true;

    chrome.runtime.sendMessage({ action: 'RETRY_QUEUE' }, () => {
      elements.retryQueue.textContent = '🔄 Retry Queued Captures';
      elements.retryQueue.disabled = false;

      // Reload state to update queue count
      setTimeout(loadState, 1000);
      showToast('Queue processed');
    });
  }

  // =========================================================================
  // EVENT LISTENERS
  // =========================================================================

  function setupEventListeners() {
    elements.captureToggle.addEventListener('click', onToggleCapture);
    elements.projectSelect.addEventListener('change', onProjectChange);
    elements.refreshProjects.addEventListener('click', loadProjects);
    elements.settingsToggle.addEventListener('click', onToggleSettings);
    elements.saveApiUrl.addEventListener('click', onSaveApiUrl);
    elements.retryQueue.addEventListener('click', onRetryQueue);

    // Save API URL on Enter key
    elements.apiUrlInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') onSaveApiUrl();
    });
  }

  // =========================================================================
  // UTILITIES
  // =========================================================================

  /**
   * Escape HTML special characters to prevent XSS.
   * Never trust data from external sources (even our own API).
   *
   * @param {string} str - Raw string
   * @returns {string}   - HTML-safe string
   */
  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  /**
   * Format a timestamp to a human-readable relative time.
   *
   * @param {string} timestamp - ISO timestamp
   * @returns {string}         - Formatted time (e.g., "2m ago")
   */
  function formatTime(timestamp) {
    if (!timestamp) return '';

    const now = Date.now();
    const then = new Date(timestamp).getTime();
    const diffMs = now - then;
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);

    if (diffSec < 60) return 'now';
    if (diffMin < 60) return `${diffMin}m`;
    if (diffHour < 24) return `${diffHour}h`;
    return new Date(timestamp).toLocaleDateString();
  }

  /**
   * Show a temporary toast notification at the bottom of the popup.
   *
   * @param {string} message  - Toast message
   * @param {'info'|'error'} type - Toast type
   */
  function showToast(message, type = 'info') {
    // Remove existing toast if any
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.className = `toast ${type === 'error' ? 'toast--error' : ''}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    // Auto-remove after 2.5 seconds
    setTimeout(() => toast.remove(), 2500);
  }

  // =========================================================================
  // START
  // =========================================================================

  // Initialize when DOM is ready
  init();

})();
