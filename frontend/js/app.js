/**
 * ATS Resume Analyzer — Modern AI/SaaS Frontend Application
 * Handles file validation, theme toggling, staged analysis progress,
 * dynamic visualizations, and authenticated history interaction.
 */

document.addEventListener('DOMContentLoaded', () => {
  // ==========================================================================
  // State Management
  // ==========================================================================
  let selectedFile = null;
  let currentAnalysisData = null;

  // ==========================================================================
  // DOM Elements
  // ==========================================================================
  const themeToggleBtn = document.getElementById('theme-toggle-btn');
  const themeIconMoon = document.getElementById('theme-icon-moon');
  const themeIconSun = document.getElementById('theme-icon-sun');

  const resumeDropzone = document.getElementById('resume-dropzone');
  const resumeFileInput = document.getElementById('resume-file');
  const filePreviewCard = document.getElementById('file-preview-card');
  const previewFilename = document.getElementById('preview-filename');
  const previewFilesize = document.getElementById('preview-filesize');
  const removeFileBtn = document.getElementById('remove-file-btn');
  const uploadError = document.getElementById('upload-error');
  const uploadErrorText = document.getElementById('upload-error-text');

  const jdText = document.getElementById('jd-text');
  const jdCharCount = document.getElementById('jd-char-count');
  const analyzeBtn = document.getElementById('analyze-btn');

  const loadingBox = document.getElementById('loading-box');
  const resultsSection = document.getElementById('results');

  const downloadPdfBtn = document.getElementById('download-pdf-btn');
  const downloadSummaryBtn = document.getElementById('download-summary-btn');

  const navHistoryBtn = document.getElementById('nav-history-btn');
  const historyModal = document.getElementById('history-modal');
  const closeHistoryBtn = document.getElementById('close-history-btn');
  const historyLoading = document.getElementById('history-loading');
  const historyEmpty = document.getElementById('history-empty');
  const historyTableWrap = document.getElementById('history-table-wrap');
  const historyTableBody = document.getElementById('history-table-body');
  const historyCardsMobile = document.getElementById('history-cards-mobile');

  const navAboutBtn = document.getElementById('nav-about-btn');
  const aboutModal = document.getElementById('about-modal');
  const closeAboutBtn = document.getElementById('close-about-btn');

  const systemStatusIndicator = document.getElementById('system-status-indicator');

  // ==========================================================================
  // 1. Theme Management (Light / Dark)
  // ==========================================================================
  function initTheme() {
    const savedTheme = localStorage.getItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const initialTheme = savedTheme || (prefersDark ? 'dark' : 'light');
    applyTheme(initialTheme);
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);

    if (theme === 'dark') {
      themeIconMoon.style.display = 'none';
      themeIconSun.style.display = 'block';
    } else {
      themeIconMoon.style.display = 'block';
      themeIconSun.style.display = 'none';
    }
  }

  themeToggleBtn.addEventListener('click', () => {
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
    applyTheme(currentTheme === 'dark' ? 'light' : 'dark');
  });

  initTheme();

  // ==========================================================================
  // 2. Authentication Helper
  // ==========================================================================
  function getAuthHeaders() {
    let token = localStorage.getItem('supabase_token') || sessionStorage.getItem('supabase_token');
    if (!token) {
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && key.startsWith('sb-') && key.endsWith('-auth-token')) {
          try {
            const parsed = JSON.parse(localStorage.getItem(key));
            if (parsed?.access_token) {
              token = parsed.access_token;
              break;
            }
          } catch (_) {}
        }
      }
    }
    return token ? { 'Authorization': `Bearer ${token}` } : {};
  }

  // ==========================================================================
  // 3. Backend Health Check
  // ==========================================================================
  async function checkBackendHealth() {
    try {
      const res = await fetch('/api/v1/health');
      if (res.ok) {
        const data = await res.json();
        if (data.nlp_loaded && data.embedder_loaded) {
          systemStatusIndicator.textContent = 'AI Models Loaded & Ready';
        } else {
          systemStatusIndicator.textContent = 'Models Initializing...';
        }
      }
    } catch (_) {
      systemStatusIndicator.textContent = 'Backend Offline';
      systemStatusIndicator.parentElement.style.borderColor = 'var(--danger-border)';
      systemStatusIndicator.parentElement.querySelector('.hero-pill-dot').style.backgroundColor = 'var(--danger)';
    }
  }
  checkBackendHealth();

  // ==========================================================================
  // 4. File Upload & Drag-and-Drop Handling
  // ==========================================================================
  ['dragenter', 'dragover'].forEach(name => {
    resumeDropzone.addEventListener(name, (e) => {
      e.preventDefault();
      e.stopPropagation();
      resumeDropzone.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach(name => {
    resumeDropzone.addEventListener(name, (e) => {
      e.preventDefault();
      e.stopPropagation();
      resumeDropzone.classList.remove('dragover');
    });
  });

  resumeDropzone.addEventListener('drop', (e) => {
    const files = e.dataTransfer?.files;
    if (files && files.length > 0) {
      handleFileSelection(files[0]);
    }
  });

  resumeDropzone.addEventListener('click', () => {
    resumeFileInput.click();
  });

  resumeDropzone.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      resumeFileInput.click();
    }
  });

  resumeFileInput.addEventListener('change', (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFileSelection(e.target.files[0]);
    }
  });

  function handleFileSelection(file) {
    hideUploadError();

    // Validate file extension
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['pdf', 'docx'].includes(ext)) {
      showUploadError('Unsupported file type. Please upload a PDF or DOCX resume.');
      return;
    }

    // Validate file size (5 MB max)
    if (file.size > 5 * 1024 * 1024) {
      showUploadError('File exceeds 5 MB limit. Please upload a smaller document.');
      return;
    }

    selectedFile = file;
    previewFilename.textContent = file.name;
    previewFilesize.textContent = formatBytes(file.size);

    resumeDropzone.style.display = 'none';
    filePreviewCard.classList.add('show');
    analyzeBtn.disabled = false;
  }

  removeFileBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    resetFileUpload();
  });

  function resetFileUpload() {
    selectedFile = null;
    resumeFileInput.value = '';
    filePreviewCard.classList.remove('show');
    resumeDropzone.style.display = 'flex';
    analyzeBtn.disabled = true;
    hideUploadError();
  }

  function showUploadError(message) {
    uploadErrorText.textContent = message;
    uploadError.classList.add('show');
  }

  function hideUploadError() {
    uploadError.classList.remove('show');
  }

  function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }

  // Live Character Counter for Job Description
  jdText.addEventListener('input', () => {
    const len = jdText.value.length;
    jdCharCount.textContent = `${len.toLocaleString()} character${len === 1 ? '' : 's'}`;
  });

  // ==========================================================================
  // 5. Staged Analysis Execution Flow
  // ==========================================================================
  analyzeBtn.addEventListener('click', async () => {
    if (!selectedFile) return;

    // UI Loading state
    analyzeBtn.disabled = true;
    hideUploadError();
    resultsSection.classList.remove('show');
    loadingBox.classList.add('show');
    loadingBox.scrollIntoView({ behavior: 'smooth', block: 'center' });

    // Step state simulation
    const stages = [
      document.getElementById('stage-1'),
      document.getElementById('stage-2'),
      document.getElementById('stage-3'),
      document.getElementById('stage-4'),
      document.getElementById('stage-5'),
    ];

    stages.forEach(s => {
      s.className = 'stage-item pending';
      s.querySelector('.stage-icon').textContent = '○';
    });

    let currentStep = 0;
    const stageInterval = setInterval(() => {
      if (currentStep < stages.length) {
        if (currentStep > 0) {
          stages[currentStep - 1].className = 'stage-item completed';
          stages[currentStep - 1].querySelector('.stage-icon').textContent = '✓';
        }
        stages[currentStep].className = 'stage-item active';
        stages[currentStep].querySelector('.stage-icon').textContent = '⟳';
        currentStep++;
      }
    }, 1800);

    // Prepare multipart form data
    const formData = new FormData();
    formData.append('resume', selectedFile);
    if (jdText.value.trim()) {
      formData.append('job_description', jdText.value.trim());
    }

    try {
      const res = await fetch('/api/v1/analyze-resume', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: formData,
      });

      clearInterval(stageInterval);

      if (!res.ok) {
        const errorJson = await res.json().catch(() => ({ detail: 'Analysis could not be completed.' }));
        throw new Error(errorJson.detail || 'Analysis could not be completed. Please check your document and try again.');
      }

      currentAnalysisData = await res.json();

      // Mark all stages complete
      stages.forEach(s => {
        s.className = 'stage-item completed';
        s.querySelector('.stage-icon').textContent = '✓';
      });

      setTimeout(() => {
        loadingBox.classList.remove('show');
        renderResults(currentAnalysisData, selectedFile.name);
        resultsSection.classList.add('show');
        resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        showToast('Resume analysis completed successfully!', 'success');
      }, 400);

    } catch (err) {
      clearInterval(stageInterval);
      loadingBox.classList.remove('show');
      showToast(err.message || 'An unexpected error occurred during analysis.', 'danger');
    } finally {
      analyzeBtn.disabled = false;
    }
  });

  // ==========================================================================
  // 6. Results Dashboard Visualization
  // ==========================================================================
  function renderResults(data, filename = 'resume.pdf') {
    // Top Metadata
    document.getElementById('res-filename').textContent = `Document: ${filename}`;
    document.getElementById('res-date').textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    // AI Status Indicator
    const aiPill = document.getElementById('ai-status-pill');
    const aiText = document.getElementById('ai-status-text');
    if (data.llm_status === 'fallback') {
      aiPill.className = 'ai-status-pill fallback';
      aiText.textContent = 'Deterministic NLP Fallback';
    } else {
      aiPill.className = 'ai-status-pill active';
      aiText.textContent = 'AI Enhanced (Groq Llama 3)';
    }

    // Overall Score & Gauge Animation
    const score = Math.min(100, Math.max(0, Math.round(data.ATS_score ?? data.ats_score ?? 0)));
    animateScoreCounter('gauge-score-val', score);

    // SVG Gauge Circle Fill: Circumference = 2 * PI * 70 = 439.82
    const circumference = 439.82;
    const offset = circumference - (score / 100) * circumference;
    const gaugeFill = document.getElementById('gauge-fill-circle');
    gaugeFill.style.strokeDashoffset = offset;

    // Tier Badge & Color Styling
    const tierBadge = document.getElementById('gauge-tier-badge');
    if (score >= 85) {
      gaugeFill.style.stroke = 'var(--success)';
      tierBadge.className = 'tier-badge excellent';
      tierBadge.textContent = 'Excellent Match';
    } else if (score >= 70) {
      gaugeFill.style.stroke = 'var(--primary)';
      tierBadge.className = 'tier-badge good';
      tierBadge.textContent = 'Good Optimization';
    } else if (score >= 55) {
      gaugeFill.style.stroke = 'var(--warning)';
      tierBadge.className = 'tier-badge moderate';
      tierBadge.textContent = 'Moderate Match';
    } else {
      gaugeFill.style.stroke = 'var(--danger)';
      tierBadge.className = 'tier-badge needs-work';
      tierBadge.textContent = 'Needs Revision';
    }

    document.getElementById('gauge-interpretation-text').textContent =
      data.interpretation || (score >= 75
        ? 'Your resume demonstrates solid ATS compatibility with clear formatting and strong keywords.'
        : 'Key improvements in formatting, keywords, and quantified achievements will enhance your screening pass rate.');

    // 5 Dimension Breakdown Progress Bars
    const comps = data.component_scores || {};
    const setMetric = (textId, fillId, val, max) => {
      const rounded = Math.min(max, Math.max(0, Math.round(val)));
      document.getElementById(textId).textContent = `${rounded} / ${max}`;
      const fillEl = document.getElementById(fillId);
      const pct = (rounded / max) * 100;
      fillEl.style.width = `${pct}%`;
    };

    setMetric('score-formatting-text', 'progress-formatting', comps.formatting || 0, 20);
    setMetric('score-keywords-text', 'progress-keywords', comps.keywords || 0, 25);
    setMetric('score-content-text', 'progress-content', comps.content || 0, 25);
    setMetric('score-skill-val-text', 'progress-skill-val', comps.skill_validation || 0, 15);
    setMetric('score-ats-comp-text', 'progress-ats-comp', comps.ats_compatibility || 0, 15);

    // Job Description Match Card
    const jdMatch = data.jd_match_analysis || data.jd_comparison;
    const jdCard = document.getElementById('jd-match-card');

    if (jdMatch && jdMatch.match_percentage !== undefined) {
      jdCard.style.display = 'flex';
      const matchPct = Math.round(jdMatch.match_percentage || 0);
      document.getElementById('jd-match-pct-badge').textContent = `${matchPct}% Match`;
      document.getElementById('jd-semantic-score').textContent = (jdMatch.semantic_similarity || 0).toFixed(2);

      renderChipsWithShowMore(
        'matched-keywords-chips',
        'show-more-matched-btn',
        jdMatch.matched_keywords || [],
        'chip-success',
        'None identified',
        8
      );

      renderChipsWithShowMore(
        'missing-keywords-chips',
        'show-more-missing-btn',
        jdMatch.missing_keywords || jdMatch.skills_gap || [],
        'chip-danger',
        'None missing — all key requirements matched!',
        8
      );
    } else {
      jdCard.style.display = 'none';
    }

    // Skill Experience Validation Card
    const svDetails = data.skill_validation_details || {};
    const validatedList = (svDetails.validated || []).map(v => typeof v === 'object' ? v.skill : v);
    const unvalidatedList = (svDetails.unvalidated || []).map(u => typeof u === 'object' ? u.skill : u);
    const valPct = Math.round(svDetails.validation_pct || (validatedList.length / (validatedList.length + unvalidatedList.length || 1) * 100));

    document.getElementById('skill-val-pct-badge').textContent = `${valPct}% Verified`;

    renderChipsWithShowMore(
      'validated-skills-chips',
      'show-more-val-btn',
      validatedList,
      'chip-success',
      'No skills verified with direct project context',
      8
    );

    renderChipsWithShowMore(
      'unvalidated-skills-chips',
      'show-more-unval-btn',
      unvalidatedList,
      'chip-warning',
      'All claimed skills are backed by experience!',
      8
    );

    // Grammar & Text Quality Card
    const issuesSummary = data.issues_summary || [];
    const grammarErrCount = issuesSummary.filter(i => /grammar|spelling|typo|punctuation/i.test(i)).length;
    const grammarScore = Math.max(70, 100 - grammarErrCount * 10);
    document.getElementById('grammar-score-display').textContent = `${grammarScore}%`;
    const grammarChip = document.getElementById('grammar-status-chip');
    if (grammarErrCount === 0) {
      grammarChip.className = 'chip chip-success';
      grammarChip.textContent = 'Clean';
      document.getElementById('grammar-desc').textContent = 'Deterministic linguistic audit found zero critical typos or punctuation glitches.';
    } else {
      grammarChip.className = 'chip chip-warning';
      grammarChip.textContent = `${grammarErrCount} anomaly`;
      document.getElementById('grammar-desc').textContent = `${grammarErrCount} text quality anomaly detected. Review recommendations below for clean readability.`;
    }

    // Privacy Card
    const privacyRisk = (data.critical_issues || []).some(i => /privacy|address|pin/i.test(i));
    const privacyChip = document.getElementById('privacy-status-chip');
    if (!privacyRisk) {
      privacyChip.className = 'chip chip-success';
      privacyChip.textContent = 'Safe';
      document.getElementById('privacy-status-title').textContent = 'Safe Contact Data';
      document.getElementById('privacy-desc').textContent = 'Only standard City/State or professional contact information was detected. No excessive PII.';
    } else {
      privacyChip.className = 'chip chip-warning';
      privacyChip.textContent = 'Attention';
      document.getElementById('privacy-status-title').textContent = 'PII Over-disclosure';
      document.getElementById('privacy-desc').textContent = 'Full street addresses or ZIP/PIN codes were flagged. For ATS submissions, City, State is sufficient.';
    }

    // Optimization Recommendations List
    renderRecommendations(data);
  }

  function animateScoreCounter(elementId, targetVal) {
    const el = document.getElementById(elementId);
    let current = 0;
    const duration = 900;
    const startTime = performance.now();

    function update(timestamp) {
      const progress = Math.min((timestamp - startTime) / duration, 1);
      const ease = 1 - Math.pow(1 - progress, 3);
      current = Math.round(ease * targetVal);
      el.textContent = current;
      if (progress < 1) {
        requestAnimationFrame(update);
      }
    }
    requestAnimationFrame(update);
  }

  function renderChipsWithShowMore(containerId, btnId, items, chipClass, emptyText, limit = 8) {
    const container = document.getElementById(containerId);
    const btn = document.getElementById(btnId);
    container.innerHTML = '';

    if (!items || items.length === 0) {
      container.innerHTML = `<span style="font-size: 0.8125rem; color: var(--text-muted);">${emptyText}</span>`;
      btn.style.display = 'none';
      return;
    }

    let isExpanded = false;

    function render(showAll) {
      container.innerHTML = '';
      const displayItems = showAll ? items : items.slice(0, limit);

      displayItems.forEach(item => {
        const chip = document.createElement('span');
        chip.className = `chip ${chipClass}`;
        chip.textContent = item;
        container.appendChild(chip);
      });

      if (items.length > limit) {
        btn.style.display = 'inline-block';
        btn.textContent = showAll ? 'Show less' : `Show more (+${items.length - limit})`;
      } else {
        btn.style.display = 'none';
      }
    }

    btn.onclick = () => {
      isExpanded = !isExpanded;
      render(isExpanded);
    };

    render(false);
  }

  function renderRecommendations(data) {
    const list = document.getElementById('detailed-feedback-list');
    list.innerHTML = '';

    const feedbacks = data.detailed_feedback || [];

    if (feedbacks.length > 0) {
      feedbacks.forEach(item => {
        const severity = (item.severity_level || 'low').toLowerCase();
        const card = document.createElement('div');
        card.className = `rec-card ${severity === 'critical' ? 'high' : severity}`;

        const priorityLabel = severity === 'critical' || severity === 'high' ? 'High Priority' : (severity === 'medium' || severity === 'moderate' ? 'Medium Priority' : 'Low Priority');

        card.innerHTML = `
          <div class="rec-top-row">
            <div class="rec-title-group">
              <span class="rec-title">${escapeHtml(item.issue_title || 'Recommendation')}</span>
            </div>
            <span class="rec-priority-badge ${severity === 'critical' ? 'high' : severity}">${priorityLabel}</span>
          </div>
          ${item.explanation ? `<p class="rec-explanation">${escapeHtml(item.explanation)}</p>` : ''}
          ${item.how_to_fix ? `<div class="rec-action-box"><strong>How to Fix:</strong> ${escapeHtml(item.how_to_fix)}</div>` : ''}
          ${item.example_improvement ? `<div class="rec-example">Example: "${escapeHtml(item.example_improvement)}"</div>` : ''}
        `;
        list.appendChild(card);
      });
    } else {
      const suggestions = data.suggestions || [];
      if (suggestions.length > 0) {
        suggestions.forEach((sug, idx) => {
          const card = document.createElement('div');
          card.className = 'rec-card low';
          card.innerHTML = `
            <div class="rec-top-row">
              <span class="rec-title">Suggestion #${idx + 1}</span>
              <span class="rec-priority-badge low">Optimization</span>
            </div>
            <p class="rec-explanation">${escapeHtml(sug)}</p>
          `;
          list.appendChild(card);
        });
      } else {
        list.innerHTML = `
          <div class="rec-card" style="border-left-color: var(--success);">
            <div class="rec-top-row">
              <span class="rec-title">🎉 No critical ATS blockers identified!</span>
              <span class="rec-priority-badge" style="background-color: var(--success-bg); color: var(--success-text); border: 1px solid var(--success-border);">Optimal</span>
            </div>
            <p class="rec-explanation">Your resume structure, keyword distribution, and experience descriptions adhere to ATS best practices.</p>
          </div>
        `;
      }
    }
  }

  // ==========================================================================
  // 7. PDF Report & Text Summary Downloads
  // ==========================================================================
  downloadPdfBtn.addEventListener('click', async () => {
    if (!currentAnalysisData) return;

    downloadPdfBtn.disabled = true;
    const originalText = downloadPdfBtn.innerHTML;
    downloadPdfBtn.innerHTML = '<span>Generating PDF...</span>';

    try {
      const res = await fetch('/api/v1/generate-pdf', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(currentAnalysisData),
      });

      if (!res.ok) throw new Error('PDF generation service failed.');

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `ats_resume_report_${Date.now()}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      showToast('PDF report downloaded successfully!', 'success');
    } catch (e) {
      showToast(e.message || 'Could not download PDF report.', 'danger');
    } finally {
      downloadPdfBtn.disabled = false;
      downloadPdfBtn.innerHTML = originalText;
    }
  });

  downloadSummaryBtn.addEventListener('click', () => {
    if (!currentAnalysisData) return;

    const score = Math.round(currentAnalysisData.ATS_score ?? currentAnalysisData.ats_score ?? 0);
    let summary = `ATS RESUME ANALYSIS REPORT\n`;
    summary += `==========================\n`;
    summary += `Overall ATS Score: ${score}/100\n`;
    summary += `Generated: ${new Date().toLocaleString()}\n\n`;

    if (currentAnalysisData.strengths && currentAnalysisData.strengths.length > 0) {
      summary += `KEY STRENGTHS:\n`;
      currentAnalysisData.strengths.forEach(s => summary += ` - ${s}\n`);
      summary += `\n`;
    }

    if (currentAnalysisData.critical_issues && currentAnalysisData.critical_issues.length > 0) {
      summary += `CRITICAL IMPROVEMENTS:\n`;
      currentAnalysisData.critical_issues.forEach(i => summary += ` - ${i}\n`);
      summary += `\n`;
    }

    if (currentAnalysisData.suggestions && currentAnalysisData.suggestions.length > 0) {
      summary += `SUGGESTIONS:\n`;
      currentAnalysisData.suggestions.forEach(s => summary += ` - ${s}\n`);
    }

    const blob = new Blob([summary], { type: 'text/plain' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ats_summary_${Date.now()}.txt`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
    showToast('Text summary exported.', 'info');
  });

  // ==========================================================================
  // 8. History Modal Interactions
  // ==========================================================================
  navHistoryBtn.addEventListener('click', (e) => {
    e.preventDefault();
    historyModal.classList.add('show');
    loadHistoryData();
  });

  closeHistoryBtn.addEventListener('click', () => {
    historyModal.classList.remove('show');
  });

  historyModal.addEventListener('click', (e) => {
    if (e.target === historyModal) {
      historyModal.classList.remove('show');
    }
  });

  async function loadHistoryData() {
    historyLoading.style.display = 'block';
    historyTableWrap.style.display = 'none';
    historyCardsMobile.style.display = 'none';
    historyEmpty.style.display = 'none';
    historyTableBody.innerHTML = '';
    historyCardsMobile.innerHTML = '';

    try {
      const res = await fetch('/api/v1/history', { headers: getAuthHeaders() });
      historyLoading.style.display = 'none';

      if (res.status === 401) {
        historyEmpty.style.display = 'block';
        historyEmpty.innerHTML = `
          <div class="history-empty-icon">🔒</div>
          <h4>Authentication Required</h4>
          <p style="font-size: 0.84375rem; margin-top: 0.25rem;">Please provide a user session token in localStorage to access saved analyses.</p>
        `;
        return;
      }

      if (!res.ok) throw new Error('Could not load history records.');

      const items = await res.json();
      if (!items || items.length === 0) {
        historyEmpty.style.display = 'block';
        return;
      }

      historyTableWrap.style.display = 'block';
      historyCardsMobile.style.display = 'flex';

      items.forEach(item => {
        const score = Math.round(item.ats_score || 0);
        const dateStr = item.created_at ? new Date(item.created_at).toLocaleDateString() : 'Recent';
        const filename = escapeHtml(item.filename || 'Resume');

        // Desktop Row
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><strong>${filename}</strong></td>
          <td><span class="tier-badge ${score >= 75 ? 'excellent' : 'moderate'}">${score} / 100</span></td>
          <td>${dateStr}</td>
          <td style="text-align: right;">
            <button class="btn-secondary" style="padding: 0.35rem 0.75rem; font-size: 0.75rem; margin-right: 0.4rem;" data-pdf-id="${item.id}">
              📑 PDF
            </button>
            <button class="btn-secondary" style="padding: 0.35rem 0.6rem; font-size: 0.75rem; color: var(--danger);" data-del-id="${item.id}" title="Delete record">
              🗑️
            </button>
          </td>
        `;

        // Mobile Card
        const mobCard = document.createElement('div');
        mobCard.className = 'history-card-item';
        mobCard.innerHTML = `
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <strong>${filename}</strong>
            <span class="tier-badge ${score >= 75 ? 'excellent' : 'moderate'}">${score} / 100</span>
          </div>
          <div style="font-size: 0.75rem; color: var(--text-muted);">${dateStr}</div>
          <div style="display: flex; gap: 0.5rem; margin-top: 0.5rem;">
            <button class="btn-secondary" style="flex: 1; font-size: 0.75rem; padding: 0.4rem;" data-pdf-id="${item.id}">📑 Download PDF</button>
            <button class="btn-secondary" style="font-size: 0.75rem; padding: 0.4rem 0.75rem; color: var(--danger);" data-del-id="${item.id}">🗑️</button>
          </div>
        `;

        // Bind PDF and Delete actions
        [tr, mobCard].forEach(parent => {
          parent.querySelector(`[data-pdf-id="${item.id}"]`)?.addEventListener('click', () => downloadHistoryPdf(item.id, filename));
          parent.querySelector(`[data-del-id="${item.id}"]`)?.addEventListener('click', () => deleteHistoryRecord(item.id, tr, mobCard));
        });

        historyTableBody.appendChild(tr);
        historyCardsMobile.appendChild(mobCard);
      });

    } catch (e) {
      historyLoading.style.display = 'none';
      historyEmpty.style.display = 'block';
      historyEmpty.innerHTML = `<p style="color: var(--danger);">${escapeHtml(e.message)}</p>`;
    }
  }

  async function downloadHistoryPdf(id, filename) {
    try {
      const res = await fetch(`/api/v1/history/${id}/pdf`, { headers: getAuthHeaders() });
      if (!res.ok) throw new Error('PDF retrieval failed.');
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `ats_report_${filename}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      showToast('PDF downloaded successfully.', 'success');
    } catch (e) {
      showToast(e.message || 'Could not download history PDF.', 'danger');
    }
  }

  async function deleteHistoryRecord(id, tr, mobCard) {
    if (!confirm('Are you sure you want to delete this analysis record?')) return;
    try {
      const res = await fetch(`/api/v1/history/${id}`, { method: 'DELETE', headers: getAuthHeaders() });
      if (!res.ok) throw new Error('Delete failed.');
      tr.remove();
      mobCard.remove();
      showToast('Record deleted.', 'info');
    } catch (e) {
      showToast(e.message || 'Could not delete history record.', 'danger');
    }
  }

  // ==========================================================================
  // 9. Methodology Modal Interactions
  // ==========================================================================
  navAboutBtn.addEventListener('click', (e) => {
    e.preventDefault();
    aboutModal.classList.add('show');
  });

  closeAboutBtn.addEventListener('click', () => {
    aboutModal.classList.remove('show');
  });

  aboutModal.addEventListener('click', (e) => {
    if (e.target === aboutModal) {
      aboutModal.classList.remove('show');
    }
  });

  // ==========================================================================
  // 10. Toast Notification System
  // ==========================================================================
  function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const iconSvg = type === 'success'
      ? '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--success)" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg>'
      : (type === 'danger'
        ? '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--danger)" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>'
        : '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--info)" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>');

    toast.innerHTML = `
      ${iconSvg}
      <span style="flex: 1;">${escapeHtml(message)}</span>
    `;

    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(8px)';
      setTimeout(() => toast.remove(), 250);
    }, 4000);
  }

  function escapeHtml(text) {
    if (!text) return '';
    const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
    return String(text).replace(/[&<>"']/g, m => map[m]);
  }
});
