"""Receiver-owned local onboarding. Demo buyer credential is LOCAL FICTIONAL ONLY.

The receiver's policy and seller private key are stored in receiver-owned files.
Never use this sample co-located buyer private key in a deployed multi-party setup.
"""
from __future__ import annotations
import hashlib, json, os, secrets, sqlite3, time
from pathlib import Path
from .engine import ConnectEngine, ProtectionError
from .local_example import register_demo
from .signing import digest, pub, sign
from .verify import inspect as inspect_receipts


def _home(home: str | Path) -> Path:
    return Path(home).expanduser().resolve()


def _write_private(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def _write_policy(path: Path, policy: dict) -> None:
    tmp = path.with_name(path.name + '.tmp-' + secrets.token_hex(5))
    _write_private(tmp, json.dumps(policy, indent=2, sort_keys=True))
    os.replace(tmp, path)
    os.chmod(path, 0o600)


def initialize(home: str | Path) -> dict:
    base = _home(home)
    # Refuse reinitialization even if a partial previous setup exists.
    if base.exists() and any(base.iterdir()):
        raise ProtectionError('already_initialized_or_nonempty_directory', 409)
    base.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(base, 0o700)
    seller = secrets.token_hex(32)
    local_buyer = secrets.token_hex(32)
    _write_private(base / 'keys' / 'receiver.seed', seller + '\n')
    _write_private(base / 'keys' / 'fictional-buyer.seed', local_buyer + '\n')
    policy = {'buyers': {'fictional-buyer': pub(local_buyer)}, 'grants': {},
              'local_profile_only': True, 'version': 1}
    _write_policy(base / 'policy.json', policy)
    engine = ConnectEngine('sqlite:///' + str(base / 'connect.sqlite'), policy,
                           seller_seed=seller, seller_id='fictional-supplier')
    register_demo(engine)
    trust = {'seller_public': pub(seller), 'note': 'Copy to an independent verifier over a trusted channel; this local copy is NOT independent trust.'}
    _write_private(base / 'trust-bootstrap.json', json.dumps(trust, indent=2))
    return {'home': str(base), 'default_deny': True, 'authorized_operations': 0,
            'seller_public': pub(seller), 'fictional_buyer': True, 'network_listener_started': False}


def read_engine(home: str | Path) -> ConnectEngine:
    base = _home(home)
    seller_file = base / 'keys' / 'receiver.seed'
    policy_file = base / 'policy.json'
    if not seller_file.is_file() or not policy_file.is_file():
        raise ProtectionError('not_initialized', 400)
    engine = ConnectEngine('sqlite:///' + str(base / 'connect.sqlite'), str(policy_file),
                           seller_seed=seller_file.read_text(encoding='ascii').strip(),
                           seller_id='fictional-supplier')
    register_demo(engine)
    return engine


def allow(home: str | Path, *, action: str, target: str, value: str,
          amount_cents: int, ttl_seconds: int, grant_name: str | None = None) -> dict:
    if action != 'record.update':
        raise ProtectionError('unsupported_local_fictional_operation', 400)
    if not target or len(target) > 128 or not value or len(value) > 256:
        raise ProtectionError('invalid_operation_arguments', 400)
    if type(amount_cents) is not int or not (0 <= amount_cents <= 5000):
        raise ProtectionError('amount_outside_demo_limit', 400)
    if type(ttl_seconds) is not int or not (1 <= ttl_seconds <= 3600):
        raise ProtectionError('expiry_outside_local_policy_limit', 400)
    base = _home(home)
    engine = read_engine(base)
    policy = json.loads((base / 'policy.json').read_text())
    if not isinstance(policy.get('grants'), dict):
        raise ProtectionError('policy_not_default_deny', 409)
    buyer = (base / 'keys' / 'fictional-buyer.seed').read_text(encoding='ascii').strip()
    params = {'target': target, 'value': value, 'amount_cents': amount_cents}
    now = engine.clock()
    expires = now + ttl_seconds
    name = grant_name or ('grant-' + secrets.token_hex(8))
    if not name.replace('-', '').replace('_', '').isalnum() or len(name) > 80:
        raise ProtectionError('invalid_grant_name', 400)
    existing = {g['id'] for groups in policy['grants'].values() for g in groups}
    if name in existing:
        raise ProtectionError('grant_name_already_exists', 409)
    grant = {'id': name, 'action': action, 'subject': 'fictional-buyer',
             'target': target, 'max_amount_cents': amount_cents,
             'expires_at': expires, 'active': True}
    grant['receiver_signature'] = sign({**grant, 'kind': 'openline.connect.receiver_grant.v1'}, engine.seed, 'seller')
    policy['grants'].setdefault(action, []).append(grant)
    _write_policy(base / 'policy.json', policy)
    claims = {'kind': 'openline.connect.mandate.v1', 'subject': 'fictional-buyer',
              'seller': engine.seller_id, 'action': action, 'target': target,
              'parameters_sha256': digest(params), 'max_amount_cents': amount_cents,
              'nbf': now - 1, 'exp': expires, 'jti': name}
    authorization = sign(claims, buyer, 'fictional-buyer')
    payload = {'action': action, 'params': params, 'authorization': authorization,
               'nonce': 'nonce-' + secrets.token_hex(12)}
    # Grant is receiver-controlled; buyer mandate is NOT passed into the server via a read tool.
    grant_file = base / 'grants' / (name + '.json')
    _write_private(grant_file, json.dumps(payload, indent=2))
    return {'grant_id': name, 'expires_at': expires, 'action': action,
            'target': target, 'signed_by_receiver': True,
            'fictional_agent_request': str(grant_file),
            'note': 'Explicit local grant only; restart serve to load newly added policy.'}


def verify_local(home: str | Path, *, seller_public: str,
                 expected_head: str | None = None, expected_seq: int | None = None) -> dict:
    # Only read the database and verify its exported signed records using a key supplied
    # by the caller, never automatically trusting a key bundled in an audit packet.
    base = _home(home)
    db_uri = 'file:' + str(base / 'connect.sqlite') + '?mode=ro'
    try:
        db = sqlite3.connect(db_uri, uri=True)
        rows = db.execute('SELECT body FROM operations WHERE body IS NOT NULL ORDER BY updated,nonce').fetchall()
        db.close()
    except sqlite3.Error as e:
        raise ProtectionError('audit_database_unavailable', 404) from e
    entries = []
    for (raw,) in rows:
        item = json.loads(raw)
        if 'receipt' in item and 'outcome' in item:
            entries.append(item)
    # Chronological order is determined by the signed decision_seq; server DB ordering
    # is untrusted. An independent head must be pinned to detect truncation.
    entries.sort(key=lambda item: item['decision_seq'])
    if not entries:
        return {'verified': False, 'reason': 'no_signed_decisions_yet', 'entries': 0}
    return inspect_receipts(entries, {'seller': seller_public},
                            expected_head=expected_head, expected_seq=expected_seq)
