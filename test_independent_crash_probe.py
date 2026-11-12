import tempfile,copy,sqlite3,json,traceback
from genie_engine import OpenLineGenieEngine,sha256_hex
with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
    source=OpenLineGenieEngine(state_dir=d1,model_adapter=None)
    dest=OpenLineGenieEngine(state_dir=d2,model_adapter=None)
    pid=source.list_projects()[0]['project_id']
    current=source.get_project_bundle(pid)['accepted']['state']
    print('family:',current['project_family'],'id:',pid)
    app='<html><body>Real HTML</body></html>'
    upd=copy.deepcopy(current);upd['app_sha256']=sha256_hex(app);upd['app_version']=1;upd['app_filename']='demo.html'
    try:
        receipt=source._commit_accepted_state(pid,upd['project_family'],upd,operation='promote_project_state')
        print('source signed',receipt.get('status'))
    except Exception as e:
        print('SOURCE SIGN ERROR:',repr(e));raise
    doc=source.get_project_bundle(pid)
    doc['app']={'filename':'demo.html','content':app,'sha256':sha256_hex(app),'version':1,'runs_standalone':True}
    target=pid+'-copied-for-audit'
    def crash(*a,**kw): raise RuntimeError('simulated post-commit app-promotion crash')
    dest.promote_app_version=crash
    try:
        dest.import_portable_bundle(doc,target_project_id=target)
        print('unexpected import success')
    except Exception as e:print('EXPECTED INJECTED ERROR:',repr(e))
    with sqlite3.connect(dest.db_path) as db:
        print('TARGET ROW:',db.execute('SELECT version,state_sha256 FROM genie_accepted WHERE project_id=?',(target,)).fetchone())
        print('APP ROW:',db.execute('SELECT status,sha256 FROM genie_app_versions WHERE project_id=?',(target,)).fetchall())
    try:
        b=dest.get_project_bundle(target);print('TARGET ACCEPTED APP REF:',b['accepted']['state'].get('app_version'))
    except Exception as e:print('TARGET GET ERROR',repr(e))
