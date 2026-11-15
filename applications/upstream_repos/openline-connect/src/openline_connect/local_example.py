"""Fictional business handlers. SQLite-local effects only, no external side effects."""
import json

def register_demo(engine):
    def update(params,db):
        db.execute('INSERT OR REPLACE INTO records(record_id,content) VALUES(?,?)',(params['target'],json.dumps({'value':params['value']})))
        return {'record_id':params['target'],'value':params['value'],'status':'updated_locally'}
    def analyze(params,db):
        db.execute('INSERT OR REPLACE INTO records(record_id,content) VALUES(?,?)',(params['target'],json.dumps({'report':'synthetic_ok'})))
        return {'report_id':params['target'],'result':'synthetic_ok'}
    engine.register('record.update',update,max_amount_cents=5000)
    engine.register('report.generate',analyze,max_amount_cents=5000,payment_required=True)
