// Local browser journey tests. Uses fresh browser storage and a temporary inbox.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { spawn, spawnSync } = require('node:child_process');
const python = process.env.SPRAY_DRAFT_PYTHON;
assert.ok(python, 'Set SPRAY_DRAFT_PYTHON to the interpreter supplied by the separate verifier setup.');

const root = __dirname;
const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'ofarm-draft-browser-'));
const results = [];
let browser, server, base;
const errors = [];
const artifact = process.env.SPRAY_BROWSER_EVIDENCE || path.join(root, '.local', 'test-evidence', 'browser');
fs.mkdirSync(artifact, { recursive: true });

async function startServer(port = 0) {
  server = spawn(python,
    ['-B', path.join(root, 'app.py'), '--port', String(port), '--data', path.join(temporary, 'drafts.sqlite3')],
    { cwd: root, env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' }, stdio: ['ignore', 'pipe', 'pipe'] });
  return await new Promise((resolve, reject) => {
    let output = '';
    const timer = setTimeout(() => reject(new Error('Local server did not start: ' + output)), 15000);
    server.stderr.on('data', value => output += value);
    server.once('exit', code => { clearTimeout(timer); reject(new Error('Local server exited: ' + code + ' ' + output)); });
    server.stdout.on('data', value => {
      output += value;
      const found = output.match(/http:\/\/127\.0\.0\.1:\d+/);
      if (found) { clearTimeout(timer); resolve(found[0]); }
    });
  });
}

async function stopServer() {
  if (!server || server.exitCode !== null || server.signalCode !== null) return;
  const stopped = new Promise(resolve => server.once('exit', resolve));
  server.kill('SIGTERM');
  await stopped;
}

async function waitFor(test, message) {
  const deadline = Date.now() + 15000;
  while (Date.now() < deadline) {
    if (await test()) return;
    await new Promise(resolve => setTimeout(resolve, 80));
  }
  throw new Error(message);
}

async function fill(page, value = '0.30', product = 'binding:demo-product-a') {
  await page.selectOption('#job', 'job:demo-orchard-spray');
  await page.selectOption('#example-evidence', 'example-evidence:orchard-notes:r1');
  await page.selectOption('#product', product);
  await page.selectOption('#parcel', 'field:demo-orchard');
  await page.selectOption('#crop', 'binding:demo-apples');
  await page.fill('#dose', value);
  await page.selectOption('#liquid-kind', 'water');
  await page.fill('#application-volume', '200.00');
  await page.selectOption('#performer', 'party:demo-operator');
  await page.selectOption('#method', 'method:demo-tractor-sprayer');
  await page.selectOption('#treatment-target', 'organism:demo-pest');
  await page.fill('#start', '2026-11-11T10:00');
  await page.fill('#end', '2026-11-11T10:45');
}

async function original(page) {
  return JSON.parse(await page.locator('#original').textContent());
}

async function browserEntry(page, id) {
  return await page.evaluate(async id => {
    const db = await new Promise(resolve => { const r = indexedDB.open('ofarm-spray-draft-rehearsal-v1'); r.onsuccess = () => resolve(r.result); });
    const entry = await new Promise(resolve => { const r = db.transaction('outbox').objectStore('outbox').get(id); r.onsuccess = () => resolve(r.result); });
    db.close(); return entry;
  }, id);
}

async function formState(page) {
  return await page.locator('#capture input, #capture select').evaluateAll(nodes => Object.fromEntries(nodes.map(node => [node.id, node.value])));
}

async function workingEntry(page) {
  return await page.evaluate(async () => {
    const db = await new Promise(resolve => { const r = indexedDB.open('ofarm-spray-draft-rehearsal-v1'); r.onsuccess = () => resolve(r.result); });
    const value = await new Promise(resolve => { const r = db.transaction('settings').objectStore('settings').get('working-entry'); r.onsuccess = () => resolve(r.result); });
    db.close(); return value;
  });
}

async function api(draftId) {
  const response = await fetch(`${base}/api/drafts/${draftId}`);
  assert.equal(response.status, 200);
  return await response.json();
}

function inboxRows() {
  const read = spawnSync(python,
    ['-B', '-I', '-S', '-c', `import json, sqlite3, sys
from pathlib import Path
with sqlite3.connect(Path(sys.argv[1]).resolve().as_uri() + '?mode=ro', uri=True) as db:
 rows = [dict(id=r[0], original=r[1].decode(), sha256=r[2], receivedAt=r[3]) for r in db.execute('SELECT id, original, sha256, received_at FROM captures ORDER BY id')]
print(json.dumps(rows))`, path.join(temporary, 'drafts.sqlite3')],
    { env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' }, encoding: 'utf8' });
  assert.equal(read.status, 0, read.stderr);
  return JSON.parse(read.stdout);
}

async function acknowledge(page) {
  await waitFor(() => page.locator('#acknowledge').isEnabled(), 'Draft did not become reviewable');
  await page.click('#acknowledge');
  await waitFor(async () => await page.locator('#review-state').textContent() === 'Reviewed draft', 'Review acknowledgement did not complete');
}

function checkVerifier(saved) {
  const check = saved.verification;
  assert.equal(check.completeClaim, false);
  assert.equal(check.liveC4, 'NOT_EVALUATED');
  assert.equal(check.publication, 'BLOCKED');
  assert.match(check.checkId, /^[a-f0-9]{64}$/);
  if (check.state === 'REPORT_AVAILABLE') {
    assert.equal(check.transportStatus, 'DOMAIN_REPORT');
    assert.equal(check.reportStatus, 'FAIL');
    assert.equal(check.findings.length, 49);
    assert.equal(check.payload, null);
    assert.equal(check.atomicCommit, 'NOT_EVALUATED');
    assert.equal(check.runtimeAdmission, 'NOT_ESTABLISHED');
  } else {
    // A guarded runtime refusal is tested as a refusal, never as completed
    // happy-path verifier coverage. The exact response is kept as evidence.
    assert.equal(check.state, 'UNAVAILABLE');
    assert.equal(check.transportStatus, 'DEPENDENCY_INTEGRITY_ERROR');
    assert.ok(check.error === 'INTERPRETER_BYTES_MISMATCH' || check.error.startsWith('DEPENDENCY_FILE_BYTES_MISMATCH:'));
    assert.deepEqual(check.findings, []);
  }
  return check.state;
}

async function testServerRestart() {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, locale: 'en-GB', timezoneId: 'Europe/Ljubljana' });
  const page = await context.newPage(), beforeRows = inboxRows(), port = Number(new URL(base).port);
  const sends = [], inFlight = new Set();
  let maxInFlight = 0;
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => {
    if (!request.url().startsWith(base) && !request.url().startsWith('data:')) errors.push('Unexpected external request: ' + request.url());
    if (request.url() === base + '/api/drafts' && request.method() === 'POST') {
      sends.push({ raw: request.postData(), at: new Date().toISOString() });
      inFlight.add(request); maxInFlight = Math.max(maxInFlight, inFlight.size);
    }
  });
  for (const event of ['requestfinished', 'requestfailed']) page.on(event, request => inFlight.delete(request));
  const waitSaved = async id => waitFor(async () => Boolean((await browserEntry(page, id)).response), 'Server restart did not automatically recover draft ' + id);
  const newRecord = async value => {
    await waitFor(() => page.locator('#new-record').isEnabled(), 'New-record button not ready');
    await page.click('#new-record');
    await waitFor(async () => await page.inputValue('#product') === '', 'Fresh form did not clear');
    await fill(page, value);
  };
  try {
    await page.goto(base);
    await waitFor(() => page.locator('#product').isEnabled(), 'Restart test form not ready');
    await page.evaluate(() => { window.networkChanges = []; for (const type of ['online', 'offline']) window.addEventListener(type, () => window.networkChanges.push(type)); });
    await fill(page);
    await page.click('#save');
    await acknowledge(page);
    const first = await original(page), firstSaved = await api(first.draftId);

    await stopServer();
    await stopServer(); // Cleanup also works after an already completed signal exit.
    assert.equal(await page.evaluate(() => navigator.onLine), true);
    const pending = [];
    for (const value of ['0.40', '0.50']) {
      await newRecord(value);
      await page.click('#save');
      await waitFor(async () => await page.locator('#sync').isEnabled()
        && Boolean((await browserEntry(page, (await original(page)).draftId)).error), 'Stopped server did not leave a saved pending draft');
      pending.push(await browserEntry(page, (await original(page)).draftId));
    }
    await newRecord('0.77');
    await waitFor(async () => (await workingEntry(page)).dose === '0.77', 'Unfinished entry not stored');
    const unfinished = await formState(page), working = await workingEntry(page);
    await new Promise(resolve => setTimeout(resolve, 2300));
    assert.equal(await startServer(port), base);
    try {
      for (const entry of pending) await waitSaved(entry.id);
    } finally {
      fs.writeFileSync(path.join(artifact, 'server-restart-recovery.json'), JSON.stringify({ pending, after: await Promise.all(pending.map(row => browserEntry(page, row.id))),
        sends, maxInFlight, networkChanges: await page.evaluate(() => window.networkChanges), workingBefore: working, workingAfter: await workingEntry(page) }, null, 2));
    }
    assert.deepEqual(await formState(page), unfinished);
    assert.deepEqual(await workingEntry(page), working);
    for (const entry of pending) {
      const saved = await api(entry.id);
      assert.equal(saved.originalText, entry.raw); assert.equal(saved.originalSha256, entry.sha256);
      assert.equal(saved.reviewedAt, null); assert.equal(saved.gates.accepted, false); assert.equal(saved.gates.payload, null);
      assert.equal(saved.gates.liveC4, 'NOT_EVALUATED'); assert.equal(saved.gates.publication, 'BLOCKED');
    }
    const firstAgain = await api(first.draftId);
    for (const key of ['originalText', 'originalSha256', 'receivedAt', 'reviewedAt']) assert.equal(firstAgain[key], firstSaved[key]);
    assert.deepEqual(inboxRows().map(row => row.id).sort(), [...beforeRows.map(row => row.id), first.draftId, ...pending.map(row => row.id)].sort());
    assert.equal(await page.locator('#draft-count').textContent(), '3');
    results.push({ case: 'server-restart-recovers-two-pending-drafts-without-network-event-and-keeps-unfinished-work-and-reviewed-original', passed: true });

    // Save the unfinished fourth record, then stop the real server after it
    // stores the original but before the browser can receive its response.
    let lostResponse;
    await page.route('**/api/drafts', async route => {
      if (!lostResponse) {
        const response = await route.fetch(); lostResponse = await response.json();
        await stopServer(); await route.abort('failed');
      } else await route.continue();
    });
    await page.click('#save');
    await waitFor(async () => Boolean(lostResponse) && await page.locator('#sync').isEnabled()
      && Boolean((await browserEntry(page, lostResponse.capture.draftId)).error), 'Lost reply did not leave pending original');
    const lostPending = await browserEntry(page, lostResponse.capture.draftId);
    assert.equal(lostPending.response, null);
    await page.unroute('**/api/drafts');
    assert.equal(await startServer(port), base);
    await waitSaved(lostPending.id);
    const recovered = await api(lostPending.id);
    for (const key of ['originalText', 'originalSha256', 'receivedAt', 'reviewedAt']) assert.equal(recovered[key], lostResponse[key]);
    assert.equal(recovered.originalText, lostPending.raw);
    assert.equal(recovered.verification.checkId, lostResponse.verification.checkId);
    assert.equal(recovered.reviewedAt, null);
    assert.equal(inboxRows().length, beforeRows.length + 4);
    assert.equal(await page.locator('#draft-count').textContent(), '4');
    results.push({ case: 'server-restart-after-lost-reply-reuses-one-original-receipt-and-verifier-result', passed: true });
    const settledSends = sends.length;
    await new Promise(resolve => setTimeout(resolve, 3200));
    assert.equal(sends.length, settledSends, 'A settled queue kept sending');
    assert.deepEqual(await page.evaluate(() => window.networkChanges), []);
    results.push({ case: 'server-return-retries-stop-after-all-pending-originals-sync', passed: true });

    let temporaryFailures = 0;
    await page.route('**/api/drafts', async route => {
      temporaryFailures++;
      if (temporaryFailures === 1) await route.fulfill({ status: 503, json: { error: 'Test temporary server failure' } });
      else await route.continue();
    });
    await newRecord('0.30'); await page.click('#save');
    await waitFor(async () => temporaryFailures >= 1 && Boolean((await original(page)).draftId), 'Temporary server failure not reached');
    const temporaryId = (await original(page)).draftId;
    await waitSaved(temporaryId);
    assert.equal(temporaryFailures, 2);
    assert.equal((await api(temporaryId)).reviewedAt, null);
    await page.unroute('**/api/drafts');
    results.push({ case: 'temporary-server-error-retries-automatically-with-one-stored-original', passed: true });

    for (const refusal of ['conflict', 'unsafe-reply']) {
      let calls = 0;
      await page.route('**/api/drafts', async route => {
        calls++;
        if (refusal === 'conflict') await route.fulfill({ status: 409, json: { error: 'Test original conflict: review is blocked.' } });
        else {
          const response = await route.fetch(), changed = await response.json();
          changed.gates.publication = 'ALLOWED'; await route.fulfill({ response, json: changed });
        }
      });
      await newRecord('0.30'); await page.click('#save');
      await waitFor(async () => calls >= 1 && await page.locator('#sync').isEnabled()
        && Boolean((await browserEntry(page, (await original(page)).draftId)).error), 'Refusal was not retained');
      const refused = await browserEntry(page, (await original(page)).draftId);
      await new Promise(resolve => setTimeout(resolve, 3200));
      assert.equal(calls, 1, refusal + ' incorrectly scheduled automatic retries');
      assert.equal((await browserEntry(page, refused.id)).raw, refused.raw);
      assert.equal((await browserEntry(page, refused.id)).response, null);
      assert.equal(await page.locator('#acknowledge').isDisabled(), true);
      await page.unroute('**/api/drafts');
      await page.click('#sync'); await waitSaved(refused.id);
      assert.equal((await api(refused.id)).originalText, refused.raw);
      results.push({ case: 'server-retry-keeps-' + refusal + '-blocked-without-an-automatic-loop', passed: true });
    }
    assert.equal(maxInFlight, 1);
    const rows = inboxRows();
    assert.equal(rows.length, beforeRows.length + 7);
    assert.equal(await page.locator('#draft-count').textContent(), '7');
    for (const old of beforeRows) assert.deepEqual(rows.find(row => row.id === old.id), old);
    const firstAtEnd = await api(first.draftId);
    for (const key of ['originalText', 'originalSha256', 'receivedAt', 'reviewedAt']) assert.equal(firstAtEnd[key], firstSaved[key]);
    for (const route of ['/commit', '/review', '/api/accept', '/api/publish']) {
      const response = await fetch(base + route, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      assert.equal(response.status, 403);
      assert.deepEqual((await response.json()).gates, { liveC4: 'NOT_EVALUATED', runtimeAdmission: 'NOT_ESTABLISHED', publication: 'BLOCKED', payload: null, accepted: false });
    }
    results.push({ case: 'server-restart-keeps-real-approval-commit-and-publication-routes-blocked', passed: true });
    fs.writeFileSync(path.join(artifact, 'server-restart-final.json'), JSON.stringify({ lostResponse, recovered, sends, maxInFlight,
      networkChanges: await page.evaluate(() => window.networkChanges), inboxBefore: beforeRows, inboxAfter: rows, firstBefore: firstSaved, firstAfter: firstAtEnd }, null, 2));
  } finally { await context.close(); }
}

(async () => {
  try {
    base = await startServer();
    browser = await chromium.launch({ headless: true });
    if (process.env.SPRAY_RESTART_ONLY === '1') {
      await testServerRestart();
      assert.deepEqual(errors, []);
      console.log(JSON.stringify({ passed: true, cases: results.length, results }, null, 2));
      return;
    }
    const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, locale: 'en-GB', timezoneId: 'Europe/Ljubljana' });
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => {
      if (!request.url().startsWith(base) && !request.url().startsWith('data:')) errors.push('Unexpected external request: ' + request.url());
    });
    await page.goto(base);
    await waitFor(() => page.locator('#product').isEnabled(), 'Entry form not ready');
    for (const selector of ['#job', '#example-evidence', '#performer', '#method', '#treatment-target', '#liquid-kind', '#application-volume', '#parcel', '#crop', '#start', '#end']) assert.equal(await page.inputValue(selector), '');
    await fill(page);
    assert.ok((await page.locator('#entry-job').textContent()).includes('Job conditions — not checked'));
    assert.ok((await page.locator('#entry-amount-rules').textContent()).includes('0.30 litres per hectare'));
    assert.ok((await page.locator('#entry-amount-rules').textContent()).includes('200.00 litres per hectare'));
    await page.click('#save');
    await acknowledge(page);
    const first = await original(page);
    const saved = await api(first.draftId);
    assert.equal(saved.capture.dose.value, '0.30');
    assert.equal(saved.draftSource.actualQuantityParameters[0].reportedValue, '0.30');
    assert.equal(saved.capture.format, 'spray-draft.v5');
    assert.equal(saved.capture.exampleEvidenceSetId, 'example-evidence:orchard-notes:r1');
    assert.deepEqual(saved.exampleConditionEvidence.links.map(row => row.status), ['EXAMPLE_LINKED', 'EXAMPLE_LINKED', 'EXAMPLE_LINKED']);
    assert.equal(saved.exampleConditionEvidence.evidenceUse, 'NOT_ADMITTED');
    assert.equal(await page.locator('#review-condition-evidence details').count(), 3);
    assert.ok((await page.locator('#review-condition-evidence').textContent()).includes('every selected treatment segment is still missing'));
    assert.ok((await page.locator('#review-condition-evidence').textContent()).includes('does not verify a condition'));
    assert.equal(saved.capture.jobId, 'job:demo-orchard-spray');
    assert.equal(saved.draftJob.revision, 'r1');
    assert.equal(saved.jobSource.catalogRawSha256, saved.capture.catalogSha256);
    assert.deepEqual(saved.jobConditions.map(row => row.status), ['NOT_EVALUATED', 'NOT_EVALUATED', 'NOT_EVALUATED']);
    assert.deepEqual(saved.exampleAmountChecks.map(row => row.status), ['MATCH', 'MATCH']);
    assert.ok((await page.locator('#review-amount-rules').textContent()).includes('Product amount — Matches example'));
    assert.ok((await page.locator('#review-amount-rules').textContent()).includes('Water amount — Matches example'));
    assert.ok((await page.locator('#review-job').textContent()).includes('Example orchard spray — version 1'));
    assert.ok((await page.locator('#review-job').textContent()).includes('Job conditions — not checked'));
    assert.equal((await page.locator('#review-job').textContent()).split('— Not checked').length - 1, 3);
    assert.deepEqual(saved.capture.applicationVolume, { liquidId: 'water', value: '200.00', unitId: 'litres-per-hectare' });
    assert.equal(saved.draftSource.actualQuantityParameters[1].parameterRole, 'APPLICATION_VOLUME');
    assert.equal(saved.draftSource.actualQuantityParameters[1].reportedValue, '200.00');
    assert.equal(saved.capture.performerId, 'party:demo-operator');
    assert.equal(saved.capture.methodId, 'method:demo-tractor-sprayer');
    assert.equal(saved.capture.treatmentTargetId, 'organism:demo-pest');
    assert.equal(saved.draftSource.actor.actorPartyRef, 'party:demo-farmer');
    assert.equal(saved.draftSource.actor.operatorPartyRef, saved.capture.performerId);
    assert.equal(saved.draftSource.actualAction.methodRef, saved.capture.methodId);
    for (const text of ['Example operator', 'Tractor-mounted sprayer (example)', 'Example pest', 'Water only', '200.00 L/ha'])
      assert.ok((await page.locator('#review-summary').textContent()).includes(text));
    assert.equal(saved.gates.accepted, false);
    assert.equal(saved.gates.payload, null);
    assert.equal(saved.gates.publication, 'BLOCKED');
    assert.equal(saved.gates.liveC4, 'NOT_EVALUATED');
    assert.ok(saved.reviewedAt);
    assert.notEqual(first.event.start, first.capturedAt);
    const verifierState = checkVerifier(saved);
    fs.writeFileSync(path.join(artifact, 'first-draft-api-response.json'), JSON.stringify(saved, null, 2));
    assert.equal(await page.locator('#verifier-message').textContent(), saved.verification.message);
    assert.equal(await page.locator('#unresolved li').count(), 6);
    assert.equal(await page.locator('#verifier-findings tr').count(), verifierState === 'REPORT_AVAILABLE' ? 49 : 0);
    if (verifierState === 'UNAVAILABLE') {
      await page.locator('#check-details > summary').click();
      await page.click('#recheck');
      await waitFor(async () => await page.locator('#verifier-message').textContent() === saved.verification.message,
        'Retry did not display the actual unavailable result');
      assert.deepEqual(await original(page), first);
      await page.locator('#check-details > summary').click();
    }
    for (const id of ['entry-background', 'review-background', 'check-details', 'missing-input-details'])
      assert.equal(await page.locator('#' + id).evaluate(node => node.open), false);
    assert.equal(await page.locator('#amount-outcomes li').count(), 2);
    assert.equal(await page.locator('#condition-outcomes li').count(), 3);
    assert.ok((await page.locator('#condition-outcomes').innerText()).includes('Finish — unverified'));
    assert.ok((await page.locator('#review-outcome').innerText()).includes(verifierState === 'REPORT_AVAILABLE' ? 'still unverified' : 'could not run'));
    const checkSummary = page.locator('#check-details > summary');
    await checkSummary.focus(); await checkSummary.press('Enter');
    assert.equal(await page.locator('#check-details').evaluate(node => node.open), true);
    if (verifierState === 'REPORT_AVAILABLE') {
      const findingSummary = page.locator('#verifier-details > summary');
      await findingSummary.focus(); await findingSummary.press('Enter');
      assert.equal(await page.locator('#verifier-findings tr:visible').count(), 49);
      assert.ok((await page.locator('#verifier-counts').innerText()).includes('6 failed'));
      await findingSummary.press('Enter');
    }
    await checkSummary.focus(); await checkSummary.press('Enter');
    results.push({ case: 'short-review-keeps-separate-outcomes-and-keyboard-access-to-exact-findings', passed: true });
    await page.screenshot({ path: path.join(artifact, 'desktop-reviewed-draft.png'), fullPage: true });
    results.push({ case: 'entry-to-synced-reviewed-draft', passed: true });
    results.push({ case: 'actual-verifier-result-displayed-with-closed-gates', passed: true,
      observedState: verifierState, fullReportPathTested: verifierState === 'REPORT_AVAILABLE' });

    await page.evaluate(() => navigator.serviceWorker.ready);
    await waitFor(() => page.evaluate(() => Boolean(navigator.serviceWorker.controller)), 'Offline shell not controlling page');
    await context.setOffline(true);
    await page.reload();
    await waitFor(() => page.locator('#product').isEnabled(), 'Offline reload did not restore form');
    await fill(page, '0.40');
    await page.selectOption('#performer', 'party:demo-farmer');
    await page.selectOption('#method', 'method:demo-handheld-sprayer');
    await page.selectOption('#treatment-target', 'organism:demo-fungal-disease');
    await page.selectOption('#liquid-kind', 'spray-mixture');
    await page.fill('#application-volume', '250.50');
    await page.click('#save');
    await waitFor(async () => (await page.locator('#draft-count').textContent()) === '2', 'Offline draft not saved');
    const offline = await original(page);
    assert.ok((await page.locator('#review-amount-rules').textContent()).includes('have not run'));
    await waitFor(() => page.locator('#sync').isEnabled(), 'Offline save did not finish its attempt');
    const offlinePending = await browserEntry(page, offline.draftId);
    const offlineWorking = await workingEntry(page);
    // Hold the offline startup send until the real reconnect event has arrived.
    // This makes the formerly missed retry deterministic, not a timing guess.
    let releaseStartup, activeSends = 0, maxActiveSends = 0;
    const startupPaused = new Promise(resolve => { releaseStartup = resolve; });
    const reconnectSends = [];
    await page.route('**/api/drafts', async route => {
      reconnectSends.push(route.request().postData());
      maxActiveSends = Math.max(maxActiveSends, ++activeSends);
      try {
        if (reconnectSends.length === 1) { await startupPaused; await route.abort('internetdisconnected'); }
        else { const response = await route.fetch(); await route.fulfill({ response }); }
      } finally { activeSends--; }
    });
    await page.reload();
    await waitFor(async () => (await page.locator('#draft-count').textContent()) === '2', 'Offline draft lost on reload');
    await waitFor(() => reconnectSends.length === 1, 'Offline startup send was not held');
    assert.deepEqual(await original(page), offline);
    assert.equal(await page.locator('#acknowledge').isDisabled(), true);
    await page.evaluate(() => { window.reconnectEvents = 0; window.addEventListener('online', () => window.reconnectEvents++); });
    const networkBefore = await page.evaluate(() => ({ online: navigator.onLine, events: window.reconnectEvents }));
    await context.setOffline(false);
    const networkAfter = await page.evaluate(() => ({ online: navigator.onLine, events: window.reconnectEvents }));
    fs.writeFileSync(path.join(artifact, 'reconnect-event-diagnostic.json'), JSON.stringify({ networkBefore, networkAfter }, null, 2));
    // Re-assert the network edge after a service-worker offline reload. This
    // also checks reconnect while the same startup send remains outstanding.
    await context.setOffline(true);
    await waitFor(() => page.evaluate(() => !navigator.onLine), 'Browser did not enter offline state');
    await context.setOffline(false);
    await waitFor(() => page.evaluate(() => window.reconnectEvents > 0), 'Browser did not announce reconnect');
    await page.evaluate(() => { for (let i = 0; i < 4; i++) window.dispatchEvent(new Event('online')); });
    releaseStartup();
    try {
      await waitFor(async () => Boolean((await browserEntry(page, offline.draftId)).response), 'Reconnect during startup did not automatically retry');
    } finally {
      fs.writeFileSync(path.join(artifact, 'startup-reconnect.json'), JSON.stringify({ reconnectSends, maxActiveSends,
        browserEntry: await browserEntry(page, offline.draftId), workingBefore: offlineWorking, workingAfter: await workingEntry(page) }, null, 2));
    }
    await waitFor(() => page.locator('#sync').isEnabled(), 'Reconnect sync did not finish');
    assert.deepEqual(reconnectSends, [offlinePending.raw, offlinePending.raw]);
    assert.equal(maxActiveSends, 1);
    assert.deepEqual(await workingEntry(page), offlineWorking);
    assert.equal((await browserEntry(page, offline.draftId)).response.reviewedAt, null, 'Sync must not acknowledge review');
    await page.unroute('**/api/drafts');
    await acknowledge(page);
    assert.equal((await api(offline.draftId)).originalText, JSON.stringify(offline));
    assert.equal(offline.performerId, 'party:demo-farmer');
    assert.equal(offline.methodId, 'method:demo-handheld-sprayer');
    assert.equal(offline.treatmentTargetId, 'organism:demo-fungal-disease');
    assert.equal(offline.jobId, first.jobId);
    assert.equal(offline.exampleEvidenceSetId, first.exampleEvidenceSetId);
    const offlineReply = await api(offline.draftId);
    assert.ok(offlineReply.issues.some(row => row.code === 'EXAMPLE_JOB_DIFFERENCE'));
    assert.deepEqual(offlineReply.jobConditions, saved.jobConditions);
    assert.deepEqual(offlineReply.exampleConditionEvidence.links.map(row => row.status), ['CONTEXT_MISMATCH', 'CONTEXT_MISMATCH', 'CONTEXT_MISMATCH']);
    assert.ok((await page.locator('#review-condition-evidence').textContent()).includes('Different example — not linked'));
    assert.deepEqual(offlineReply.exampleAmountChecks.map(row => row.status), ['DIFFERENT', 'NOT_CHECKED']);
    assert.ok((await page.locator('#review-amount-rules').textContent()).includes('finished mixture is not treated as water'));
    assert.ok((await page.locator('#issue-list').textContent()).includes('differs from the example job'));
    assert.deepEqual(offline.applicationVolume, { liquidId: 'spray-mixture', value: '250.50', unitId: 'litres-per-hectare' });
    assert.ok((await page.locator('#review-summary').textContent()).includes('Finished spray mixture'));
    assert.ok((await page.locator('#review-summary').textContent()).includes('250.50 L/ha'));
    const firstAfterReconnect = await api(first.draftId);
    for (const key of ['originalText', 'originalSha256', 'receivedAt', 'reviewedAt']) assert.equal(firstAfterReconnect[key], saved[key]);
    results.push({ case: 'offline-startup-reconnect-coalesces-events-keeps-form-and-originals-and-syncs-automatically', passed: true });

    // The server saves the original but its first response is lost. The retry
    // must reuse exactly that original and keep the original receipt time.
    let lostResponse;
    const lostSends = [];
    await page.route('**/api/drafts', async route => {
      lostSends.push(route.request().postData());
      if (!lostResponse) {
        const response = await route.fetch();
        lostResponse = await response.json();
        await context.setOffline(true);
        await context.setOffline(false);
        await page.evaluate(() => { for (let i = 0; i < 4; i++) window.dispatchEvent(new Event('online')); });
        await route.abort('failed');
      } else await route.continue();
    });
    await page.click('#edit');
    await fill(page, '0.50');
    await page.click('#save');
    await waitFor(async () => Boolean(lostResponse) && Boolean((await browserEntry(page, lostResponse.capture.draftId)).response), 'Lost response did not automatically retry');
    const lost = await original(page);
    assert.equal((await browserEntry(page, lost.draftId)).response.reviewedAt, null);
    await acknowledge(page);
    const retried = await api(lost.draftId);
    assert.equal(retried.receivedAt, lostResponse.receivedAt);
    assert.equal(retried.originalSha256, lostResponse.originalSha256);
    assert.equal(retried.verification.checkId, lostResponse.verification.checkId);
    if (retried.verification.state === 'REPORT_AVAILABLE')
      assert.equal(retried.verification.checkedAtUtc, lostResponse.verification.checkedAtUtc);
    assert.deepEqual(lostSends, [retried.originalText, retried.originalText]);
    const threeRows = inboxRows();
    assert.deepEqual(threeRows.map(row => row.id).sort(), [first.draftId, offline.draftId, lost.draftId].sort());
    assert.equal(await page.locator('#draft-count').textContent(), '3');
    for (const row of threeRows) {
      const entry = await browserEntry(page, row.id);
      assert.equal(row.original, entry.raw); assert.equal(row.sha256, entry.sha256);
    }
    fs.writeFileSync(path.join(artifact, 'lost-response-reconnect.json'), JSON.stringify({ lostSends, lostResponse, retried, inbox: threeRows }, null, 2));
    await page.unroute('**/api/drafts');
    results.push({ case: 'lost-response-automatic-retry-keeps-exact-original-receipt-and-one-stored-copy', passed: true });

    // Reconnect does not prove that the local server is available. One burst
    // requests one extra pass; later attempts must wait for the retry delay.
    const unavailableSends = [];
    await page.route('**/api/drafts', async route => {
      unavailableSends.push(route.request().postData());
      if (unavailableSends.length === 1)
        await page.evaluate(() => { for (let i = 0; i < 4; i++) window.dispatchEvent(new Event('online')); });
      await route.abort('failed');
    });
    await page.click('#edit');
    await page.fill('#dose', '0.55');
    await page.click('#save');
    await waitFor(async () => unavailableSends.length >= 2 && await page.locator('#sync').isEnabled(), 'Unavailable server retry did not settle');
    assert.equal(unavailableSends.length, 2);
    const unavailable = await original(page), unavailableEntry = await browserEntry(page, unavailable.draftId);
    assert.equal(unavailableEntry.response, null);
    assert.deepEqual(unavailableSends, [unavailableEntry.raw, unavailableEntry.raw]);
    assert.equal(await page.locator('#acknowledge').isDisabled(), true);
    assert.equal(inboxRows().length, 3);
    // Unsaved typing must survive the later successful sync too.
    await page.fill('#dose', '0.56');
    await waitFor(async () => (await workingEntry(page)).dose === '0.56', 'Unfinished change was not stored');
    const waitingForm = await formState(page), waitingWorking = await workingEntry(page);
    assert.equal(unavailableSends.length, 2);
    results.push({ case: 'unavailable-server-waits-after-coalesced-retry-and-keeps-pending-original', passed: true });
    await page.unroute('**/api/drafts');
    await context.setOffline(true);
    await context.setOffline(false);
    await waitFor(async () => Boolean((await browserEntry(page, unavailable.draftId)).response), 'Later reconnect did not recover pending draft');
    assert.deepEqual(await formState(page), waitingForm);
    assert.deepEqual(await workingEntry(page), waitingWorking);
    const recovered = await api(unavailable.draftId);
    assert.equal(recovered.originalText, unavailableEntry.raw);
    assert.equal(recovered.originalSha256, unavailableEntry.sha256);
    assert.equal(recovered.reviewedAt, null);
    assert.equal(inboxRows().length, 4);
    assert.equal(await page.locator('#draft-count').textContent(), '4');
    fs.writeFileSync(path.join(artifact, 'unavailable-then-reconnected.json'), JSON.stringify({ unavailableSends, pending: unavailableEntry, recovered,
      workingBefore: waitingWorking, workingAfter: await workingEntry(page), inbox: inboxRows() }, null, 2));
    results.push({ case: 'later-reconnect-recovers-once-without-losing-unsaved-edits-or-approving-draft', passed: true });

    await page.click('#edit');
    await page.fill('#dose', '-2');
    await page.click('#save');
    await waitFor(async () => (await original(page)).dose.value === '-2'
      && (await page.locator('#issue-list').textContent()).includes('Enter a dose'), 'Invalid dose was not shown');
    assert.equal(await page.locator('#acknowledge').isDisabled(), true);
    const invalid = await original(page);
    assert.equal((await api(invalid.draftId)).draftSource, null);
    assert.equal(await page.evaluate(() => document.activeElement.id), 'entry-issues-title');
    assert.equal(await page.evaluate(() => document.querySelector('#entry-issues').getBoundingClientRect().top < document.querySelector('#review-summary').getBoundingClientRect().top), true);
    await page.locator('#issue-list').getByRole('button', { name: 'Fix this field', exact: true }).first().click();
    assert.equal(await page.evaluate(() => document.activeElement.id), 'dose');
    assert.equal(await page.locator('#dose').getAttribute('aria-invalid'), 'true');
    assert.equal(await page.locator('#dose').getAttribute('aria-describedby'), 'dose-error');
    assert.ok((await page.locator('#dose-error').innerText()).includes('Enter a dose'));
    await waitFor(() => page.evaluate(async () => {
      const db = await new Promise(resolve => { const r = indexedDB.open('ofarm-spray-draft-rehearsal-v1'); r.onsuccess = () => resolve(r.result); });
      const working = await new Promise(resolve => { const r = db.transaction('settings').objectStore('settings').get('working-entry'); r.onsuccess = () => resolve(r.result); });
      db.close(); return Boolean(working?.corrects);
    }), 'Correction context was not stored');
    await page.reload();
    await waitFor(() => page.locator('#product').isEnabled(), 'Correction did not reload');
    assert.equal(await page.locator('#correction-context').isVisible(), true);
    assert.equal(await page.locator('#dose').getAttribute('aria-invalid'), 'true');
    await page.fill('#dose', '0.60');
    assert.equal(await page.locator('#dose').getAttribute('aria-invalid'), null);
    assert.equal(await page.locator('#dose-error').count(), 0);
    await page.click('#save');
    await acknowledge(page);
    const corrected = await original(page);
    assert.notEqual(corrected.draftId, invalid.draftId);
    assert.equal((await api(invalid.draftId)).capture.dose.value, '-2');
    assert.equal((await api(corrected.draftId)).capture.dose.value, '0.60');
    assert.equal(corrected.performerId, invalid.performerId);
    assert.equal(corrected.methodId, invalid.methodId);
    assert.equal(corrected.treatmentTargetId, invalid.treatmentTargetId);
    assert.deepEqual(corrected.applicationVolume, invalid.applicationVolume);
    assert.equal(corrected.jobId, invalid.jobId);
    assert.equal(corrected.exampleEvidenceSetId, invalid.exampleEvidenceSetId);
    assert.equal((await browserEntry(page, corrected.draftId)).corrects.id, invalid.draftId);
    assert.equal(corrected.corrects, undefined);
    results.push({ case: 'invalid-entry-visible-correction-keeps-original', passed: true });
    results.push({ case: 'error-first-direct-field-focus-accessible-message-and-reloadable-correction', passed: true });

    // Moving between fix links must keep the work already entered for the
    // same original. A reload must preserve it too, without changing that original.
    await page.click('#edit');
    await fill(page, '');
    await page.selectOption('#performer', '');
    await page.click('#save');
    await waitFor(async () => (await page.locator('#issue-list').textContent()).includes('Choose the person who sprayed')
      && (await page.locator('#issue-list').textContent()).includes('Enter a dose'), 'The two missing details were not shown');
    const twoMissing = await original(page), twoMissingSaved = await api(twoMissing.draftId);
    assert.equal(await page.locator('#acknowledge').isDisabled(), true);
    await page.locator('#review').screenshot({ path: path.join(artifact, 'two-mistakes-before.png') });
    const doseFix = page.locator('#issue-list li').filter({ hasText: 'Enter a dose' }).getByRole('button', { name: 'Fix this field', exact: true });
    const personFix = page.locator('#issue-list li').filter({ hasText: 'Choose the person who sprayed' }).getByRole('button', { name: 'Fix this field', exact: true });
    await doseFix.click();
    await page.fill('#dose', '0.30');
    await personFix.click();
    assert.equal(await page.inputValue('#dose'), '0.30', 'Moving to the person must keep the corrected dose');
    assert.equal(await page.evaluate(() => document.activeElement.id), 'performer');
    assert.equal(await page.locator('#dose').getAttribute('aria-invalid'), null);
    await page.selectOption('#performer', 'party:demo-operator');
    await doseFix.click();
    assert.equal(await page.inputValue('#performer'), 'party:demo-operator', 'Moving back to dose must keep the corrected person');
    await page.click('#edit');
    assert.equal(await page.inputValue('#dose'), '0.30');
    assert.equal(await page.inputValue('#performer'), 'party:demo-operator');
    results.push({ case: 'multiple-field-fix-links-and-copy-button-preserve-unsaved-corrections', passed: true });
    await waitFor(() => page.evaluate(async () => {
      const db = await new Promise(resolve => { const r = indexedDB.open('ofarm-spray-draft-rehearsal-v1'); r.onsuccess = () => resolve(r.result); });
      const working = await new Promise(resolve => { const r = db.transaction('settings').objectStore('settings').get('working-entry'); r.onsuccess = () => resolve(r.result); });
      db.close(); return working?.dose === '0.30' && working?.performer === 'party:demo-operator';
    }), 'Both unfinished corrections were not stored');
    await page.reload();
    await waitFor(() => page.locator('#product').isEnabled(), 'Two-field correction did not reload');
    await personFix.click();
    assert.equal(await page.inputValue('#dose'), '0.30');
    assert.equal(await page.inputValue('#performer'), 'party:demo-operator');
    assert.equal(await page.locator('#performer').getAttribute('aria-invalid'), null);
    await page.click('#save');
    await acknowledge(page);
    const bothCorrected = await original(page), bothSaved = await api(bothCorrected.draftId);
    assert.equal(bothCorrected.dose.value, '0.30');
    assert.equal(bothCorrected.performerId, 'party:demo-operator');
    assert.deepEqual((await browserEntry(page, bothCorrected.draftId)).corrects,
      { id: twoMissing.draftId, sha256: twoMissingSaved.originalSha256 });
    assert.equal(bothCorrected.corrects, undefined);
    assert.equal((await api(twoMissing.draftId)).originalText, twoMissingSaved.originalText);
    assert.equal((await api(twoMissing.draftId)).reviewedAt, null);
    assert.deepEqual(bothSaved.gates, saved.gates);
    assert.ok((await page.locator('#review-correction').innerText()).includes('Dose: Not entered → 0.30'));
    assert.ok((await page.locator('#review-correction').innerText()).includes('Who sprayed: Not recorded → Example operator'));
    await page.locator('#review').screenshot({ path: path.join(artifact, 'two-mistakes-corrected-review.png') });
    fs.writeFileSync(path.join(artifact, 'two-mistakes-replay.json'), JSON.stringify({ original: twoMissingSaved, corrected: bothSaved }, null, 2));
    results.push({ case: 'two-corrections-survive-reload-and-save-one-linked-reviewed-copy', passed: true });

    await page.click('#edit');
    await page.fill('#dose', '9.99');
    await page.locator(`[data-draft-id="${twoMissing.draftId}"]`).click();
    await doseFix.click();
    assert.equal(await page.inputValue('#dose'), '');
    assert.equal(await page.inputValue('#performer'), '');
    assert.equal(await page.locator('#dose').getAttribute('aria-invalid'), 'true');
    results.push({ case: 'starting-a-correction-for-a-different-original-loads-that-original', passed: true });

    // Correct only the water amount from the original example. Both rows must
    // remain distinguishable, even after an offline save and browser reload.
    await page.locator(`[data-draft-id="${first.draftId}"]`).click();
    await page.click('#edit');
    await page.fill('#application-volume', '201.00');
    await context.setOffline(true);
    await page.click('#save');
    await waitFor(async () => (await original(page)).applicationVolume.value === '201.00', 'Water correction did not save offline');
    const waterCorrection = await original(page);
    await page.reload();
    await waitFor(() => page.locator('#product').isEnabled(), 'Water correction did not reload');
    assert.deepEqual((await browserEntry(page, waterCorrection.draftId)).corrects, { id: first.draftId, sha256: saved.originalSha256 });
    await context.setOffline(false);
    await page.click('#sync');
    await acknowledge(page);
    const newRow = await page.locator(`[data-draft-id="${waterCorrection.draftId}"]`).innerText();
    const oldRow = await page.locator(`[data-draft-id="${first.draftId}"]`).innerText();
    assert.ok(newRow.includes('Corrected copy'));
    assert.ok(newRow.includes('Water or mixture per hectare: 200.00 → 201.00'));
    assert.ok(oldRow.includes('Has a corrected copy'));
    assert.notEqual(newRow, oldRow);
    assert.equal((await api(first.draftId)).originalText, saved.originalText);
    assert.equal((await api(waterCorrection.draftId)).capture.corrects, undefined);
    await page.locator('#issue-list li').filter({ hasText: 'Water amount:' }).getByRole('button').click();
    assert.equal(await page.evaluate(() => document.activeElement.id), 'application-volume');
    await page.locator('#review-correction').getByRole('button', { name: 'View the original draft' }).click();
    assert.equal((await original(page)).draftId, first.draftId);
    await page.locator(`[data-draft-id="${waterCorrection.draftId}"]`).click();
    await page.locator('#draft-list').screenshot({ path: path.join(artifact, 'distinguishable-corrections.png') });
    results.push({ case: 'water-only-correction-link-survives-offline-reload-and-keeps-original-bytes', passed: true });

    await page.click('#edit');
    await page.click('#separate-draft');
    assert.equal(await page.locator('#correction-context').isVisible(), false);
    await page.click('#save');
    await acknowledge(page);
    assert.equal((await browserEntry(page, (await original(page)).draftId)).corrects, undefined);
    assert.equal(await page.locator('#review-correction').isVisible(), false);
    results.push({ case: 'explicit-separate-draft-does-not-inherit-a-correction-link', passed: true });

    const beforeCount = await page.locator('#draft-count').textContent();
    await page.click('#edit');
    await page.fill('#dose', '0.70');
    await page.evaluate(() => {
      window.savedAdd = IDBObjectStore.prototype.add;
      IDBObjectStore.prototype.add = function () { throw new DOMException('Test storage full', 'QuotaExceededError'); };
    });
    await page.click('#save');
    await waitFor(async () => (await page.locator('#notice').textContent()).includes('NOT saved'), 'Storage failure looked like success');
    assert.equal(await page.locator('#draft-count').textContent(), beforeCount);
    assert.equal(await page.inputValue('#dose'), '0.70');
    await page.evaluate(() => { IDBObjectStore.prototype.add = window.savedAdd; });
    results.push({ case: 'browser-storage-failure-keeps-form-and-refuses-success', passed: true });

    // A server-shaped reply that unexpectedly enables C4 must not be accepted
    // into browser storage or make this draft reviewable.
    let refusedSends = 0;
    await page.route('**/api/drafts', async route => {
      refusedSends++;
      const response = await route.fetch();
      const changed = await response.json();
      changed.verification.liveC4 = 'PASS';
      if (refusedSends === 1) await page.evaluate(() => window.dispatchEvent(new Event('online')));
      await route.fulfill({ response, json: changed });
    });
    await page.click('#save');
    await waitFor(async () => (await page.locator('#review-sync').textContent()).includes('exceeded'),
      'Unexpectedly enabled verifier reply was accepted');
    const refused = await original(page);
    await waitFor(async () => refusedSends >= 2 && await page.locator('#sync').isEnabled(), 'Unsafe automatic retry did not settle');
    assert.equal(refusedSends, 2);
    assert.equal((await browserEntry(page, refused.draftId)).response, null);
    assert.equal(await page.locator('#acknowledge').isDisabled(), true);
    assert.equal(await page.locator('#verifier-findings tr').count(), 0);
    await page.unroute('**/api/drafts');
    await context.setOffline(true);
    await context.setOffline(false);
    await acknowledge(page);
    assert.deepEqual(await original(page), refused);
    checkVerifier(await api(refused.draftId));
    results.push({ case: 'unexpected-C4-success-rejected-on-automatic-retry-original-kept-and-reconnect-recovers', passed: true });

    await page.click('#edit');
    await page.route('**/api/drafts', async route => {
      const response = await route.fetch();
      const changed = await response.json();
      changed.jobConditions[2].status = 'PASS';
      await route.fulfill({ response, json: changed });
    });
    await page.click('#save');
    await waitFor(async () => (await page.locator('#review-sync').textContent()).includes('claimed that a job condition was verified'),
      'Unexpected condition success was accepted');
    assert.equal(await page.locator('#acknowledge').isDisabled(), true);
    await page.unroute('**/api/drafts');
    await page.click('#sync');
    await acknowledge(page);
    assert.ok((await page.locator('#review-job').textContent()).includes('Job conditions — not checked'));
    results.push({ case: 'unexpected-condition-success-blocked-retry-keeps-conditions-unverified', passed: true });

    await page.click('#edit');
    await page.route('**/api/drafts', async route => {
      const response = await route.fetch();
      const changed = await response.json();
      changed.exampleAmountChecks[0].status = 'APPROVED';
      await route.fulfill({ response, json: changed });
    });
    await page.click('#save');
    await waitFor(async () => (await page.locator('#review-sync').textContent()).includes('example amount reply exceeded'),
      'Unexpected approval from an example rule was accepted');
    assert.equal(await page.locator('#acknowledge').isDisabled(), true);
    await page.unroute('**/api/drafts');
    await page.click('#sync');
    await acknowledge(page);
    results.push({ case: 'example-rule-approval-rejected-and-retry-recovers', passed: true });

    await page.click('#edit');
    await page.route('**/api/drafts', async route => {
      const response = await route.fetch();
      const changed = await response.json();
      changed.exampleConditionEvidence.evidenceUse = 'ADMITTED';
      await route.fulfill({ response, json: changed });
    });
    await page.click('#save');
    await waitFor(async () => (await page.locator('#review-sync').textContent()).includes('example evidence reply exceeded'),
      'Unexpected admission of fictional evidence was accepted');
    assert.equal(await page.locator('#acknowledge').isDisabled(), true);
    await page.unroute('**/api/drafts');
    await page.click('#sync');
    await acknowledge(page);
    results.push({ case: 'fictional-evidence-admission-rejected-and-retry-recovers', passed: true });

    await page.click('#edit');
    await page.selectOption('#job', '');
    await page.click('#save');
    await waitFor(async () => (await original(page)).jobId === ''
      && (await page.locator('#issue-list').textContent()).includes('Choose an example job'), 'Missing job was not shown');
    const missingJob = await original(page);
    assert.equal(await page.locator('#acknowledge').isDisabled(), true);
    assert.ok((await api(missingJob.draftId)).issues.some(row => row.field === 'jobId'));
    await page.click('#edit');
    await page.selectOption('#job', 'job:demo-orchard-spray');
    await page.click('#save');
    await acknowledge(page);
    assert.notEqual((await original(page)).draftId, missingJob.draftId);
    assert.equal((await api(missingJob.draftId)).capture.jobId, '');
    results.push({ case: 'missing-job-blocks-review-corrected-copy-keeps-original', passed: true });

    await page.click('#edit');
    for (const selector of ['#performer', '#method', '#treatment-target']) await page.selectOption(selector, '');
    await page.click('#save');
    await waitFor(async () => (await original(page)).performerId === ''
      && (await page.locator('#issue-list').textContent()).includes('Choose the person who sprayed'), 'Missing spray details were not shown');
    assert.equal(await page.locator('#acknowledge').isDisabled(), true);
    const missingDetails = await original(page);
    const missingReply = await api(missingDetails.draftId);
    for (const field of ['performerId', 'methodId', 'treatmentTargetId'])
      assert.ok(missingReply.issues.some(issue => issue.field === field));
    assert.equal(missingReply.draftSource, null);
    await page.click('#edit');
    await fill(page, '0.30');
    await page.click('#save');
    await acknowledge(page);
    const suppliedDetails = await original(page);
    assert.notEqual(suppliedDetails.draftId, missingDetails.draftId);
    assert.equal((await api(missingDetails.draftId)).capture.performerId, '');
    assert.equal((await api(suppliedDetails.draftId)).capture.performerId, 'party:demo-operator');
    results.push({ case: 'missing-three-details-block-review-correction-keeps-original', passed: true });

    await page.click('#edit');
    await page.selectOption('#liquid-kind', '');
    await page.fill('#application-volume', '');
    await page.click('#save');
    await waitFor(async () => (await original(page)).applicationVolume.value === ''
      && (await page.locator('#issue-list').textContent()).includes('Enter the water or mixture amount'), 'Missing liquid amount was not shown');
    assert.equal(await page.locator('#acknowledge').isDisabled(), true);
    const missingVolume = await original(page);
    const missingVolumeReply = await api(missingVolume.draftId);
    assert.ok(missingVolumeReply.issues.some(row => row.field === 'applicationVolume.value'));
    assert.ok(missingVolumeReply.issues.some(row => row.field === 'applicationVolume.liquidId'));
    await page.click('#edit');
    await fill(page);
    await page.click('#save');
    await acknowledge(page);
    assert.notEqual((await original(page)).draftId, missingVolume.draftId);
    assert.equal((await api(missingVolume.draftId)).capture.applicationVolume.value, '');
    results.push({ case: 'missing-liquid-amount-blocks-review-correction-keeps-original', passed: true });

    for (const [product, water, expected] of [['0.31', '200.00', ['DIFFERENT', 'MATCH']], ['0.30', '201.00', ['MATCH', 'DIFFERENT']]]) {
      await page.click('#edit');
      await fill(page, product);
      await page.fill('#application-volume', water);
      await page.click('#save');
      await acknowledge(page);
      const changedAmount = await original(page);
      const changedReply = await api(changedAmount.draftId);
      assert.deepEqual(changedReply.exampleAmountChecks.map(row => row.status), expected);
      assert.equal(changedAmount.dose.value, product);
      assert.equal(changedAmount.applicationVolume.value, water);
      assert.ok((await page.locator('#review-amount-rules').textContent()).includes('Different from example'));
      assert.ok(changedReply.jobConditions.every(row => row.status === 'NOT_EVALUATED'));
      assert.equal(changedReply.gates.accepted, false);
      results.push({ case: `independent-amount-result-product-${product}-water-${water}`, passed: true });
    }

    await page.click('#edit');
    await fill(page);
    await page.selectOption('#example-evidence', '');
    await page.click('#save');
    await acknowledge(page);
    const withoutNotes = await original(page);
    assert.deepEqual((await api(withoutNotes.draftId)).exampleConditionEvidence.links.map(row => row.status), ['NO_EXAMPLE', 'NO_EXAMPLE', 'NO_EXAMPLE']);
    assert.ok((await page.locator('#review-condition-evidence').textContent()).includes('No fictional notes were selected'));
    await page.click('#edit');
    await page.selectOption('#example-evidence', 'example-evidence:orchard-notes:r1');
    await page.click('#save');
    await acknowledge(page);
    assert.notEqual((await original(page)).draftId, withoutNotes.draftId);
    assert.equal((await api(withoutNotes.draftId)).capture.exampleEvidenceSetId, '');
    assert.deepEqual((await api((await original(page)).draftId)).exampleConditionEvidence.links.map(row => row.status), ['EXAMPLE_LINKED', 'EXAMPLE_LINKED', 'EXAMPLE_LINKED']);
    results.push({ case: 'optional-evidence-absence-is-visible-and-new-copy-links-notes', passed: true });

    for (const [legacyName, legacyPath] of [['spray-details-20261118', 'fixtures/details/original.json'], ['spray-draft-job-20261118', 'fixtures/job/original.json'], ['spray-draft-amount-rules-20261118', 'fixtures/amount-rules/original.json']]) {
    const legacyRaw = fs.readFileSync(path.join(root, legacyPath), 'utf8');
    const legacyCapture = JSON.parse(legacyRaw);
    const legacyResponse = await fetch(`${base}/api/drafts`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: legacyRaw });
    assert.equal(legacyResponse.status, 200);
    const legacySaved = await legacyResponse.json();
    await page.evaluate(async entry => {
      const db = await new Promise(resolve => { const r = indexedDB.open('ofarm-spray-draft-rehearsal-v1'); r.onsuccess = () => resolve(r.result); });
      await new Promise((resolve, reject) => { const t = db.transaction('outbox', 'readwrite'); t.objectStore('outbox').add(entry); t.oncomplete = resolve; t.onerror = () => reject(t.error); });
      db.close();
    }, { id: legacyCapture.draftId, raw: legacyRaw, sha256: legacySaved.originalSha256, response: legacySaved, error: null });
    await page.reload();
    await waitFor(() => page.locator('#product').isEnabled(), 'Legacy draft list did not reload');
    await page.locator(`[data-draft-id="${legacyCapture.draftId}"]`).click();
    const hadAmountRules = legacyName.includes('spray-draft-amount-rules');
    assert.ok((await page.locator('#review-amount-rules').textContent()).includes(hadAmountRules ? 'Matches example' : 'No separate example amount rules'));
    assert.ok((await page.locator('#review-condition-evidence').textContent()).includes('No fictional notes were selected'));
    await page.click('#edit');
    assert.equal(await page.inputValue('#job'), '');
    assert.equal(await page.inputValue('#example-evidence'), '');
    assert.equal(await page.inputValue('#liquid-kind'), legacyCapture.applicationVolume?.liquidId || '');
    assert.equal(await page.inputValue('#application-volume'), legacyCapture.applicationVolume?.value || '');
    await fill(page);
    await page.click('#save');
    await acknowledge(page);
    assert.notEqual((await original(page)).draftId, legacyCapture.draftId);
    const legacyAfter = await api(legacyCapture.draftId);
    assert.equal(legacyAfter.originalText, legacyRaw);
    assert.deepEqual(legacyAfter.capture, legacyCapture);
    assert.deepEqual(legacyAfter.exampleAmountChecks.map(row => row.status), hadAmountRules ? ['MATCH', 'MATCH'] : []);
    assert.equal(legacyAfter.exampleConditionEvidence, null);
    assert.equal(legacyAfter.capture.exampleEvidenceSetId, undefined);
    results.push({ case: `older-${legacyName}-original-gets-no-new-evidence`, passed: true });
    }

    const mobileContext = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 1, locale: 'en-GB', timezoneId: 'Europe/Ljubljana' });
    const mobile = await mobileContext.newPage();
    mobile.on('pageerror', error => errors.push(error.message));
    await mobile.goto(base);
    await waitFor(() => mobile.locator('#product').isEnabled(), 'Mobile form not ready');
    await mobile.selectOption('#job', 'job:demo-orchard-spray');
    await mobile.selectOption('#example-evidence', 'example-evidence:orchard-notes:r1');
    await mobile.selectOption('#liquid-kind', 'spray-mixture');
    await mobile.fill('#application-volume', '125.50');
    await mobile.selectOption('#product', 'binding:demo-product-b');
    await waitFor(() => mobile.evaluate(async () => {
      const db = await new Promise(resolve => { const r = indexedDB.open('ofarm-spray-draft-rehearsal-v1'); r.onsuccess = () => resolve(r.result); });
      const value = await new Promise(resolve => { const r = db.transaction('settings').objectStore('settings').get('working-entry'); r.onsuccess = () => resolve(r.result); });
      db.close();
      return value?.job === 'job:demo-orchard-spray' && value?.['example-evidence'] === 'example-evidence:orchard-notes:r1' && value?.product === 'binding:demo-product-b' && value?.unit === 'kilograms-per-hectare'
        && value?.['liquid-kind'] === 'spray-mixture' && value?.['application-volume'] === '125.50';
    }), 'Auto-selected unit did not persist with the product');
    await mobile.reload();
    await waitFor(() => mobile.locator('#product').isEnabled(), 'Reloaded mobile form not ready');
    assert.equal(await mobile.inputValue('#unit'), 'kilograms-per-hectare');
    assert.equal(await mobile.inputValue('#liquid-kind'), 'spray-mixture');
    assert.equal(await mobile.inputValue('#application-volume'), '125.50');
    assert.equal(await mobile.inputValue('#job'), 'job:demo-orchard-spray');
    assert.equal(await mobile.inputValue('#example-evidence'), 'example-evidence:orchard-notes:r1');
    results.push({ case: 'unfinished-form-preserves-product-and-auto-selected-unit', passed: true });
    await fill(mobile, '1.25', 'binding:demo-product-b');
    assert.equal(await mobile.inputValue('#unit'), 'kilograms-per-hectare');
    await mobile.screenshot({ path: path.join(artifact, 'mobile-entry.png'), fullPage: true });
    await mobile.click('#save');
    await acknowledge(mobile);
    assert.equal(await mobile.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
    assert.equal((await api((await original(mobile)).draftId)).draftSource.actualQuantityParameters[0].unitRef, 'scheme:ucum:kg/har');
    assert.deepEqual((await api((await original(mobile)).draftId)).exampleAmountChecks.map(row => row.status), ['NOT_CHECKED', 'MATCH']);
    assert.equal(await mobile.locator('#issue-list li').filter({ hasText: 'Product amount:' }).getByRole('button').count(), 0);
    assert.deepEqual((await api((await original(mobile)).draftId)).exampleConditionEvidence.links.map(row => row.status), ['CONTEXT_MISMATCH', 'CONTEXT_MISMATCH', 'CONTEXT_MISMATCH']);
    assert.ok((await mobile.locator('#review-summary').textContent()).includes('200.00 L/ha'));
    await mobile.screenshot({ path: path.join(artifact, 'mobile-reviewed-draft.png'), fullPage: true });
    results.push({ case: 'mobile-entry-review-unit-retention-no-horizontal-overflow', passed: true });

    // A changed catalog must not silently bind an unfinished or corrected
    // entry to a new revision of the same job ID. No changed catalog is saved.
    await mobile.route('**/api/catalog', async route => {
      const response = await route.fetch();
      const changed = await response.json();
      changed.sha256 = '0'.repeat(64);
      changed.catalog.jobs[0].revision = 'r2';
      changed.catalog.jobs[0].label = 'Changed job version for browser test';
      await route.fulfill({ response, json: changed });
    });
    await mobile.reload();
    await waitFor(() => mobile.locator('#product').isEnabled(), 'Changed catalog form not ready');
    assert.equal(await mobile.inputValue('#job'), '');
    assert.equal(await mobile.inputValue('#example-evidence'), '');
    assert.equal(await mobile.inputValue('#dose'), '1.25');
    assert.ok((await mobile.locator('#review-job').textContent()).includes('Example orchard spray — version 1'));
    await mobile.click('#edit');
    assert.equal(await mobile.inputValue('#job'), '');
    assert.equal(await mobile.inputValue('#example-evidence'), '');
    assert.ok((await mobile.locator('#notice').textContent()).includes('Choose the job version'));
    await mobile.unroute('**/api/catalog');
    results.push({ case: 'catalog-change-clears-new-selection-and-preserves-saved-job-version', passed: true });

    // A fresh browser exercises two separate records without touching the
    // user's inbox or inheriting any correction link from the earlier cases.
    const repeatContext = await browser.newContext({ viewport: { width: 1280, height: 900 }, locale: 'en-GB', timezoneId: 'Europe/Ljubljana' });
    const repeat = await repeatContext.newPage();
    repeat.on('pageerror', error => errors.push(error.message));
    repeat.on('request', request => {
      if (!request.url().startsWith(base) && !request.url().startsWith('data:')) errors.push('Unexpected external request: ' + request.url());
    });
    const clearPrompts = [];
    let allowClear = false;
    repeat.on('dialog', async dialog => {
      clearPrompts.push({ type: dialog.type(), message: dialog.message(), accepted: allowClear });
      if (allowClear) await dialog.accept(); else await dialog.dismiss();
    });
    await repeat.goto(base);
    await waitFor(() => repeat.locator('#new-record').isEnabled(), 'Fresh form not ready');
    const blank = await formState(repeat);
    for (const [id, value] of Object.entries(blank))
      assert.equal(value, ['unit', 'volume-unit'].includes(id) ? 'litres-per-hectare' : '', 'Fresh ' + id);
    await fill(repeat);
    await repeat.click('#save');
    await acknowledge(repeat);
    const recordOne = await original(repeat), recordOneSaved = await api(recordOne.draftId);
    const recordOneBrowser = await browserEntry(repeat, recordOne.draftId);
    await waitFor(() => repeat.locator('#new-record-review').isEnabled(), 'New-record action stayed disabled after saving');
    await repeat.click('#new-record-review');
    await waitFor(async () => await repeat.inputValue('#product') === '', 'New record did not clear the old form');
    assert.deepEqual(clearPrompts, []);
    assert.deepEqual(await formState(repeat), blank);
    assert.equal(await repeat.locator('#review').isVisible(), false);
    assert.equal(await repeat.locator('#correction-context').isVisible(), false);
    assert.equal(await repeat.evaluate(() => document.activeElement.id), 'job');
    assert.equal((await workingEntry(repeat)).corrects, null);
    assert.deepEqual(await browserEntry(repeat, recordOne.draftId), recordOneBrowser);
    results.push({ case: 'start-new-record-clears-facts-times-and-correction-context-without-changing-saved-draft', passed: true });

    await fill(repeat, '1.25', 'binding:demo-product-b');
    await repeat.selectOption('#example-evidence', '');
    await repeat.selectOption('#performer', 'party:demo-farmer');
    await repeat.selectOption('#method', 'method:demo-handheld-sprayer');
    await repeat.selectOption('#treatment-target', 'organism:demo-fungal-disease');
    await repeat.fill('#application-volume', '250.00');
    await repeat.fill('#start', '2026-11-12T11:00');
    await repeat.fill('#end', '2026-11-12T11:30');
    const unfinished = await formState(repeat);
    await waitFor(async () => (await workingEntry(repeat))?.end === unfinished.end, 'Unfinished second record was not stored');
    const unfinishedStored = await workingEntry(repeat);
    await repeat.click('#new-record');
    assert.equal(clearPrompts.length, 1);
    assert.equal(clearPrompts[0].type, 'confirm');
    assert.ok(clearPrompts[0].message.includes('Saved drafts will stay unchanged'));
    assert.deepEqual(await formState(repeat), unfinished);
    assert.deepEqual(await workingEntry(repeat), unfinishedStored);
    await repeat.reload();
    await waitFor(() => repeat.locator('#new-record').isEnabled(), 'Unfinished second record did not reload');
    assert.deepEqual(await formState(repeat), unfinished);
    results.push({ case: 'cancel-start-new-keeps-unfinished-second-record-through-reload', passed: true });

    await repeat.evaluate(() => navigator.serviceWorker.ready);
    await waitFor(() => repeat.evaluate(() => Boolean(navigator.serviceWorker.controller)), 'Repeat-record offline shell not ready');
    await repeatContext.setOffline(true);
    await repeat.click('#save');
    await waitFor(async () => await repeat.locator('#draft-count').textContent() === '2', 'Offline second record not saved');
    const recordTwo = await original(repeat), recordTwoPending = await browserEntry(repeat, recordTwo.draftId);
    assert.equal(recordTwoPending.response, null);
    assert.equal(recordTwoPending.corrects, undefined);
    await waitFor(() => repeat.locator('#new-record-review').isEnabled(), 'Offline save did not release the new-record button');
    await repeat.click('#new-record-review');
    await waitFor(async () => await repeat.inputValue('#dose') === '', 'Offline start-new did not clear the form');
    assert.equal(clearPrompts.length, 1, 'An already saved offline draft must not be treated as lost work');
    assert.deepEqual(await browserEntry(repeat, recordTwo.draftId), recordTwoPending);
    await repeat.reload();
    await waitFor(() => repeat.locator('#new-record').isEnabled(), 'Fresh offline form did not reload');
    assert.deepEqual(await formState(repeat), blank);
    assert.equal(await repeat.locator('#review').isVisible(), false);
    assert.equal(await repeat.locator('#draft-count').textContent(), '2');
    // Chromium's service-worker reload can reset navigator.onLine while
    // requests remain emulated offline. Restore that test precondition first.
    await repeatContext.setOffline(false);
    await repeatContext.setOffline(true);
    await waitFor(() => repeat.evaluate(() => !navigator.onLine), 'Repeat-record browser did not enter offline state');
    await repeatContext.setOffline(false);
    await waitFor(async () => Boolean((await browserEntry(repeat, recordTwo.draftId)).response), 'Second draft did not sync automatically');
    await repeat.locator(`[data-draft-id="${recordTwo.draftId}"]`).click();
    await acknowledge(repeat);
    const recordTwoSaved = await api(recordTwo.draftId);
    assert.notEqual(recordOne.draftId, recordTwo.draftId);
    assert.equal(recordTwoSaved.originalText, recordTwoPending.raw);
    assert.equal(recordTwoSaved.capture.dose.value, '1.25');
    assert.equal(recordTwoSaved.capture.dose.unitId, 'kilograms-per-hectare');
    assert.equal((await browserEntry(repeat, recordTwo.draftId)).corrects, undefined);
    assert.deepEqual(await browserEntry(repeat, recordOne.draftId), recordOneBrowser);
    const oneAgain = await api(recordOne.draftId);
    assert.equal(oneAgain.originalText, recordOneSaved.originalText);
    assert.equal(oneAgain.originalSha256, recordOneSaved.originalSha256);
    assert.equal(oneAgain.receivedAt, recordOneSaved.receivedAt);
    assert.equal(oneAgain.reviewedAt, recordOneSaved.reviewedAt);
    await repeat.locator('#review').screenshot({ path: path.join(artifact, 'second-record-reviewed.png') });
    fs.writeFileSync(path.join(artifact, 'two-separate-records.json'), JSON.stringify({ first: recordOneSaved, second: recordTwoSaved }, null, 2));
    results.push({ case: 'two-separate-records-survive-offline-start-reload-sync-and-review-with-unchanged-originals', passed: true });

    await repeat.locator(`[data-draft-id="${recordOne.draftId}"]`).click();
    await repeat.click('#edit');
    await repeat.fill('#dose', '0.80');
    await waitFor(async () => (await workingEntry(repeat))?.dose === '0.80', 'Unfinished correction was not stored');
    const correctionStored = await workingEntry(repeat);
    await repeat.click('#new-record');
    assert.equal(clearPrompts.length, 2);
    assert.equal(await repeat.inputValue('#dose'), '0.80');
    assert.deepEqual(await workingEntry(repeat), correctionStored);
    await repeat.reload();
    await waitFor(() => repeat.locator('#new-record').isEnabled(), 'Unfinished correction did not reload');
    assert.equal(await repeat.inputValue('#dose'), '0.80');
    assert.equal(await repeat.locator('#correction-context').isVisible(), true);
    allowClear = true;
    await repeat.click('#new-record');
    await waitFor(async () => await repeat.inputValue('#dose') === '', 'Confirmed clear did not start a new form');
    assert.equal(clearPrompts.length, 3);
    assert.deepEqual(await formState(repeat), blank);
    assert.equal((await workingEntry(repeat)).corrects, null);
    assert.equal(await repeat.locator('#correction-context').isVisible(), false);
    assert.equal(await repeat.locator('#draft-count').textContent(), '2');
    assert.deepEqual(await browserEntry(repeat, recordOne.draftId), recordOneBrowser);
    results.push({ case: 'cancel-keeps-unfinished-correction-and-confirm-clears-only-its-working-form', passed: true });

    await repeat.selectOption('#product', 'binding:demo-product-a');
    await repeat.fill('#dose', '0.44');
    await waitFor(async () => (await workingEntry(repeat))?.dose === '0.44', 'Storage-failure example was not stored');
    const beforeResetFailure = await workingEntry(repeat), beforeResetForm = await formState(repeat);
    await repeat.evaluate(() => {
      window.originalWorkingPut = IDBObjectStore.prototype.put;
      IDBObjectStore.prototype.put = function (...args) {
        if (this.name === 'settings' && args[1] === 'working-entry') throw new DOMException('Test reset storage failure', 'QuotaExceededError');
        return window.originalWorkingPut.apply(this, args);
      };
    });
    await repeat.click('#new-record');
    await waitFor(async () => (await repeat.locator('#notice').textContent()).includes('new form could not be stored'), 'Reset storage failure was hidden');
    assert.deepEqual(await formState(repeat), beforeResetForm);
    assert.deepEqual(await workingEntry(repeat), beforeResetFailure);
    assert.equal(await repeat.locator('#dose').isEnabled(), true);
    await repeat.evaluate(() => { IDBObjectStore.prototype.put = window.originalWorkingPut; });
    await repeat.reload();
    await waitFor(() => repeat.locator('#new-record').isEnabled(), 'Storage-failure form did not reload');
    assert.deepEqual(await formState(repeat), beforeResetForm);
    results.push({ case: 'new-record-storage-failure-keeps-visible-and-stored-unfinished-work', passed: true });

    await repeat.click('#new-record');
    await waitFor(async () => await repeat.inputValue('#dose') === '', 'Clean form did not start after retry');
    await repeat.screenshot({ path: path.join(artifact, 'new-record-and-two-saved-drafts.png') });
    await repeat.setViewportSize({ width: 390, height: 844 });
    await repeat.screenshot({ path: path.join(artifact, 'new-record-phone.png') });
    assert.equal(await repeat.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    for (const row of [recordOneSaved, recordTwoSaved]) {
      assert.equal(row.gates.liveC4, 'NOT_EVALUATED'); assert.equal(row.gates.publication, 'BLOCKED');
      assert.equal(row.gates.accepted, false); assert.equal(row.gates.payload, null);
      assert.equal(checkVerifier(row), 'REPORT_AVAILABLE');
    }
    for (const route of ['/commit', '/api/accept', '/api/publish']) {
      const response = await fetch(base + route, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      assert.equal(response.status, 403);
      assert.deepEqual((await response.json()).gates, recordOneSaved.gates);
    }
    fs.writeFileSync(path.join(artifact, 'start-new-confirmations.json'), JSON.stringify(clearPrompts, null, 2));
    results.push({ case: 'new-record-fits-phone-and-both-records-keep-live-approval-publication-gates-closed', passed: true });
    await repeatContext.close();

    await testServerRestart();
    assert.deepEqual(errors, []);
    results.push({ case: 'no-page-errors-or-external-requests', passed: true });
    console.log(JSON.stringify({ passed: true, cases: results.length, results }, null, 2));
  } catch (error) {
    results.push({ case: 'browser-run', passed: false, error: error.stack });
    console.error(error);
    process.exitCode = 1;
  } finally {
    fs.writeFileSync(path.join(artifact, 'browser-results.json'), JSON.stringify({ capturedAtUtc: new Date().toISOString(), results, pageErrors: errors, scope: 'Local fictional draft rehearsal; no live C4, public payload or generic C3 closure.' }, null, 2) + '\n');
    if (browser) await browser.close();
    await stopServer();
    const attempts = path.join(temporary, 'drafts.verifier-results');
    if (fs.existsSync(attempts)) fs.cpSync(attempts, path.join(artifact, 'worker-attempts'), { recursive: true });
    fs.rmSync(temporary, { recursive: true, force: true });
  }
})();
