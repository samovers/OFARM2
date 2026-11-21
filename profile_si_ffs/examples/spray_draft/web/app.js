const $ = (id) => document.getElementById(id);
const state = { db: null, catalog: null, catalogSha: null, entries: [], selected: null, correcting: null, syncing: false, syncRequested: false, connected: false,
  retryableIds: new Set(), retryTimer: null, retryDelay: 2000 };
const fields = ['job', 'example-evidence', 'product', 'dose', 'unit', 'liquid-kind', 'application-volume', 'volume-unit', 'parcel', 'crop', 'performer', 'method', 'treatment-target', 'start', 'end'];
const fieldNames = ['Example job', 'Example evidence', 'Product', 'Dose', 'Dose unit', 'Liquid measured', 'Water or mixture per hectare', 'Liquid unit', 'Parcel', 'Crop', 'Who sprayed', 'Spraying method', 'Treatment target', 'Start', 'Finish'];
const issueFields = { jobId: 'job', exampleEvidenceSetId: 'example-evidence', productId: 'product', dose: 'dose', unitId: 'unit',
  'applicationVolume.liquidId': 'liquid-kind', 'applicationVolume.value': 'application-volume', 'applicationVolume.unitId': 'volume-unit',
  parcelId: 'parcel', cropId: 'crop', performerId: 'performer', methodId: 'method', treatmentTargetId: 'treatment-target', start: 'start', end: 'end' };
const zone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';

function element(tag, text, className) {
  const el = document.createElement(tag);
  if (text !== undefined) el.textContent = text;
  if (className) el.className = className;
  return el;
}
function notice(message, error = false) {
  $('notice').textContent = message;
  $('notice').className = 'notice' + (error ? ' error' : '');
  $('notice').hidden = !message;
}
function localMinute(date) {
  const pad = (v) => String(v).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}
function toInstant(value) {
  const date = new Date(value);
  // A daylight-saving gap must not silently move the entered clock time.
  return Number.isFinite(date.getTime()) && localMinute(date) === value ? date.toISOString() : '';
}
function humanTime(value) {
  const date = new Date(value);
  return value && Number.isFinite(date.getTime()) ? new Intl.DateTimeFormat('en-GB', {
    dateStyle: 'medium', timeStyle: 'short', timeZone: zone
  }).format(date) : value || 'Not entered';
}
async function hash(raw) {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(raw));
  return [...new Uint8Array(digest)].map(v => v.toString(16).padStart(2, '0')).join('');
}
function openDatabase() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('ofarm-spray-draft-rehearsal-v1', 1);
    request.onupgradeneeded = () => {
      request.result.createObjectStore('outbox', { keyPath: 'id' });
      request.result.createObjectStore('settings');
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
    request.onblocked = () => reject(new Error('Close another test-app tab and retry.'));
  });
}
function dbRequest(store, method, ...args) {
  return new Promise((resolve, reject) => {
    const transaction = state.db.transaction(store, ['get', 'getAll'].includes(method) ? 'readonly' : 'readwrite');
    const request = transaction.objectStore(store)[method](...args);
    transaction.oncomplete = () => resolve(request.result);
    transaction.onerror = () => reject(transaction.error || request.error);
    transaction.onabort = () => reject(transaction.error || new Error('Browser storage was not saved.'));
  });
}
async function request(path, options = {}) {
  let response, value;
  try {
    response = await fetch(path, { ...options, cache: 'no-store', signal: AbortSignal.timeout(path.startsWith('/api/drafts') ? 45000 : 10000) });
    value = await response.json();
  } catch (error) {
    // Only transport failures are temporary. Malformed JSON and later reply
    // guard/storage failures must not start automatic retries.
    if (error instanceof TypeError || ['TimeoutError', 'AbortError'].includes(error.name)) error.retryable = true;
    throw error;
  }
  if (!response.ok) throw Object.assign(new Error(value?.error || 'This draft could not be synced.'), { retryable: response.status >= 500 });
  return value;
}
function fillSelect(id, rows, blank = '') {
  const select = $(id);
  select.replaceChildren();
  if (blank) select.add(new Option(blank, ''));
  for (const row of rows || []) select.add(new Option(row.label, row.id));
}
function label(group, id, capture) {
  if (!id) return 'Not recorded';
  const saved = state.entries.find(entry => entry.id === capture.draftId)?.response?.displayLabels?.[group];
  if (saved?.id === id) return saved.label;
  if (capture.catalogSha256 !== state.catalogSha) return id || 'Not entered';
  const catalogGroup = group === 'applicationVolumeUnits' ? 'units' : group;
  return state.catalog[catalogGroup]?.find(row => row.id === id)?.label || id || 'Not entered';
}
function formValues() { return Object.fromEntries(fields.map(id => [id, $(id).value])); }
function saveWorkingForm() {
  return dbRequest('settings', 'put', { ...formValues(), catalogSha256: state.catalogSha, corrects: state.correcting }, 'working-entry').catch(() => notice('The unfinished form could not be stored. Keep this tab open and save your draft.', true));
}
function setForm(value) {
  for (const id of fields) if (typeof value?.[id] === 'string') $(id).value = value[id];
  showEntryJob();
  showEvidencePreview();
}
function captureForm(capture) {
  return { job: capture.jobId || '', 'example-evidence': capture.exampleEvidenceSetId || '',
    product: capture.productId, dose: capture.dose.value, unit: capture.dose.unitId,
    'liquid-kind': capture.applicationVolume?.liquidId || '', 'application-volume': capture.applicationVolume?.value || '',
    'volume-unit': capture.applicationVolume?.unitId || 'litres-per-hectare', parcel: capture.parcelId, crop: capture.cropId,
    performer: capture.performerId || '', method: capture.methodId || '', 'treatment-target': capture.treatmentTargetId || '',
    start: capture.event.startLocal, end: capture.event.endLocal };
}
function blankForm() {
  return { ...Object.fromEntries(fields.map(id => [id, ''])), unit: state.catalog.units[0]?.id || '', 'volume-unit': 'litres-per-hectare' };
}
function sameForm(left, right) { return fields.every(id => left[id] === right[id]); }
function hasUnfinishedWork() {
  const values = formValues();
  if (!state.correcting && sameForm(values, blankForm())) return false;
  return !state.entries.some(entry => {
    if (state.correcting && (entry.id !== state.correcting.id || entry.sha256 !== state.correcting.sha256)) return false;
    const capture = JSON.parse(entry.raw);
    return capture.catalogSha256 === state.catalogSha && sameForm(values, captureForm(capture));
  });
}
function disableNewRecord(disabled) {
  for (const id of ['new-record', 'new-record-review']) $(id).disabled = disabled;
}
async function startNewRecord() {
  if ($('entry-fields').disabled) return;
  if (hasUnfinishedWork() && !window.confirm('Clear this unfinished form and start a new spray record?\n\nCancel keeps your work. OK clears only this form. Saved drafts will stay unchanged.')) return;
  const values = blankForm();
  $('entry-fields').disabled = true; disableNewRecord(true);
  let started = false;
  try {
    // Store the blank working form first. If storage fails, keep visible work.
    await dbRequest('settings', 'put', { ...values, catalogSha256: state.catalogSha, corrects: null }, 'working-entry');
    setForm(values); fields.forEach(clearFieldError);
    state.correcting = null; state.selected = null;
    $('correction-context').hidden = true; $('review').hidden = true;
    for (const id of ['entry-background', 'example-evidence-preview']) $(id).open = false;
    $('save').disabled = false; $('save').textContent = 'Save draft and check →';
    renderList();
    notice('New spray record ready. Your saved drafts are still in Your drafts.');
    started = true;
  } catch {
    notice('The new form could not be stored. Your unfinished entry is kept; keep this tab open and retry.', true);
  } finally {
    $('entry-fields').disabled = false; disableNewRecord(false);
  }
  if (started) { $('job').focus({ preventScroll: true }); $('entry-title').scrollIntoView({ block: 'start' }); }
}
function correctionParent(entry) {
  return state.entries.find(row => row.id !== entry.id && row.id === entry.corrects?.id && row.sha256 === entry.corrects.sha256);
}
function correctionChanges(entry) {
  const parent = correctionParent(entry);
  if (!parent) return [];
  const before = JSON.parse(parent.raw), after = JSON.parse(entry.raw), oldForm = captureForm(before), newForm = captureForm(after);
  const groups = { job: 'jobs', 'example-evidence': 'exampleEvidenceSets', product: 'products', unit: 'units', 'liquid-kind': 'applicationLiquids',
    'volume-unit': 'units', parcel: 'parcels', crop: 'crops', performer: 'performers', method: 'methods', 'treatment-target': 'treatmentTargets' };
  const display = (id, value, capture) => groups[id] ? label(groups[id], value, capture) : value || 'Not entered';
  const changes = fields.flatMap((id, index) => oldForm[id] === newForm[id] ? []
    : [`${fieldNames[index]}: ${display(id, oldForm[id], before)} → ${display(id, newForm[id], after)}`]);
  if (before.catalogSha256 !== after.catalogSha256) changes.push('Example list version changed');
  return changes;
}
function actionButton(text, action) {
  const button = element('button', text, 'inline-action'); button.type = 'button';
  button.addEventListener('click', action); return button;
}
function showCorrection(entry) {
  const parent = correctionParent(entry), children = state.entries.filter(row => correctionParent(row)?.id === entry.id);
  const panel = $('review-correction'); panel.replaceChildren(); panel.hidden = !entry.corrects && !children.length;
  if (entry.corrects) {
    panel.append(element('h3', 'Corrected copy — both drafts are kept'));
    const changes = correctionChanges(entry), list = element('ul');
    for (const change of changes) list.append(element('li', change));
    panel.append(list);
    if (parent) {
      if (!changes.length) panel.append(element('p', 'No entered details changed in this copy.'));
      panel.append(actionButton('View the original draft', () => showReview(parent.id, true)));
    } else panel.append(element('p', 'The original for this correction is unavailable in this browser.'));
  }
  for (const child of children) panel.append(actionButton('View a corrected copy', () => showReview(child.id, true)));
}
function issueControl(issue) {
  // A differing number identifies its input. An unsupported rule may instead
  // concern product, material or unit, so do not guess a field to fix.
  if (issue.code === 'EXAMPLE_AMOUNT_DIFFERENCE') return { 'amountRules.product': 'dose', 'amountRules.water': 'application-volume' }[issue.field];
  return issueFields[issue.field] || (issue.field.startsWith('job.') ? issueFields[issue.field.slice(4)] : null)
    || (issue.field.startsWith('exampleEvidence.') ? 'example-evidence' : null);
}
function clearFieldError(id) {
  const control = $(id), errorId = id + '-error';
  $(errorId)?.remove(); control.removeAttribute('aria-invalid');
  const descriptions = (control.getAttribute('aria-describedby') || '').split(' ').filter(value => value && value !== errorId);
  if (descriptions.length) control.setAttribute('aria-describedby', descriptions.join(' ')); else control.removeAttribute('aria-describedby');
}
function showFieldErrors(entry) {
  fields.forEach(clearFieldError);
  const original = captureForm(JSON.parse(entry.raw));
  for (const issue of entry.response?.issues || []) {
    const id = issueControl(issue);
    if (!id || issue.level !== 'error' || $(id).value !== original[id]) continue;
    const errorId = id + '-error';
    if ($(errorId)) { $(errorId).textContent += ' ' + issue.message; continue; }
    const message = element('p', issue.message, 'field-error'); message.id = errorId;
    $(id).closest('.field').append(message); $(id).setAttribute('aria-invalid', 'true');
    $(id).setAttribute('aria-describedby', [$(id).getAttribute('aria-describedby'), errorId].filter(Boolean).join(' '));
  }
}
function correctDraft(controlId) {
  const entry = state.entries.find(row => row.id === state.selected);
  if (!entry || $('entry-fields').disabled) return;
  const capture = JSON.parse(entry.raw);
  const continuing = state.correcting?.id === entry.id && state.correcting.sha256 === entry.sha256;
  // Another fix link for this original only moves focus; keep edits already made.
  if (!continuing) {
    const values = captureForm(capture);
    if (capture.catalogSha256 !== state.catalogSha) { values.job = ''; values['example-evidence'] = ''; }
    state.correcting = { id: entry.id, sha256: entry.sha256 };
    setForm(values);
  }
  showFieldErrors(entry); $('correction-context').hidden = false;
  $('save').disabled = false; $('save').textContent = 'Save corrected copy →';
  notice('Edit the form and save a new draft. The original draft will stay unchanged.');
  if (!continuing && (capture.jobId || capture.exampleEvidenceSetId) && capture.catalogSha256 !== state.catalogSha)
    notice('The example list has changed. Choose the job version and any fictional notes again for this new copy. The original keeps its saved version.');
  saveWorkingForm();
  const firstError = (entry.response?.issues || []).find(issue => issue.level === 'error' && issueControl(issue));
  const target = $(controlId || (firstError && issueControl(firstError)) || 'product');
  target.focus({ preventScroll: true }); target.scrollIntoView({ block: 'center' });
}
function showQuickChecks(report) {
  const amounts = $('amount-outcomes'); amounts.replaceChildren();
  for (const check of report?.exampleAmountChecks || []) {
    const row = element('li'); row.append(element('div', check.label), element('span',
      { MATCH: 'Matches example', DIFFERENT: 'Different from example', NOT_CHECKED: 'Not checked' }[check.status])); amounts.append(row);
  }
  if (!amounts.children.length) amounts.append(element('li', report ? 'No example amount rules linked.' : 'Waiting for sync.'));
  const conditions = $('condition-outcomes'); conditions.replaceChildren();
  for (const condition of report?.jobConditions || []) {
    const link = report.exampleConditionEvidence?.links.find(row => row.conditionId === condition.id);
    const phase = { START: 'Start', IN_PROGRESS: 'During spraying', FINISH: 'Finish' }[condition.phase];
    const row = element('li'); row.append(element('strong', `${phase} — unverified`), element('span',
      link?.status === 'EXAMPLE_LINKED' ? 'Fictional note linked' : link?.status === 'CONTEXT_MISMATCH' ? 'Different example; note not linked'
        : link?.status === 'INVALID_EXAMPLE' ? 'Note not usable; not linked' : 'No note linked'));
    conditions.append(row);
  }
  if (!conditions.children.length) conditions.append(element('li', report ? 'No job conditions linked.' : 'Waiting for sync. Conditions are unverified.'));
}
function showEvidencePreview() {
  const selected = state.catalog?.exampleEvidenceSets?.find(row => row.id === $('example-evidence').value);
  $('example-evidence-preview').hidden = !selected;
  $('example-evidence-notes').replaceChildren();
  if (!selected) return;
  $('example-evidence-notes').append(element('p', selected.qualification));
  for (const note of selected.records) {
    $('example-evidence-notes').append(element('p', note.originalText), element('p', note.limitations, 'hint'));
  }
}
function showConditionEvidence(report) {
  const parent = $('review-condition-evidence'); parent.replaceChildren();
  parent.append(element('h3', 'Example evidence links'));
  const evidence = report?.exampleConditionEvidence;
  if (!evidence?.selection) {
    parent.append(element('p', report ? 'No fictional notes were selected for this draft. The job conditions remain unverified.'
      : 'Waiting for sync. No example evidence links have been checked yet.'));
    return;
  }
  parent.append(element('p', evidence.evidenceSet?.label || 'Selected example notes unavailable'),
    element('p', 'These notes are fictional. Linking them does not verify a condition or approve the job.'));
  const list = element('ul');
  for (const link of evidence.links) {
    const phase = { START: 'Start', IN_PROGRESS: 'During spraying', FINISH: 'Finish' }[link.phase];
    const status = { EXAMPLE_LINKED: 'Fictional note linked', NO_EXAMPLE: 'No note linked',
      CONTEXT_MISMATCH: 'Different example — not linked', INVALID_EXAMPLE: 'Note not usable — not linked' }[link.status] || 'Not linked';
    const item = element('li'); item.append(element('strong', `${phase} — ${status}`), element('p', link.message));
    if (link.record) {
      item.append(element('p', link.record.supports), element('p', link.record.limitations));
      const original = element('details', undefined, 'original');
      original.append(element('summary', 'Read original fictional note'), element('pre', link.record.originalText),
        element('p', `Example observation time: ${link.record.observedAt}`),
        element('p', `Original text SHA-256: ${link.record.originalTextSha256}`));
      item.append(original);
    }
    list.append(item);
  }
  parent.append(list);
}
function showEntryJob() {
  const job = state.catalog?.jobs?.find(row => row.id === $('job').value);
  $('entry-background').hidden = !job;
  showJob($('entry-job'), job);
  const parent = $('entry-amount-rules');
  const rules = Object.values(state.catalog?.exampleAmountRules || {}).filter(rule => rule?.jobId === job?.id && rule?.jobRevision === job?.revision);
  parent.replaceChildren(); parent.hidden = !rules.length;
  if (!rules.length) return;
  parent.append(element('h3', 'Separate example amount rules'), element('p', 'For this made-up job only. These numbers are not safety limits or permission to spray.'));
  const list = element('ul');
  for (const rule of rules) list.append(element('li', `${rule.label}: ${rule.meaning}`));
  parent.append(list);
}
function showAmountResults(report) {
  const parent = $('review-amount-rules'); parent.replaceChildren();
  parent.append(element('h3', 'Example amount checks'));
  const checks = report?.exampleAmountChecks || [];
  if (!checks.length) {
    parent.append(element('p', report ? 'No separate example amount rules were selected for this draft.' : 'Waiting for sync. The example amount checks have not run.'));
    return;
  }
  parent.append(element('p', 'These checks compare entered numbers with a made-up example. They do not approve spraying or prove the amounts used.'));
  const list = element('ul');
  for (const check of checks) {
    const result = { MATCH: 'Matches example', DIFFERENT: 'Different from example', NOT_CHECKED: 'Not checked' }[check.status] || 'Not checked';
    const item = element('li');
    item.append(element('strong', `${check.label} — ${result}`), element('p', check.message));
    if (check.rule?.label) item.append(element('p', `${check.rule.label}: ${check.rule.meaning}`, 'hint'));
    list.append(item);
  }
  parent.append(list);
}
function showJob(parent, job, empty = '') {
  parent.replaceChildren();
  parent.hidden = !job && !empty;
  if (!job) { if (empty) parent.append(element('p', empty)); return; }
  parent.append(element('h3', job.label), element('p', job.summary), element('p', job.qualification));
  const plan = element('ul');
  for (const step of job.procedure.instructions) plan.append(element('li', step));
  parent.append(plan, element('p', 'Job conditions — not checked. Choosing this job or reviewing the draft does not prove these happened.'));
  const conditions = element('ul');
  for (const condition of job.conditions) {
    const phase = { START: 'Start', IN_PROGRESS: 'During spraying', FINISH: 'Finish' }[condition.phase];
    conditions.append(element('li', `${phase}: ${condition.meaning} — Not checked`));
  }
  parent.append(conditions);
}
function setConnection() {
  const pending = state.entries.filter(entry => !entry.response).length;
  $('connection').textContent = !navigator.onLine ? `Offline · ${pending ? pending + ' draft(s) waiting to sync' : 'drafts stay on this device'}`
    : state.connected ? `Connected to this computer${pending ? ' · ' + pending + ' waiting to sync' : ' · drafts synced'}`
    : 'Local server unavailable · drafts stay on this device';
  $('connection-dot').classList.toggle('online', state.connected && navigator.onLine);
  $('sync').disabled = state.syncing;
}
function rowState(entry) {
  if (!entry.response && state.retryableIds.has(entry.id)) return 'Saved on device · retrying automatically';
  if (!entry.response) return entry.error ? 'Saved on device · sync needs attention' : 'Saved on device · waiting to sync';
  if (!entry.response.canAcknowledgeDraft) return 'Draft · check entry details';
  return entry.response.reviewedAt ? 'Reviewed draft' : 'Draft · ready for your review';
}
function renderList() {
  $('draft-count').textContent = state.entries.length;
  const list = $('draft-list');
  list.replaceChildren();
  if (!state.entries.length) list.append(element('p', 'Your first draft will appear here.', 'empty'));
  for (const entry of [...state.entries].reverse()) {
    const capture = JSON.parse(entry.raw);
    const button = element('button', undefined, 'draft-row' + (entry.id === state.selected ? ' selected' : ''));
    button.type = 'button';
    button.dataset.draftId = entry.id;
    button.append(element('strong', label('products', capture.productId, capture)),
      element('small', `${label('parcels', capture.parcelId, capture)} · ${capture.dose.value || 'No dose'} ${label('units', capture.dose.unitId, capture)}`),
      element('small', humanTime(capture.event.start)), element('small', rowState(entry), 'row-state'));
    if (entry.corrects) {
      const changes = correctionChanges(entry);
      button.append(element('small', 'Corrected copy', 'copy-label'), element('small',
        changes.length ? changes.slice(0, 2).join(' · ') + (changes.length > 2 ? ` · ${changes.length - 2} more changes` : '')
          : correctionParent(entry) ? 'No entered details changed' : 'Original unavailable in this browser'));
    }
    if (state.entries.some(row => correctionParent(row)?.id === entry.id))
      button.append(element('small', 'Has a corrected copy — both are kept', 'copy-label'));
    button.addEventListener('click', () => showReview(entry.id, true));
    list.append(button);
  }
  setConnection();
}
function fact(parent, name, value) {
  const block = element('div');
  block.append(element('dt', name), element('dd', value));
  parent.append(block);
}
function showReview(id, focus = false) {
  const changedSelection = state.selected !== id;
  state.selected = id;
  const entry = state.entries.find(row => row.id === id);
  if (!entry) return;
  const capture = JSON.parse(entry.raw), report = entry.response;
  if (changedSelection) for (const section of ['review-background', 'check-details', 'missing-input-details', 'verifier-details']) $(section).open = false;
  $('review').hidden = false;
  $('review-state').textContent = report?.reviewedAt ? 'Reviewed draft' : 'Draft';
  $('review-summary').replaceChildren();
  for (const [name, value] of [
    ['Example job', label('jobs', capture.jobId, capture)],
    ['Product', label('products', capture.productId, capture)],
    ['Dose', `${capture.dose.value || 'Not entered'} ${label('units', capture.dose.unitId, capture)}`],
    ['Liquid measured', label('applicationLiquids', capture.applicationVolume?.liquidId, capture)],
    ['Water or mixture per hectare', capture.applicationVolume
      ? `${capture.applicationVolume.value || 'Not entered'} ${label('applicationVolumeUnits', capture.applicationVolume.unitId, capture)}` : 'Not recorded'],
    ['Parcel', label('parcels', capture.parcelId, capture) + ' · whole parcel'],
    ['Crop', label('crops', capture.cropId, capture)],
    ['Who sprayed', label('performers', capture.performerId, capture)],
    ['Spraying method', label('methods', capture.methodId, capture)],
    ['Treatment target', label('treatmentTargets', capture.treatmentTargetId, capture)],
    ['Application start', humanTime(capture.event.start || capture.event.startLocal)],
    ['Application end', humanTime(capture.event.end || capture.event.endLocal)]
  ]) fact($('review-summary'), name, value);
  const job = report ? report.draftJob : capture.catalogSha256 === state.catalogSha
    ? state.catalog.jobs?.find(row => row.id === capture.jobId) : null;
  showJob($('review-job'), job, capture.jobId
    ? 'This job’s saved version is unavailable. Sync the draft to load its exact job and conditions.'
    : 'No example job is linked to this draft. A corrected copy can select one.');
  showAmountResults(report);
  showConditionEvidence(report);
  showQuickChecks(report);
  showCorrection(entry);
  $('review-sync').hidden = Boolean(report);
  $('review-sync').textContent = entry.error || 'Saved on this device. The checks will run when this draft syncs to the local server.';
  $('review-sync').className = 'notice' + (entry.error ? ' error' : '');
  $('entry-issues').hidden = !report?.issues.length;
  const entryErrors = (report?.issues || []).filter(item => item.level === 'error');
  $('entry-issues-title').textContent = entryErrors.length ? 'Fix these entry details' : 'Things to review';
  $('issue-list').replaceChildren(...(report?.issues || []).map(item => {
    const row = element('li', item.message), control = issueControl(item);
    if (control) row.append(' ', actionButton(item.level === 'error' ? 'Fix this field' : 'Edit this field', () => correctDraft(control)));
    return row;
  }));
  $('check-list').replaceChildren();
  for (const check of report?.checks || [{ label: 'Waiting for sync', status: 'NOT_CHECKED' }]) {
    const row = element('li'); row.append(element('div', check.label));
    row.append(element('span', { CHECKED: 'Entry check passed', ERROR: 'Needs attention', REVIEW: 'Review', NOT_CHECKED: 'Not checked' }[check.status], check.status === 'ERROR' ? 'error' : ''));
    $('check-list').append(row);
  }
  const verification = report?.verification;
  $('review-outcome').textContent = !report ? 'Saved on this device. Connect to run the entry checks.'
    : entryErrors.length ? 'Fix the entry details below before finishing draft review.'
    : verification?.state === 'UNAVAILABLE' ? 'Your draft is saved, but the verifier could not run. Open the check details for the reason.'
    : report.reviewedAt ? 'Draft review finished. The spraying itself is still unverified.'
    : 'Ready for draft review. The spraying itself is still unverified.';
  $('verifier-message').textContent = verification?.message || 'The existing verifier has not checked this draft yet.';
  $('verifier-counts').textContent = '';
  if (verification?.counts) {
    const c = verification.counts;
    $('verifier-counts').textContent = `${c.PASS} passed · ${c.FAIL} failed · ${c.NOT_EVALUATED} not checked · ${c.NOT_APPLICABLE} not applicable. The complete spray claim is still unverified.`;
  } else if (verification?.error) $('verifier-counts').textContent = 'This draft has not passed the verifier check.';
  $('verifier-error').hidden = !verification?.error;
  $('verifier-error-detail').textContent = verification?.error || '';
  $('recheck').hidden = !report?.draftSource || verification?.state === 'REPORT_AVAILABLE';
  $('recheck').textContent = verification?.state === 'UNAVAILABLE' ? 'Retry verifier' : 'Run verifier';
  $('recheck').disabled = false;
  $('verifier-details').hidden = verification?.state !== 'REPORT_AVAILABLE';
  $('verifier-identity').textContent = verification?.checkId ? `Checked ${humanTime(verification.checkedAtUtc)} · draft check ${verification.checkId}` : '';
  $('verifier-findings').replaceChildren();
  for (const finding of verification?.findings || []) {
    const row = element('tr');
    const status = { PASS: 'Passed', FAIL: 'Failed', NOT_EVALUATED: 'Not checked', NOT_APPLICABLE: 'Not applicable' }[finding.disposition] || finding.disposition;
    row.append(element('td', finding.id), element('td', status),
      element('td', (finding.diagnostics || []).map(item => [item.code, item.pointer, item.detail].filter(Boolean).join(' · ')).join('\n') || '—'));
    $('verifier-findings').append(row);
  }
  const unresolved = verification?.missingInputs?.map(item => item.message) || report?.unresolved || ['Real approval stays unavailable. Sync this draft to see its checks and remaining questions.'];
  $('unresolved').replaceChildren(...unresolved.map(item => element('li', item)));
  $('times').replaceChildren();
  for (const [name, value] of [['Captured on device', capture.capturedAt], ['Received by this computer', report?.receivedAt || 'Not synced'],
    ['Draft review acknowledged', report?.reviewedAt || 'Not yet reviewed'], ['Entered time zone', capture.event.timeZone]]) fact($('times'), name, value);
  $('digest').textContent = 'Original entry SHA-256: ' + entry.sha256;
  $('original').textContent = entry.raw;
  $('acknowledge').disabled = !report?.canAcknowledgeDraft || Boolean(report?.reviewedAt);
  $('acknowledge').textContent = report?.reviewedAt ? 'Draft reviewed' : 'Finish draft review';
  $('review-help').textContent = report?.reviewedAt
    ? 'You reviewed this draft. Real approval and publication are still unavailable.'
    : 'This marks only the draft as reviewed. It does not approve or publish it.';
  renderList();
  if (focus) {
    const target = $(entryErrors.length ? 'entry-issues-title' : 'review-title');
    target.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'start' });
    target.focus({ preventScroll: true });
  }
}
async function verifyReply(entry, report) {
  if (report.originalText !== entry.raw || report.originalSha256 !== entry.sha256 || await hash(report.originalText) !== entry.sha256)
    throw new Error('The saved original does not match this device. The browser copy was kept; review is blocked.');
  if (report.gates?.payload !== null || report.gates?.accepted !== false || report.gates?.publication !== 'BLOCKED'
      || report.gates?.liveC4 !== 'NOT_EVALUATED' || report.gates?.runtimeAdmission !== 'NOT_ESTABLISHED' || report.typedClaim !== null)
    throw new Error('The reply exceeded this draft-only test. Review is blocked.');
  if (report.jobConditions?.some(condition => condition.status !== 'NOT_EVALUATED'))
    throw new Error('The reply claimed that a job condition was verified. Review is blocked.');
  if (report.exampleAmountChecks?.some(check => !['MATCH', 'DIFFERENT', 'NOT_CHECKED'].includes(check.status)
      || (check.status !== 'NOT_CHECKED' && check.rule?.fictional !== true)))
    throw new Error('The example amount reply exceeded the draft-only boundary. Review is blocked.');
  const exampleEvidence = report.exampleConditionEvidence;
  if (exampleEvidence && (exampleEvidence.qualification !== 'FICTIONAL_EXAMPLE_ONLY' || exampleEvidence.evidenceUse !== 'NOT_ADMITTED'
      || exampleEvidence.links?.some(link => link.conditionStatus !== 'NOT_EVALUATED'
        || !['EXAMPLE_LINKED', 'NO_EXAMPLE', 'CONTEXT_MISMATCH', 'INVALID_EXAMPLE'].includes(link.status)
        || (link.status === 'EXAMPLE_LINKED' && (link.record?.fictional !== true || exampleEvidence.evidenceSet?.fictional !== true)))))
    throw new Error('The example evidence reply exceeded the draft-only boundary. Review is blocked.');
  const check = report.verification;
  if (check?.completeClaim !== false || check?.liveC4 !== 'NOT_EVALUATED' || check?.publication !== 'BLOCKED')
    throw new Error('The verifier reply exceeded the draft-only boundary. Review is blocked.');
  if (check?.state === 'REPORT_AVAILABLE' && (check.payload !== null || check.atomicCommit !== 'NOT_EVALUATED'
      || check.runtimeAdmission !== 'NOT_ESTABLISHED' || check.implementationCompleteness !== 'INCOMPLETE'
      || check.transportStatus !== 'DOMAIN_REPORT' || !['FAIL', 'DEPENDENCY_UNAVAILABLE', 'INPUT_ERROR'].includes(check.reportStatus)
      || check.findings?.length !== 49))
    throw new Error('The verifier returned an incomplete or unexpectedly enabled result. Review is blocked.');
}
async function sync(automatic = false) {
  if (!state.db) return;
  clearTimeout(state.retryTimer); state.retryTimer = null;
  if (automatic !== true) state.retryDelay = 2000;
  state.syncRequested = true;
  if (state.syncing) return;
  state.syncing = true; setConnection();
  try {
    do {
      // A timer only retries temporary failures. A queued save/reconnect/manual
      // request gets a full follow-up pass. Timers are never armed during a pass.
      const retryOnly = automatic === true;
      automatic = false;
      state.syncRequested = false;
      const attempted = new Set();
      let entry;
      while ((entry = state.entries.find(row => !row.response && !attempted.has(row.id) && (!retryOnly || state.retryableIds.has(row.id))))) {
        attempted.add(entry.id);
        try {
          const response = await request('/api/drafts', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: entry.raw });
          await verifyReply(entry, response);
          const updated = { ...entry, response, error: null };
          await dbRequest('outbox', 'put', updated);
          Object.assign(entry, updated); state.connected = true;
          state.retryableIds.delete(entry.id);
        } catch (error) {
          state.connected = false;
          if (error.retryable === true) state.retryableIds.add(entry.id); else state.retryableIds.delete(entry.id);
          entry.error = error.retryable === true
            ? 'Sync could not finish. Your draft is saved on this device. This app will retry automatically while it is open.' : error.message;
          // Failure to save a status must never erase the already saved original.
          try { await dbRequest('outbox', 'put', entry); } catch { notice('Browser storage could not save the sync status. Keep this tab open.', true); }
        }
        if (state.selected === entry.id) showReview(entry.id, document.activeElement === $('review-title'));
        else renderList();
      }
    } while (state.syncRequested);
  } finally { state.syncing = false; scheduleRetry(); setConnection(); }
}
function scheduleRetry() {
  if (!state.entries.some(entry => !entry.response && state.retryableIds.has(entry.id))) {
    state.retryDelay = 2000;
    return;
  }
  // One page-local timer; no health endpoint or background worker is needed.
  state.retryTimer = setTimeout(() => { state.retryTimer = null; sync(true); }, state.retryDelay);
  state.retryDelay = Math.min(state.retryDelay * 2, 30000);
}

$('capture').addEventListener('submit', async (event) => {
  event.preventDefault();
  if ($('entry-fields').disabled) return;
  $('save').disabled = true; disableNewRecord(true);
  try {
    const form = formValues();
    const capture = { format: 'spray-draft.v5', draftId: crypto.randomUUID(), capturedAt: new Date().toISOString(), jobId: form.job,
      exampleEvidenceSetId: form['example-evidence'],
      catalogSha256: state.catalogSha, productId: form.product, parcelId: form.parcel, cropId: form.crop,
      performerId: form.performer, methodId: form.method, treatmentTargetId: form['treatment-target'],
      dose: { value: form.dose, unitId: form.unit },
      applicationVolume: { liquidId: form['liquid-kind'], value: form['application-volume'], unitId: form['volume-unit'] },
      event: { start: toInstant(form.start), end: toInstant(form.end), startLocal: form.start, endLocal: form.end, timeZone: zone } };
    const raw = JSON.stringify(capture);
    // This browser-only relationship is not part of the captured facts or
    // verifier request. A correction never rewrites or approves its parent.
    const entry = { id: capture.draftId, raw, sha256: await hash(raw), response: null, error: null,
      ...(state.correcting ? { corrects: { ...state.correcting } } : {}) };
    await dbRequest('outbox', 'add', entry);
    state.entries.push(entry);
    state.correcting = null; $('correction-context').hidden = true; fields.forEach(clearFieldError);
    await saveWorkingForm();
    notice('Draft saved on this device. Your original entry is kept.');
    showReview(entry.id, true);
    $('save').textContent = 'Saved · edit to make another draft';
    await sync();
  } catch (error) {
    notice('The draft was NOT saved on this device. Keep the entered details and retry. ' + error.message, true);
    $('save').disabled = false;
  } finally {
    disableNewRecord($('entry-fields').disabled);
  }
});
$('capture').addEventListener('input', event => {
  $('save').disabled = false;
  $('save').textContent = state.correcting ? 'Save corrected copy →' : 'Save draft and check →';
  if (fields.includes(event.target.id)) clearFieldError(event.target.id);
  saveWorkingForm();
});
$('product').addEventListener('change', () => {
  const product = state.catalog.products.find(row => row.id === $('product').value);
  if (product) { $('unit').value = product.defaultUnitId; clearFieldError('unit'); }
  saveWorkingForm();
});
$('job').addEventListener('change', () => {
  showEntryJob();
  saveWorkingForm();
});
$('example-evidence').addEventListener('change', () => {
  showEvidencePreview();
  saveWorkingForm();
});
$('parcel').addEventListener('change', () => {
  const parcel = state.catalog.parcels.find(row => row.id === $('parcel').value);
  if (parcel) { $('crop').value = parcel.cropId; clearFieldError('crop'); }
  saveWorkingForm();
});
$('sync').addEventListener('click', sync);
$('recheck').addEventListener('click', async () => {
  const entry = state.entries.find(row => row.id === state.selected);
  if (!entry?.response) return;
  $('recheck').disabled = true;
  $('verifier-message').textContent = 'Running the existing verifier…';
  try {
    const response = await request(`/api/drafts/${entry.id}/verify`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ originalSha256: entry.sha256 }) });
    await verifyReply(entry, response);
    const updated = { ...entry, response };
    await dbRequest('outbox', 'put', updated);
    Object.assign(entry, updated); showReview(entry.id);
  } catch (error) {
    $('verifier-message').textContent = 'The check could not finish. Your draft is kept.';
    $('verifier-counts').textContent = error.message;
    $('recheck').disabled = false;
  }
});
$('acknowledge').addEventListener('click', async () => {
  const entry = state.entries.find(row => row.id === state.selected);
  if (!entry?.response?.canAcknowledgeDraft) return;
  $('acknowledge').disabled = true;
  try {
    const response = await request(`/api/drafts/${entry.id}/review`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ originalSha256: entry.sha256 }) });
    await verifyReply(entry, response);
    const updated = { ...entry, response };
    await dbRequest('outbox', 'put', updated);
    Object.assign(entry, updated);
    showReview(entry.id);
    notice('Draft review finished. This is still a draft; nothing was approved or published.');
  } catch (error) {
    notice('Draft review was not confirmed. ' + error.message, true);
    showReview(entry.id);
  }
});
$('edit').addEventListener('click', () => correctDraft());
for (const id of ['new-record', 'new-record-review']) $(id).addEventListener('click', startNewRecord);
$('separate-draft').addEventListener('click', () => {
  if ($('entry-fields').disabled) return;
  state.correcting = null; $('correction-context').hidden = true; fields.forEach(clearFieldError);
  $('save').textContent = 'Save draft and check →'; saveWorkingForm();
  notice('These details will be saved as a separate draft. Existing drafts stay unchanged.');
});
window.addEventListener('online', () => { setConnection(); sync(); });
window.addEventListener('offline', () => { state.connected = false; setConnection(); });

async function start() {
  try {
    state.db = await openDatabase();
    let selected;
    try {
      selected = await request('/api/catalog');
      await dbRequest('settings', 'put', selected, 'catalog');
      state.connected = true;
    } catch (error) {
      selected = await dbRequest('settings', 'get', 'catalog');
      if (!selected) throw new Error('Start the local server and load the app once before using it offline.');
    }
    state.catalog = selected.catalog; state.catalogSha = selected.sha256;
    fillSelect('job', state.catalog.jobs, 'Choose an example job');
    fillSelect('example-evidence', state.catalog.exampleEvidenceSets, 'No example evidence');
    fillSelect('product', state.catalog.products, 'Choose a product'); fillSelect('unit', state.catalog.units);
    fillSelect('liquid-kind', state.catalog.applicationLiquids, 'Choose water or mixture');
    fillSelect('volume-unit', state.catalog.units.filter(row => row.id === 'litres-per-hectare'));
    fillSelect('parcel', state.catalog.parcels, 'Choose a parcel'); fillSelect('crop', state.catalog.crops, 'Choose a crop');
    fillSelect('performer', state.catalog.performers, 'Choose who sprayed');
    fillSelect('method', state.catalog.methods, 'Choose a spraying method');
    fillSelect('treatment-target', state.catalog.treatmentTargets, 'Choose a treatment target');
    setForm(blankForm());
    const working = await dbRequest('settings', 'get', 'working-entry');
    if ((working?.job || working?.['example-evidence']) && working.catalogSha256 !== state.catalogSha) {
      working.job = '';
      working['example-evidence'] = '';
      notice('The example list has changed. Choose the job version and any fictional notes again for this unfinished entry. Your other entered details are kept.');
    }
    setForm(working);
    $('timezone').textContent = 'Your device time: ' + zone + '. Delayed entry is allowed.';
    state.entries = await dbRequest('outbox', 'getAll');
    state.entries.sort((a, b) => JSON.parse(a.raw).capturedAt.localeCompare(JSON.parse(b.raw).capturedAt));
    const parent = state.entries.find(row => row.id === working?.corrects?.id && row.sha256 === working.corrects.sha256);
    if (parent) {
      state.correcting = { id: parent.id, sha256: parent.sha256 }; $('correction-context').hidden = false;
      $('save').textContent = 'Save corrected copy →'; showFieldErrors(parent);
    }
    const hasDetails = ['jobs', 'performers', 'methods', 'treatmentTargets', 'applicationLiquids'].every(group => state.catalog[group]?.length);
    $('entry-fields').disabled = !hasDetails;
    disableNewRecord(!hasDetails);
    if (!hasDetails) notice('Reconnect and reload once to get the current spray choices, including the example job. Your earlier drafts are kept.', true);
    renderList();
    if (state.entries.length && !sameForm(formValues(), blankForm())) showReview(state.entries.at(-1).id);
    await sync();
    if ('serviceWorker' in navigator) {
      try { await navigator.serviceWorker.register('/sw.js'); }
      catch { notice('Offline page loading is unavailable in this browser. Saved drafts remain in browser storage.', true); }
    }
  } catch (error) { notice(error.message, true); setConnection(); }
}
start();
