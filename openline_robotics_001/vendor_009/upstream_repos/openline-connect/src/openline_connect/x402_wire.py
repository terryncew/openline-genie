"""Strict x402 v2 *shape* helpers, not a replacement for official SDK verification.

Facilitator must independently verify and settle. Local tests use signed fake claims.
Offer/receipt placement is prototype-only and not certified against x402 SDK.
"""
import re,json,base64
from datetime import datetime,timezone

_EVM=re.compile(r'^(?:0x)?[0-9a-fA-F]{64}$')
_SOL=re.compile(r'^[1-9A-HJ-NP-Za-km-z]{64,88}$')
_DEC=re.compile(r'^(?:0|[1-9][0-9]*)$')

def decimal_atomic(value):
    if not isinstance(value,str) or not _DEC.fullmatch(value) or len(value)>78 or int(value)>=2**256:raise ValueError('invalid_x402_uint256_string')
    return int(value)
def timestamp(value):
    if isinstance(value,str) and value.isdecimal() and len(value)<=16:return int(value)
    if isinstance(value,str):
        try:return int(datetime.fromisoformat(value.replace('Z','+00:00')).timestamp())
        except (ValueError,OverflowError):pass
    raise ValueError('invalid_x402_timestamp')
def txid(value):
    if not isinstance(value,str) or not (_EVM.fullmatch(value) or _SOL.fullmatch(value)):raise ValueError('invalid_x402_txid')
    return value
def parse_signature_header(h):
    if not isinstance(h,str) or len(h)>30000:raise ValueError('invalid_x402_header')
    try:
        data=base64.b64decode(h,validate=True)
        if len(data)>20000:raise ValueError('x402_header_too_large')
        doc=json.loads(data)
        if doc.get('x402Version')!=2 or not isinstance(doc.get('accepted'),dict) or not isinstance(doc.get('payload'),dict):raise ValueError('invalid_x402_v2_shape')
        accepted=doc['accepted'];decimal_atomic(accepted['amount'])
        return doc
    except (KeyError,TypeError,UnicodeDecodeError,ValueError) as e:raise ValueError('invalid_x402_payment_signature_header') from e

def attach_offer_receipt(payment_response,receipt_jws):
    doc=dict(payment_response)
    ex=dict(doc.get('extensions') or {})
    ex['offer-receipt']={'jws':receipt_jws} # candidate extension until official SDK conformance
    doc['extensions']=ex
    return doc
