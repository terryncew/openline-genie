"""Optional FastAPI app exposing exactly guarded routes, no raw seller submit path."""
from .engine import ProtectionError
from .signing import b64

def create_app(engine):
    from fastapi import FastAPI,HTTPException
    from pydantic import BaseModel,ConfigDict
    app=FastAPI(title='OpenLine Connect — fictional local actions',version='0.1.0rc1')
    class Request(BaseModel):
        model_config=ConfigDict(extra='forbid')
        action:str
        params:dict
        authorization:str|None=None
        nonce:str
        payment:dict|None=None
    @app.get('/healthz')
    def health():return {'status':'ok','scope':'local_sqlite_only'}
    @app.get('/.well-known/openline-connect.json')
    def discovery():
        d=engine.public()
        d['jwks']={'keys':[{'kty':'OKP','crv':'Ed25519','kid':f'seller-epoch-{x["sequence"]}',
                            'x':b64(bytes.fromhex(x['public']))} for x in d['key_epochs']]}
        return d
    @app.post('/v1/connect/execute')
    def execute(req:Request):
        try:return engine.execute(**req.model_dump())
        except ProtectionError as e:raise HTTPException(status_code=e.status,detail=e.code)
        except ValueError:raise HTTPException(status_code=400,detail='invalid_signed_evidence_or_shape')
        except Exception:raise HTTPException(status_code=503,detail='indeterminate_reconcile_required')
    return app
