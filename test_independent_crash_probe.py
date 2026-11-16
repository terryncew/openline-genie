import tempfile, copy, sqlite3
from genie_engine import OpenLineGenieEngine, sha256_hex

with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
    source = OpenLineGenieEngine(state_dir=d1, model_adapter=None)
    dest = OpenLineGenieEngine(state_dir=d2, model_adapter=None)
    pid = source.list_projects()[0]['project_id']
    current = source.get_project_bundle(pid)['accepted']['state']
    app = '<html><body>Real HTML</body></html>'
    staged_ver = source.store_app_version(pid, 'demo.html', app, status='exploratory')
    upd = copy.deepcopy(current)
    upd['app_sha256'] = sha256_hex(app)
    upd['app_version'] = staged_ver
    upd['app_filename'] = 'demo.html'
    receipt = source._commit_accepted_state(
        pid, upd['project_family'], upd,
        operation='promote_project_state',
        promote_staged_app_version=staged_ver,
    )
    assert receipt.get('status') == 'COMMITTED'
    doc = source.get_project_bundle(pid)
    doc['app'] = {'filename': 'demo.html', 'content': app, 'sha256': sha256_hex(app), 'version': staged_ver, 'runs_standalone': True}
    target = pid + '-copied-for-audit'
    def crash(*a, **kw):
        raise RuntimeError('simulated post-commit app-promotion crash')
    dest.promote_app_version = crash
    try:
        dest.import_portable_bundle(doc, target_project_id=target)
        raise AssertionError('unexpected import success')
    except Exception:
        pass
    with sqlite3.connect(dest.db_path) as db:
        target_row = db.execute('SELECT version, state_sha256 FROM genie_accepted WHERE project_id=?', (target,)).fetchone()
        app_rows = db.execute("SELECT status, sha256 FROM genie_app_versions WHERE project_id=? AND status='accepted'", (target,)).fetchall()
    assert target_row is None, f'Expected atomic rollback of genie_accepted, got {target_row}'
    assert app_rows == [], f'Expected 0 accepted app rows on crash rollback, got {app_rows}'
    print('PASS: test_independent_crash_probe atomic rollback verified')
