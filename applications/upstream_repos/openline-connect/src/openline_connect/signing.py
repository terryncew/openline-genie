"""Ordinary Ed25519 RFC7515 JWS compact signing, with pinned public keys.

Only application claims are OpenLine-specific; no proprietary signature format.
"""
import base64,hashlib,json
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey,Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
from cryptography.exceptions import InvalidSignature

def canon(v):
    return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('ascii')
def digest(v):return hashlib.sha256(canon(v)).hexdigest()
def b64(v):return base64.urlsafe_b64encode(v).decode().rstrip('=')
def ub64(s):
    if not isinstance(s,str) or not s or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_' for c in s):raise ValueError('noncanonical_base64')
    out=base64.urlsafe_b64decode(s+'='*(-len(s)%4))
    if b64(out)!=s:raise ValueError('noncanonical_base64')
    return out
def pub(seed):return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(seed)).public_key().public_bytes(Encoding.Raw,PublicFormat.Raw).hex()
def sign(claim,seed,kid):
    h=b64(canon({'alg':'EdDSA','kid':kid,'typ':'JWT'}));p=b64(canon(claim));msg=(h+'.'+p).encode('ascii')
    return h+'.'+p+'.'+b64(Ed25519PrivateKey.from_private_bytes(bytes.fromhex(seed)).sign(msg))
def verify(token,trust,*,kind=None):
    if not isinstance(token,str) or len(token)>262144:raise ValueError('invalid_token')
    try:
        a,b,c=token.split('.')
        header=json.loads(ub64(a));claim=json.loads(ub64(b))
        if not isinstance(claim,dict) or header.get('alg')!='EdDSA' or header.get('typ')!='JWT' or set(header)!={'alg','kid','typ'}:raise ValueError('wrong_header')
        if canon(header)!=ub64(a) or canon(claim)!=ub64(b):raise ValueError('noncanonical_json')
        keys=trust[header['kid']]
        keys=keys if isinstance(keys,(list,tuple)) else [keys]
        if not keys:raise ValueError('untrusted_empty_roots')
        validated=False
        for key in keys:
            try:
                Ed25519PublicKey.from_public_bytes(bytes.fromhex(key)).verify(ub64(c),(a+'.'+b).encode('ascii'))
                validated=True;break
            except InvalidSignature:continue
        if not validated:raise ValueError('invalid_signature')
        if kind is not None and claim.get('kind')!=kind:raise ValueError('wrong_claim_kind')
        return claim
    except (KeyError,UnicodeError,TypeError,AttributeError,OverflowError,InvalidSignature) as e:raise ValueError('invalid_signature_or_shape') from e
