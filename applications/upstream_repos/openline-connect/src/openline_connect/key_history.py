"""Verify seller-root succession with a separately pinned initial root."""
import hashlib
from .signing import verify

def inspect(epochs,pinned_first_public):
    if not epochs or epochs[0]['sequence']!=1 or epochs[0]['public']!=pinned_first_public:raise ValueError('untrusted_first_root')
    prior=epochs[0]['public']
    for i,e in enumerate(epochs[1:],start=2):
        if e['sequence']!=i or e['previous_key_hash']!=hashlib.sha256(bytes.fromhex(prior)).hexdigest():raise ValueError('epoch_chain_gap')
        c=verify(e['rotation'],{'seller':prior},kind='openline.connect.key_succession.v1')
        if c.get('new_public')!=e['public'] or c.get('sequence')!=i or c.get('previous_key_hash')!=e['previous_key_hash']:raise ValueError('invalid_key_transition')
        prior=e['public']
    return {'verified':True,'current_public':prior,'epochs':len(epochs),'not_a_global_trust_witness':True}
