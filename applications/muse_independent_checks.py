"""Independent private-preview audit (RC3 port); Playwright replaces missing Selenium for browser E2E.

Ported 2026-11-10 from the RC2 version: the RC2 checks targeted the old
in-page demo panels (#da-kpi-quotes, #db-feedback-banner, #btn-simulate-worker-replace, ...),
which the RC3 UI replaced with a server-driven Genie prompt + artifact iframe + proposal
box. Every check below preserves the RC2 check's intent and count (24), exercised
through the RC3 UI and engine instead. Browser checks run against the real local
server (deterministic, --no-model equivalent: use_model=False), never set_content.
"""
from __future__ import annotations
import os, sys, json, shutil, tempfile, threading, urllib.request, urllib.error
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from genie_engine import OpenLineGenieEngine, GenieAppSynthesizer, calculate_quote_totals
from genie_server import start_genie_server


def _resolve_chrome_path():
    """Browser binary for Playwright: GENIE_CHROME_PATH override, then a
    system Chromium/Chrome on PATH, else None (Playwright default lookup).
    No hardcoded home-directory path."""
    env = os.environ.get("GENIE_CHROME_PATH") or os.environ.get("CHROME_PATH")
    if env:
        return env
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        found = shutil.which(name)
        if found:
            return found
    return None


CHROME = _resolve_chrome_path()

checks=[]
def check(label, okay, details=''):
    checks.append({'check':label,'pass':bool(okay),'detail':details})
    print(('PASS ' if okay else 'FAIL ')+label+(' — '+details if details and not okay else ''))
    if not okay: raise AssertionError(label+' '+details)

def frame_text(page):
    return page.frame_locator("#artifact-frame").locator("body").inner_text()

def wait_frame_text(page, needle, timeout_ms=15000):
    waited = 0
    while waited < timeout_ms:
        try:
            if needle in frame_text(page):
                return True
        except Exception:
            pass
        page.wait_for_timeout(500)
        waited += 500
    return False

# --- browser section: real server, deterministic, seeded XSS payload ---
d0 = tempfile.mkdtemp(prefix='genie-audit-ui-')
seed = OpenLineGenieEngine(state_dir=d0)
seed.demo_a_add_or_update_quote(customer_id='CUST-999', customer_name='<img src=x onerror="window.__pwned=1">',
                                items=[{'service_id':'SRV-01','quantity':1,'unit_price_dollars':10,'taxable':False}])
api = start_genie_server(port=0, state_dir=d0, use_model=False)
th = threading.Thread(target=api.serve_forever, daemon=True); th.start()
try:
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True, executable_path=CHROME, args=['--no-sandbox','--disable-dev-shm-usage'])
        page = b.new_page(viewport={'width':390,'height':844})
        errors = []
        page.on('pageerror', lambda ex: errors.append(str(ex)))
        page.on('console', lambda m: errors.append('console.'+m.type+': '+m.text) if m.type == 'error' else None)
        # RC6: the RC3 UI lives at /openline_genie.html now; / is the
        # living-world UI. This suite is the RC6 equivalent of the RC3
        # independent checks, exercising the preserved RC3 UI.
        page.goto(f'http://127.0.0.1:{api.server_port}/openline_genie.html', wait_until='networkidle')
        page.wait_for_timeout(800)
        check('mobile no sideways overflow', not page.evaluate('document.documentElement.scrollWidth > document.documentElement.clientWidth + 2'))
        check('honest preview disclosure visible', page.get_by_text('Private preview · local server only', exact=False).count() > 0)
        # Open the existing demo-a fixture from the project list (the preset
        # chip rebuilds the fixture from scratch and would wipe the seed).
        page.locator("[data-open-project='demo-a-service-quoting']").wait_for(state='visible', timeout=15000)
        page.locator("[data-open-project='demo-a-service-quoting']").click()
        check('demo fixture project loads in the UI', wait_frame_text(page, 'Read-only snapshot'),
              'demo-a snapshot did not render')
        # The seeded stored-XSS payload must stay inert in the snapshot iframe.
        frame = page.frame_locator("#artifact-frame")
        check('stored HTML injection inert',
              frame.locator("img").count() == 0
              and frame.locator("body").evaluate("() => window.__pwned") in (None, False)
              and '<img src=x' in frame_text(page),
              'payload executed or was not rendered as escaped text')
        sha_before = page.locator('#kpi-sha').evaluate('el => el.textContent')
        page.fill('#change-request-input', 'bad change test')
        page.locator('#btn-propose-change').click()
        page.locator('#proposal-box').wait_for(state='visible', timeout=15000)
        page.locator('#btn-reject-proposal').click()
        page.wait_for_timeout(600)
        check('rejected proposals preserve local accepted version',
              page.locator('#kpi-sha').evaluate('el => el.textContent') == sha_before, f'sha moved {sha_before}')
        ver_before = page.locator('#kpi-version').evaluate('el => el.textContent')
        page.fill('#change-request-input', 'good change test')
        page.locator('#btn-propose-change').click()
        page.locator('#proposal-box').wait_for(state='visible', timeout=15000)
        page.locator('#btn-accept-proposal').click()
        page.wait_for_timeout(600)
        check('accepted proposals advance local draft',
              page.locator('#kpi-version').evaluate('el => el.textContent') != ver_before,
              f'version stayed {ver_before}')
        page.locator('#details-tech summary').click()
        page.locator('#btn-replace-worker').click()
        page.wait_for_timeout(600)
        check('worker switch is real, not simulated',
              'worker-b' in page.locator('#kpi-worker').evaluate('el => el.textContent')
              and 'Worker replaced' in page.locator('#trace-tbody').evaluate('el => el.textContent'),
              page.locator('#kpi-worker').evaluate('el => el.textContent'))
        check('browser JavaScript errors absent', len(errors) == 0, repr(errors[:2]))
        b.close()
finally:
    api.shutdown(); api.server_close()

# --- engine section: robot simulation and synth records (RC3 UI has no in-page panels) ---
with tempfile.TemporaryDirectory(prefix='genie-audit-') as d1:
    eng = OpenLineGenieEngine(state_dir=d1)
    bundle_b = eng.get_project_bundle("demo-b-robot-academy-kids")
    rec_blocks = bundle_b["accepted"]["state"]["levels"]["2"]["recommended_blocks"]
    res = eng.demo_b_run_program(2, rec_blocks, speed_mps=0.55)
    sim = res["accepted"]["state"]["last_simulation"]
    check('playable robot demo reaches target', sim["reached_target"] and sim["status"] == "MISSION_COMPLETE", str(sim)[:160])
    synth = eng.build_from_prompt("Build a neighborhood tool library and equipment lending tracker with refundable deposits and overdue check-in alerts.")
    pid = synth["project_id"]
    before = len(synth["accepted"]["state"]["records"])
    updated = eng.synthesized_app_add_record(pid, {
        "item_name": "Test Synthesized Item", "borrower_name": "Alex Rivera",
        "deposit_paid_dollars": 80.0, "late_days": 3, "daily_late_fee_dollars": 4.0,
        "array_watts": 800, "marginal_rate_dollars": 0.36, "self_use_fraction": 0.85,
        "quantity_units": 5, "unit_rate_dollars": 50.0, "adjustments_dollars": 10.0})
    recs = updated["accepted"]["state"]["records"]
    check('template record can be added',
          len(recs) == before + 1 and recs[-1]["record_id"] == f"REC-{101 + before}",
          f'before={before} last={recs[-1].get("record_id") if recs else None}')

with tempfile.TemporaryDirectory(prefix='genie-audit-') as d1, tempfile.TemporaryDirectory(prefix='genie-audit-') as d2:
    a=OpenLineGenieEngine(state_dir=d1)
    b=OpenLineGenieEngine(state_dir=d2)
    check('signing identities differ across installations',a.receiver_identity.public!=b.receiver_identity.public)
    check('key file restricted to owner', (os.stat(Path(d1)/'.genie_key_owner').st_mode&0o077)==0)
    same=OpenLineGenieEngine(state_dir=d1)
    check('state directory reload retains verification identity',same.receiver_identity.public==a.receiver_identity.public)
    check('recipient defaults do not silently dispatch',a.attempt_consequential_external_action('demo-a-service-quoting','send_customer_email','https://example.invalid',{},owner_approved=False)['status']=='BLOCKED_OWNER_AUTHORIZATION_REQUIRED')
    # A dispatcher that says just "DELIVERED" without a trusted signature must not prove success.
    fake_ack=a.attempt_consequential_external_action('demo-a-service-quoting','send_customer_email','https://example.invalid',{'id':'X'},owner_approved=True)
    check('unsigned dispatcher ACK remains UNKNOWN',fake_ack['status']=='UNKNOWN_RECONCILIATION_REQUIRED' and fake_ack['external_effects_verified']==0)
    # HTML/CSV exports must not interpret customer data as executable markup/formulas.
    a.demo_a_add_or_update_quote(customer_id='CUST-999',customer_name='<img src=x onerror="alert(1)">',items=[{'service_id':'SRV-01','quantity':1,'unit_price_dollars':10,'taxable':False}])
    html_dump=a.export_portable_bundle('demo-a-service-quoting')['standalone_html']
    check('standalone HTML exports escaped', '&lt;img' in html_dump and '<img src=x onerror' not in html_dump)
    a.demo_a_add_or_update_quote(customer_id='CUST-998',customer_name='=HYPERLINK("https://bad.example","click")',items=[{'service_id':'SRV-01','quantity':1,'unit_price_dollars':10,'taxable':False}])
    csv_dump=a.export_portable_bundle('demo-a-service-quoting')['portable_csv']
    check('CSV formula injection neutralized', "'=HYPERLINK" in csv_dump)
    for value in [float('nan'),float('inf'),float('-inf')]:
        try:
            GenieAppSynthesizer.compute_record_metric({'app_slug':'solar'}, {'array_watts':value})
            denied=False
        except ValueError:denied=True
        check(f'solar nonfinite {value} refused',denied)
    for value in [float('nan'),float('inf')]:
        try: calculate_quote_totals([{'unit_price_dollars':value}]) ;denied=False
        except ValueError:denied=True
        check(f'quote nonfinite {value} refused',denied)

# Cross-origin calls to the local API cannot mutate via a remote browser page.
api=start_genie_server(port=0,state_dir=tempfile.mkdtemp(prefix='genie-local-api-'),use_model=False)
th=threading.Thread(target=api.serve_forever,daemon=True);th.start()
try:
    ep=f'http://127.0.0.1:{api.server_port}/api/stop'
    def req(data, headers):
        try:
            with urllib.request.urlopen(urllib.request.Request(ep,data=data,headers=headers),timeout=6) as res:return res.status,json.loads(res.read())
        except urllib.error.HTTPError as ex:return ex.code,json.loads(ex.read())
    bad=req(b'{"reason":"hijack"}',{'Origin':'https://malicious.example','Content-Type':'application/json'})
    check('cross-origin STOP request refused',bad[0]==403)
    ct=req(b'{"reason":"hijack"}',{'Content-Type':'text/plain'})
    check('form-compatible content-type refused',ct[0]==415)
finally:
    api.shutdown();api.server_close()
(Path(__file__).parent/'MUSE_INDEPENDENT_RESULTS.json').write_text(json.dumps({'total':len(checks),'passed':sum(x['pass'] for x in checks),'checks':checks},indent=2)+'\n')
print('DONE',sum(x['pass'] for x in checks),'/',len(checks))
