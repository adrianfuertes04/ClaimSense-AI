// InsurTriage AI - Frontend Application
const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' 
  ? 'http://localhost:8000/api/v1' 
  : '/api/v1';

document.addEventListener('DOMContentLoaded', () => {
  // DOM Elements
  const form = document.getElementById('triage-form');
  const submitBtn = document.getElementById('submit-btn');
  const spinner = document.getElementById('spinner');
  const btnText = submitBtn.querySelector('.btn-text');
  
  const imageUpload = document.getElementById('image-upload');
  const dropzone = document.getElementById('dropzone');
  const previewGallery = document.getElementById('image-previews-container');
  const previewList = document.getElementById('file-preview-list');
  const docUpload = document.getElementById('doc-upload');
  const docName = document.getElementById('doc-name');
  const removeDocBtn = document.getElementById('remove-doc-btn');
  const descriptionInput = document.getElementById('description');
  const policyTypeSelect = document.getElementById('policy-type');

  const emptyState = document.getElementById('empty-state');
  const resultsContent = document.getElementById('results-content');
  const claimBadge = document.getElementById('claim-id-badge');
  const copyJsonBtn = document.getElementById('copy-json-btn');
  const resetFormBtn = document.getElementById('reset-form-btn');

  const liveStepper = document.getElementById('live-stepper');
  const stepperStatusText = document.getElementById('stepper-status-text');

  // State
  let selectedFiles = [];
  let currentReportData = null;
  let currentTraceData = null;
  let activeTraceFilter = 'all';

  // Check API health on load
  checkHealth();

  // Presets definition
  const presets = {
    water: {
      desc: "A burst supply pipe beneath the kitchen sink flooded the entire kitchen floor, causing drywall dampness and floor baseboard swelling.",
      policy: "standard_homeowner"
    },
    fire: {
      desc: "An unattended frying pan sparked grease flames that scorched the kitchen cabinets and spread dense smoke damage into the living room ceiling.",
      policy: "premium_homeowner"
    },
    storm: {
      desc: "Severe gale-force windstorm blew off multiple roof shingles, causing exterior damage and ceiling water leakage into the attic.",
      policy: "standard_homeowner"
    },
    break_in: {
      desc: "Forced entry through the rear sliding glass door; door frame splintered, lock mechanism broken, and hallway drywall vandalized.",
      policy: "standard_homeowner"
    },
    pii: {
      desc: "Claimant submitted a photo of a credit card alongside repair invoice for water damage compensation.",
      policy: "standard_homeowner"
    },
    pet: {
      desc: "Claimant submitted a photo of their family dog resting on a clean living room rug.",
      policy: "standard_homeowner"
    }
  };

  // Preset buttons handler
  document.querySelectorAll('.preset-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const type = btn.dataset.preset;
      if (presets[type]) {
        descriptionInput.value = presets[type].desc;
        policyTypeSelect.value = presets[type].policy;
        descriptionInput.focus();
        btn.classList.add('active');
        setTimeout(() => btn.classList.remove('active'), 500);
      }
    });
  });

  // Reset form handler
  if (resetFormBtn) {
    resetFormBtn.addEventListener('click', () => {
      form.reset();
      selectedFiles = [];
      renderImagePreviews();
      docName.textContent = 'Attach adjuster or contractor PDF report...';
      docName.style.color = '';
      removeDocBtn.classList.add('hidden');
      emptyState.classList.remove('hidden');
      resultsContent.classList.add('hidden');
      claimBadge.classList.add('hidden');
      copyJsonBtn.classList.add('hidden');
    });
  }

  // Drag & drop highlight
  ['dragenter', 'dragover'].forEach(name => {
    dropzone.addEventListener(name, (e) => {
      e.preventDefault();
      dropzone.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach(name => {
    dropzone.addEventListener(name, (e) => {
      e.preventDefault();
      dropzone.classList.remove('dragover');
    });
  });

  dropzone.addEventListener('drop', (e) => {
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleNewFiles(Array.from(e.dataTransfer.files));
    }
  });

  imageUpload.addEventListener('change', () => {
    if (imageUpload.files && imageUpload.files.length > 0) {
      handleNewFiles(Array.from(imageUpload.files));
    }
  });

  function handleNewFiles(files) {
    const validImages = files.filter(f => f.type.startsWith('image/'));
    selectedFiles.push(...validImages);
    renderImagePreviews();
  }

  function renderImagePreviews() {
    if (selectedFiles.length === 0) {
      previewGallery.classList.add('hidden');
      previewGallery.innerHTML = '';
      previewList.innerHTML = '';
      return;
    }

    previewGallery.classList.remove('hidden');
    previewGallery.innerHTML = '';
    previewList.innerHTML = '';

    selectedFiles.forEach((file, index) => {
      // Card with real thumbnail
      const card = document.createElement('div');
      card.className = 'image-preview-card';

      const tagBadge = document.createElement('span');
      tagBadge.className = 'image-tag-badge';
      tagBadge.textContent = index === 0 ? 'Primary' : `View #${index + 1}`;
      card.appendChild(tagBadge);

      const removeBtn = document.createElement('button');
      removeBtn.type = 'button';
      removeBtn.className = 'btn-remove-preview';
      removeBtn.innerHTML = '&times;';
      removeBtn.title = 'Remove photo';
      removeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        selectedFiles.splice(index, 1);
        renderImagePreviews();
      });
      card.appendChild(removeBtn);

      const img = document.createElement('img');
      img.className = 'image-preview-thumb';
      img.alt = file.name;
      img.src = URL.createObjectURL(file);
      card.appendChild(img);

      const meta = document.createElement('div');
      meta.className = 'image-preview-meta';
      meta.innerHTML = `
        <span class="image-preview-name" title="${file.name}">${file.name}</span>
        <span class="image-preview-size">${Math.round(file.size / 1024)} KB</span>
      `;
      card.appendChild(meta);

      previewGallery.appendChild(card);
    });
  }

  // Handle PDF file selection
  docUpload.addEventListener('change', () => {
    if (docUpload.files.length > 0) {
      const doc = docUpload.files[0];
      docName.textContent = `📄 ${doc.name} (${Math.round(doc.size / 1024)} KB)`;
      docName.style.color = '#a5b4fc';
      removeDocBtn.classList.remove('hidden');
    } else {
      docName.textContent = 'Attach adjuster or contractor PDF report...';
      docName.style.color = '';
      removeDocBtn.classList.add('hidden');
    }
  });

  removeDocBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    docUpload.value = '';
    docName.textContent = 'Attach adjuster or contractor PDF report...';
    docName.style.color = '';
    removeDocBtn.classList.add('hidden');
  });

  // Copy JSON handler
  copyJsonBtn.addEventListener('click', () => {
    if (!currentReportData) return;
    const jsonStr = JSON.stringify({
      triage_report: currentReportData,
      agent_trace: currentTraceData
    }, null, 2);

    navigator.clipboard.writeText(jsonStr).then(() => {
      const origText = copyJsonBtn.innerHTML;
      copyJsonBtn.textContent = '✔ Copied!';
      setTimeout(() => copyJsonBtn.innerHTML = origText, 2000);
    });
  });

  // Handle Form Submission
  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const desc = descriptionInput.value.trim();
    const doc = docUpload.files[0];
    const policyType = policyTypeSelect.value;

    if (selectedFiles.length === 0 && !desc) {
      alert('Please provide either at least one damage photo or an incident description.');
      return;
    }

    // Set UI loading state
    submitBtn.disabled = true;
    spinner.classList.remove('hidden');
    btnText.textContent = 'Executing Autonomous ReAct Triage...';
    liveStepper.classList.remove('hidden');

    // Start progress stage simulation
    let stageIndex = 0;
    const stages = [
      'Validating intake guardrails (PII, clarity, property damage)...',
      'Executing ReAct Cycle 1: Querying Qdrant vector database for historical claims...',
      'Executing ReAct Cycle 2: Verifying policy terms and coverage limits...',
      'Executing ReAct Cycle 3: Calculating actuarial repair cost matrix...',
      'Executing Output Safety Agent: Sanitizing recommendation & final synthesis...'
    ];
    stepperStatusText.textContent = stages[0];
    const stageTimer = setInterval(() => {
      stageIndex = (stageIndex + 1) % stages.length;
      stepperStatusText.textContent = stages[stageIndex];
    }, 2800);

    const formData = new FormData();
    if (selectedFiles.length === 1) {
      formData.append('image', selectedFiles[0]);
    } else if (selectedFiles.length > 1) {
      selectedFiles.forEach(file => {
        formData.append('images', file);
      });
    }

    if (desc) formData.append('description', desc);
    if (doc) formData.append('document', doc);
    if (policyType) formData.append('policy_type', policyType);

    try {
      const response = await fetch(`${API_BASE}/claims/triage`, {
        method: 'POST',
        body: formData
      });

      const data = await response.json();
      currentReportData = data;

      if (!response.ok) {
        handleErrorResponse(response.status, data);
      } else {
        renderTriageReport(data);
        if (data.claim_id) {
          fetchAndRenderTrace(data.claim_id);
        }
      }
    } catch (err) {
      console.error('Submission failed:', err);
      alert('Network error connecting to triage API.');
    } finally {
      clearInterval(stageTimer);
      submitBtn.disabled = false;
      spinner.classList.add('hidden');
      liveStepper.classList.add('hidden');
      btnText.textContent = 'Execute Autonomous Triage';
    }
  });

  async function checkHealth() {
    try {
      const res = await fetch(`${API_BASE}/health`);
      if (res.ok) {
        const h = await res.json();
        const badge = document.getElementById('system-health');
        if (badge) {
          const v = h.services?.vector_db === 'connected' ? 'Vector DB Ready' : 'Syncing';
          badge.innerHTML = `<span class="status-dot"></span> API Active (${v})`;
        }
      }
    } catch (e) {
      const badge = document.getElementById('system-health');
      if (badge) {
        badge.style.background = 'rgba(239, 68, 68, 0.1)';
        badge.style.color = '#f87171';
        badge.innerHTML = '⚠ API Disconnected';
      }
    }
  }

  function handleErrorResponse(status, data) {
    emptyState.classList.add('hidden');
    resultsContent.classList.remove('hidden');
    copyJsonBtn.classList.remove('hidden');

    const banner = document.getElementById('validation-banner');
    const headline = document.getElementById('val-headline');
    const icon = document.getElementById('val-icon');
    const flagsGrid = document.getElementById('val-flags');

    banner.className = 'assessment-banner failed';
    icon.className = 'icon-indicator error';
    icon.textContent = '✖';
    headline.textContent = `Submission Rejected (HTTP ${status}): ${data.message || data.error || 'Validation failed'}`;

    flagsGrid.innerHTML = '';
    const intake = data.intake_validation || {};
    for (const [key, val] of Object.entries(intake)) {
      const flagDiv = document.createElement('div');
      flagDiv.className = 'flag-item';
      flagDiv.innerHTML = `<span class="flag-icon">${val === true ? '✔' : '✖'}</span> <strong>${key}</strong>: ${val}`;
      flagsGrid.appendChild(flagDiv);
    }
  }

  function renderTriageReport(data) {
    emptyState.classList.add('hidden');
    resultsContent.classList.remove('hidden');

    claimBadge.classList.remove('hidden');
    claimBadge.textContent = `Claim ID: ${data.claim_id}`;
    copyJsonBtn.classList.remove('hidden');

    // 1. Validation Banner
    const banner = document.getElementById('validation-banner');
    const headline = document.getElementById('val-headline');
    const icon = document.getElementById('val-icon');
    const flagsGrid = document.getElementById('val-flags');

    banner.className = 'assessment-banner';
    icon.className = 'icon-indicator success';
    icon.textContent = '✔';
    headline.textContent = 'Intake Guardrails & Multimodal Vision Verified';

    flagsGrid.innerHTML = '';
    const intake = data.intake_validation || {};
    for (const [key, val] of Object.entries(intake)) {
      const flagDiv = document.createElement('div');
      flagDiv.className = 'flag-item';
      const mark = val === true ? '✔' : (val === null ? 'ℹ' : '✖');
      flagDiv.innerHTML = `<span class="flag-icon">${mark}</span> ${key}: <em>${val}</em>`;
      flagsGrid.appendChild(flagDiv);
    }

    // 2. Assessment KPI Highlights
    const a = data.triage_assessment || {};
    const damageType = a.damage_type || 'other';
    document.getElementById('res-damage-type').textContent = damageType.replace('_', ' ');

    const iconMap = {
      water_damage: '💧',
      fire_damage: '🔥',
      storm_damage: '🌪️',
      break_in: '🚪',
      vandalism: '🎨',
      other: '🏚️'
    };
    document.getElementById('res-damage-icon').textContent = iconMap[damageType] || '💥';

    const severityEl = document.getElementById('res-severity');
    severityEl.textContent = a.severity || 'moderate';

    const urgencyEl = document.getElementById('res-urgency');
    const urgencyVal = (a.urgency || 'medium').toLowerCase();
    urgencyEl.textContent = urgencyVal;
    urgencyEl.className = `urgency-pill urgency-${urgencyVal}`;

    // Estimated Cost & Spectrum
    const cost = a.estimated_repair_cost;
    const costEl = document.getElementById('res-cost');
    const spectrumText = document.getElementById('cost-spectrum-text');
    const spectrumFill = document.getElementById('spectrum-fill');
    const deductibleMarker = document.getElementById('deductible-marker');

    if (cost && cost.min !== undefined && cost.max !== undefined) {
      const minStr = cost.min.toLocaleString('en-US');
      const maxStr = cost.max.toLocaleString('en-US');
      costEl.textContent = `$${minStr} - $${maxStr} ${cost.currency || 'USD'}`;
      spectrumText.innerHTML = `Min: $${minStr} &bull; Max: $${maxStr} USD`;
      
      const widthPct = Math.min(100, Math.max(25, (cost.max / 25000) * 100));
      spectrumFill.style.width = `${widthPct}%`;

      // Deductible ($1500) position relative to max
      const dedPct = Math.min(85, Math.max(10, (1500 / Math.max(1500, cost.max)) * 100));
      deductibleMarker.style.left = `${dedPct}%`;
    } else {
      costEl.textContent = '-';
      spectrumText.textContent = '$0 - $0 USD';
    }

    // 3. Affected Areas Chips
    const areasList = document.getElementById('res-areas');
    areasList.innerHTML = '';
    (a.affected_areas || []).forEach(area => {
      const chip = document.createElement('span');
      chip.className = 'area-chip';
      chip.textContent = area.replace('_', ' ');
      areasList.appendChild(chip);
    });

    // 4. Description & Recommendation
    document.getElementById('res-description').textContent = a.damage_description || 'No description provided.';
    document.getElementById('res-recommendation').textContent = a.recommendation || 'No recommendation provided.';

    // 5. Output Safety Checklist
    const safetyGrid = document.getElementById('safety-checklist');
    safetyGrid.innerHTML = '';
    const safety = data.safety_checks || {};
    const safetyLabels = {
      no_coverage_promises: 'No Binding Coverage Promises',
      no_legal_advice: 'No Legal Counsel Provided',
      no_settlement_amounts: 'No Fixed Settlement Payouts',
      no_liability_determination: 'No Liability / Fault Assigned',
      no_emotional_language: 'Professional & Neutral Tone'
    };

    for (const [key, label] of Object.entries(safetyLabels)) {
      const isOk = safety[key] !== false;
      const item = document.createElement('div');
      item.className = `safety-item ${isOk ? 'checked' : ''}`;
      item.innerHTML = `<span class="safety-check-icon">${isOk ? '✔' : '✖'}</span> ${label}`;
      safetyGrid.appendChild(item);
    }

    // 6. Citations (Vector RAG)
    const citList = document.getElementById('res-citations');
    citList.innerHTML = '';
    (a.similar_past_claims || []).forEach(c => {
      const card = document.createElement('div');
      card.className = 'citation-card';
      const pct = Math.round((c.similarity_score || 0) * 100);
      card.innerHTML = `
        <div class="citation-meta">
          <span class="citation-id">${c.claim_id}</span>
          <span class="citation-summary">${c.resolution_summary || 'Historical claim precedent'}</span>
        </div>
        <div class="citation-score-badge">
          <span class="citation-score">${pct}% Match</span>
          <div class="score-bar-mini">
            <div class="score-bar-mini-fill" style="width: ${pct}%"></div>
          </div>
        </div>
      `;
      citList.appendChild(card);
    });
  }

  async function fetchAndRenderTrace(claimId) {
    try {
      const res = await fetch(`${API_BASE}/agent/trace/${claimId}`);
      if (!res.ok) return;
      const trace = await res.json();
      currentTraceData = trace;

      document.getElementById('res-duration').textContent = `${trace.total_duration_ms || 0} ms`;
      const steps = trace.steps || [];
      document.getElementById('res-steps-count').textContent = `${steps.length} ReAct steps`;

      renderTraceSteps(steps);
      setupTraceFilterListeners(steps);
    } catch (e) {
      console.warn('Could not fetch trace:', e);
    }
  }

  function setupTraceFilterListeners(steps) {
    document.querySelectorAll('.trace-filter-btn').forEach(btn => {
      btn.onclick = () => {
        document.querySelectorAll('.trace-filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        activeTraceFilter = btn.dataset.filter;
        renderTraceSteps(steps);
      };
    });
  }

  function renderTraceSteps(steps) {
    const timeline = document.getElementById('res-trace-timeline');
    timeline.innerHTML = '';

    const filtered = steps.filter(step => {
      if (activeTraceFilter === 'all') return true;
      return step.type === activeTraceFilter;
    });

    filtered.forEach(step => {
      const stepDiv = document.createElement('div');
      stepDiv.className = `timeline-step step-${step.type}`;

      let detailsHtml = '';
      if (step.type === 'act' && step.tool_input) {
        detailsHtml = `
          <div class="timeline-step-details">
            <span class="tool-name-tag">Tool Call: ${step.tool_name}</span><br>
            ${JSON.stringify(step.tool_input, null, 2)}
          </div>
        `;
      } else if (step.type === 'observe' && step.tool_output) {
        detailsHtml = `
          <div class="timeline-step-details">
            <span class="tool-name-tag">Observation Payload:</span><br>
            ${JSON.stringify(step.tool_output, null, 2)}
          </div>
        `;
      }

      stepDiv.innerHTML = `
        <div class="timeline-step-header">
          <div class="timeline-step-type">Step ${step.step_number}: ${step.type}</div>
          <span class="timeline-step-time">${step.timestamp ? step.timestamp.substring(11, 19) : ''}</span>
        </div>
        <div class="timeline-step-content">${step.content}</div>
        ${detailsHtml}
      `;
      timeline.appendChild(stepDiv);
    });
  }
});
