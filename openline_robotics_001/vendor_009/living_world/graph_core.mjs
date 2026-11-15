export const SCHEMA = 'openline.graph-communication.v0.1';
export const EVENT_SCHEMA = 'openline.graph-event.v0.1';
export const SCHEMA_V04 = 'openline.graph-communication.v0.4';
export const EVENT_SCHEMA_V04 = 'openline.graph-event.v0.4';
export const SCHEMA_V05 = 'openline.graph-communication.v0.5';
export const EVENT_SCHEMA_V05 = 'openline.graph-event.v0.5';

const VALID_SCHEMAS = new Set([SCHEMA, SCHEMA_V04, SCHEMA_V05]);
const VALID_EVENT_SCHEMAS = new Set([EVENT_SCHEMA, EVENT_SCHEMA_V04, EVENT_SCHEMA_V05]);

// ============================================================================
// Pure-JS Cryptographic Primitives (FIPS 180-4 SHA-256/SHA-512 & RFC 8032 Ed25519)
// Works synchronously in both Browser and Node.js with zero external dependencies.
// ============================================================================

const K256 = new Uint32Array([
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
]);

function rotr32(x, n) {
  return (x >>> n) | (x << (32 - n));
}

export function utf8Bytes(str) {
  return new TextEncoder().encode(String(str));
}

export function canonicalJson(x) {
  if (x === null || typeof x !== 'object') return JSON.stringify(x);
  if (Array.isArray(x)) return '[' + x.map(canonicalJson).join(',') + ']';
  const keys = Object.keys(x).sort();
  return '{' + keys.map(k => JSON.stringify(k) + ':' + canonicalJson(x[k])).join(',') + '}';
}

export function sha256Hex(input) {
  const msgBytes = input instanceof Uint8Array
    ? input
    : typeof input === 'string'
      ? utf8Bytes(input)
      : utf8Bytes(canonicalJson(input));
  const ml = msgBytes.length;
  const bitLenHi = Math.floor((ml * 8) / 0x100000000);
  const bitLenLo = (ml * 8) >>> 0;
  const padLen = (ml + 9 + 63) & ~63;
  const buf = new Uint8Array(padLen);
  buf.set(msgBytes);
  buf[ml] = 0x80;
  const dv = new DataView(buf.buffer);
  dv.setUint32(padLen - 8, bitLenHi, false);
  dv.setUint32(padLen - 4, bitLenLo, false);
  let h0 = 0x6a09e667, h1 = 0xbb67ae85, h2 = 0x3c6ef372, h3 = 0xa54ff53a,
      h4 = 0x510e527f, h5 = 0x9b05688c, h6 = 0x1f83d9ab, h7 = 0x5be0cd19;
  const W = new Uint32Array(64);
  for (let off = 0; off < padLen; off += 64) {
    for (let i = 0; i < 16; i++) W[i] = dv.getUint32(off + i * 4, false);
    for (let i = 16; i < 64; i++) {
      const s0 = rotr32(W[i - 15], 7) ^ rotr32(W[i - 15], 18) ^ (W[i - 15] >>> 3);
      const s1 = rotr32(W[i - 2], 17) ^ rotr32(W[i - 2], 19) ^ (W[i - 2] >>> 10);
      W[i] = (W[i - 16] + s0 + W[i - 7] + s1) >>> 0;
    }
    let a = h0, b = h1, c = h2, d = h3, e = h4, f = h5, g = h6, h = h7;
    for (let i = 0; i < 64; i++) {
      const S1 = rotr32(e, 6) ^ rotr32(e, 11) ^ rotr32(e, 25);
      const ch = (e & f) ^ (~e & g);
      const temp1 = (h + S1 + ch + K256[i] + W[i]) >>> 0;
      const S0 = rotr32(a, 2) ^ rotr32(a, 13) ^ rotr32(a, 22);
      const maj = (a & b) ^ (a & c) ^ (b & c);
      const temp2 = (S0 + maj) >>> 0;
      h = g; g = f; f = e; e = (d + temp1) >>> 0;
      d = c; c = b; b = a; a = (temp1 + temp2) >>> 0;
    }
    h0 = (h0 + a) >>> 0; h1 = (h1 + b) >>> 0; h2 = (h2 + c) >>> 0; h3 = (h3 + d) >>> 0;
    h4 = (h4 + e) >>> 0; h5 = (h5 + f) >>> 0; h6 = (h6 + g) >>> 0; h7 = (h7 + h) >>> 0;
  }
  const out = new Uint8Array(32);
  const odv = new DataView(out.buffer);
  [h0, h1, h2, h3, h4, h5, h6, h7].forEach((v, i) => odv.setUint32(i * 4, v, false));
  return Array.from(out).map(b => b.toString(16).padStart(2, '0')).join('');
}

const K512 = [
  0x428a2f98d728ae22n, 0x7137449123ef65cdn, 0xb5c0fbcfec4d3b2fn, 0xe9b5dba58189dbbcn,
  0x3956c25bf348b538n, 0x59f111f1b605d019n, 0x923f82a4af194f9bn, 0xab1c5ed5da6d8118n,
  0xd807aa98a3030242n, 0x12835b0145706fben, 0x243185be4ee4b28cn, 0x550c7dc3d5ffb4e2n,
  0x72be5d74f27b896fn, 0x80deb1fe3b1696b1n, 0x9bdc06a725c71235n, 0xc19bf174cf692694n,
  0xe49b69c19ef14ad2n, 0xefbe4786384f25e3n, 0x0fc19dc68b8cd5b5n, 0x240ca1cc77ac9c65n,
  0x2de92c6f592b0275n, 0x4a7484aa6ea6e483n, 0x5cb0a9dcbd41fbd4n, 0x76f988da831153b5n,
  0x983e5152ee66dfabn, 0xa831c66d2db43210n, 0xb00327c898fb213fn, 0xbf597fc7beef0ee4n,
  0xc6e00bf33da88fc2n, 0xd5a79147930aa725n, 0x06ca6351e003826fn, 0x142929670a0e6e70n,
  0x27b70a8546d22ffcn, 0x2e1b21385c26c926n, 0x4d2c6dfc5ac42aedn, 0x53380d139d95b3dfn,
  0x650a73548baf63den, 0x766a0abb3c77b2a8n, 0x81c2c92e47edaee6n, 0x92722c851482353bn,
  0xa2bfe8a14cf10364n, 0xa81a664bbc423001n, 0xc24b8b70d0f89791n, 0xc76c51a30654be30n,
  0xd192e819d6ef5218n, 0xd69906245565a910n, 0xf40e35855771202an, 0x106aa07032bbd1b8n,
  0x19a4c116b8d2d0c8n, 0x1e376c085141ab53n, 0x2748774cdf8eeb99n, 0x34b0bcb5e19b48a8n,
  0x391c0cb3c5c95a63n, 0x4ed8aa4ae3418acbn, 0x5b9cca4f7763e373n, 0x682e6ff3d6b2b8a3n,
  0x748f82ee5defb2fcn, 0x78a5636f43172f60n, 0x84c87814a1f0ab72n, 0x8cc702081a6439ecn,
  0x90befffa23631e28n, 0xa4506cebde82bde9n, 0xbef9a3f7b2c67915n, 0xc67178f2e372532bn,
  0xca273eceea26619cn, 0xd186b8c721c0c207n, 0xeada7dd6cde0eb1en, 0xf57d4f7fee6ed178n,
  0x06f067aa72176fban, 0x0a637dc5a2c898a6n, 0x113f9804bef90daen, 0x1b710b35131c471bn,
  0x28db77f523047d84n, 0x32caab7b40c72493n, 0x3c9ebe0a15c9bebcn, 0x431d67c49c100d4cn,
  0x4cc5d4becb3e42b6n, 0x597f299cfc657e2an, 0x5fcb6fab3ad6faecn, 0x6c44198c4a475817n
];
const MASK64 = 0xffffffffffffffffn;
function rotr64(x, n) {
  return ((x >> BigInt(n)) | (x << BigInt(64 - n))) & MASK64;
}

function sha512Bytes(msgBytes) {
  const ml = msgBytes.length;
  const padLen = (ml + 17 + 127) & ~127;
  const buf = new Uint8Array(padLen);
  buf.set(msgBytes);
  buf[ml] = 0x80;
  const dv = new DataView(buf.buffer);
  dv.setBigUint64(padLen - 8, BigInt(ml) * 8n, false);
  let h0 = 0x6a09e667f3bcc908n, h1 = 0xbb67ae8584caa73bn, h2 = 0x3c6ef372fe94f82bn, h3 = 0xa54ff53a5f1d36f1n,
      h4 = 0x510e527fade682d1n, h5 = 0x9b05688c2b3e6c1fn, h6 = 0x1f83d9abfb41bd6bn, h7 = 0x5be0cd19137e2179n;
  const W = new Array(80).fill(0n);
  for (let off = 0; off < padLen; off += 128) {
    for (let i = 0; i < 16; i++) W[i] = dv.getBigUint64(off + i * 8, false);
    for (let i = 16; i < 80; i++) {
      const s0 = rotr64(W[i - 15], 1) ^ rotr64(W[i - 15], 8) ^ (W[i - 15] >> 7n);
      const s1 = rotr64(W[i - 2], 19) ^ rotr64(W[i - 2], 61) ^ (W[i - 2] >> 6n);
      W[i] = (W[i - 16] + s0 + W[i - 7] + s1) & MASK64;
    }
    let a = h0, b = h1, c = h2, d = h3, e = h4, f = h5, g = h6, h = h7;
    for (let i = 0; i < 80; i++) {
      const S1 = rotr64(e, 14) ^ rotr64(e, 18) ^ rotr64(e, 41);
      const ch = (e & f) ^ ((~e & MASK64) & g);
      const temp1 = (h + S1 + ch + K512[i] + W[i]) & MASK64;
      const S0 = rotr64(a, 28) ^ rotr64(a, 34) ^ rotr64(a, 39);
      const maj = (a & b) ^ (a & c) ^ (b & c);
      const temp2 = (S0 + maj) & MASK64;
      h = g; g = f; f = e; e = (d + temp1) & MASK64;
      d = c; c = b; b = a; a = (temp1 + temp2) & MASK64;
    }
    h0 = (h0 + a) & MASK64; h1 = (h1 + b) & MASK64; h2 = (h2 + c) & MASK64; h3 = (h3 + d) & MASK64;
    h4 = (h4 + e) & MASK64; h5 = (h5 + f) & MASK64; h6 = (h6 + g) & MASK64; h7 = (h7 + h) & MASK64;
  }
  const out = new Uint8Array(64);
  const odv = new DataView(out.buffer);
  [h0, h1, h2, h3, h4, h5, h6, h7].forEach((v, i) => odv.setBigUint64(i * 8, v, false));
  return out;
}

const ED_P = (1n << 255n) - 19n;
const ED_L = (1n << 252n) + 27742317777372353535851937790883648493n;
function edMod(a, m = ED_P) {
  const r = a % m;
  return r >= 0n ? r : r + m;
}
function edModPow(b, e, m = ED_P) {
  let res = 1n;
  b = edMod(b, m);
  while (e > 0n) {
    if (e & 1n) res = edMod(res * b, m);
    b = edMod(b * b, m);
    e >>= 1n;
  }
  return res;
}
function edInv(a) {
  return edModPow(a, ED_P - 2n, ED_P);
}
const ED_D = edMod(-121665n * edInv(121666n));
const ED_I = edModPow(2n, (ED_P - 1n) / 4n);
const ED_BY = edMod(4n * edInv(5n));
const ED_BX = 15112221349535400772501151409588531511454012693041857206046113283949847762202n;
const ED_B = [ED_BX, ED_BY, 1n, edMod(ED_BX * ED_BY)];

function edPtAdd(P1, P2) {
  const [X1, Y1, Z1, T1] = P1, [X2, Y2, Z2, T2] = P2;
  const A = edMod((Y1 - X1) * (Y2 - X2));
  const B = edMod((Y1 + X1) * (Y2 + X2));
  const C = edMod(T1 * 2n * ED_D * T2);
  const DD = edMod(Z1 * 2n * Z2);
  const E = edMod(B - A), F = edMod(DD - C), G = edMod(DD + C), H = edMod(B + A);
  return [edMod(E * F), edMod(G * H), edMod(F * G), edMod(E * H)];
}
function edPtMul(P1, s) {
  let R = [0n, 1n, 1n, 0n], Q = P1;
  while (s > 0n) {
    if (s & 1n) R = edPtAdd(R, Q);
    Q = edPtAdd(Q, Q);
    s >>= 1n;
  }
  return R;
}
function edPtEncode(P1) {
  const zinv = edInv(P1[2]);
  const x = edMod(P1[0] * zinv), y = edMod(P1[1] * zinv);
  const out = new Uint8Array(32);
  let tmp = y;
  for (let i = 0; i < 32; i++) {
    out[i] = Number(tmp & 0xffn);
    tmp >>= 8n;
  }
  out[31] |= Number((x & 1n) << 7n);
  return out;
}
function edPtDecode(bytes) {
  if (!bytes || bytes.length !== 32) return null;
  let y = 0n;
  for (let i = 0; i < 32; i++) y |= BigInt(bytes[i]) << BigInt(8 * i);
  const sign = (y >> 255n) & 1n;
  y &= (1n << 255n) - 1n;
  if (y >= ED_P) return null;
  const y2 = edMod(y * y);
  const u = edMod(y2 - 1n);
  const v = edMod(ED_D * y2 + 1n);
  let x = edMod(u * edModPow(v, 3n) * edModPow(edMod(u * edModPow(v, 7n)), (ED_P - 5n) / 8n));
  const vx2 = edMod(v * x * x);
  if (vx2 !== u) {
    if (vx2 === edMod(-u)) x = edMod(x * ED_I);
    else return null;
  }
  if (x === 0n && sign === 1n) return null;
  if ((x & 1n) !== sign) x = ED_P - x;
  return [x, y, 1n, edMod(x * y)];
}
function bytesToScalarLE(bytes) {
  let s = 0n;
  for (let i = 0; i < bytes.length; i++) s |= BigInt(bytes[i]) << BigInt(8 * i);
  return s;
}
export function base64UrlDecode(str) {
  if (typeof str !== 'string' || !str.length) return null;
  try {
    const b64 = str.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - (str.length % 4)) % 4);
    if (typeof atob === 'function') {
      const bin = atob(b64);
      const out = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
      return out;
    }
    return new Uint8Array(Buffer.from(b64, 'base64'));
  } catch (_) {
    return null;
  }
}
export function verifyEd25519(pub32, msgBytes, sig64) {
  if (!pub32 || !sig64 || pub32.length !== 32 || sig64.length !== 64) return false;
  const A = edPtDecode(pub32);
  if (!A) return false;
  const R_bytes = sig64.slice(0, 32);
  const S_bytes = sig64.slice(32, 64);
  const R = edPtDecode(R_bytes);
  if (!R) return false;
  const S = bytesToScalarLE(S_bytes);
  if (S >= ED_L) return false;
  const hInput = new Uint8Array(64 + msgBytes.length);
  hInput.set(R_bytes, 0);
  hInput.set(pub32, 32);
  hInput.set(msgBytes, 64);
  const k = bytesToScalarLE(sha512Bytes(hInput)) % ED_L;
  const lhs = edPtEncode(edPtMul(ED_B, S));
  const rhs = edPtEncode(edPtAdd(R, edPtMul(A, k)));
  for (let i = 0; i < 32; i++) if (lhs[i] !== rhs[i]) return false;
  return true;
}

export function verifyReceiptEnvelope(envelope, trustedReceiverKeys = []) {
  if (!envelope || typeof envelope !== 'object') {
    return { verified: false, reason: 'missing_receipt_envelope' };
  }
  const env = envelope.receipt && typeof envelope.receipt === 'object' ? envelope.receipt : envelope;
  const { payload, payload_sha256, signer_pub, signature } = env;
  if (!payload || typeof payload !== 'object' || typeof payload_sha256 !== 'string' || typeof signer_pub !== 'string' || typeof signature !== 'string') {
    return { verified: false, reason: 'invalid_envelope_schema' };
  }
  const allowedKeys = Array.isArray(trustedReceiverKeys) ? trustedReceiverKeys.filter(Boolean) : [];
  if (allowedKeys.length === 0) {
    return { verified: false, reason: 'missing_trusted_receiver_key' };
  }
  if (!allowedKeys.includes(signer_pub)) {
    return { verified: false, reason: 'untrusted_receiver_signer_key' };
  }
  const rawBytes = utf8Bytes(canonicalJson(payload));
  const computedSha = sha256Hex(rawBytes);
  if (computedSha !== payload_sha256) {
    return { verified: false, reason: 'receipt_payload_digest_mismatch' };
  }
  const pubBytes = base64UrlDecode(signer_pub);
  const sigBytes = base64UrlDecode(signature);
  if (!verifyEd25519(pubBytes, rawBytes, sigBytes)) {
    return { verified: false, reason: 'invalid_ed25519_signature' };
  }
  return { verified: true, payload, payload_sha256, signer_pub };
}

export function verifyGenieBundleReceipt(bundle, options = {}) {
  if (!bundle || typeof bundle !== 'object' || !bundle.accepted || !bundle.accepted.state) {
    return { verified: false, status: 'UNVERIFIED_IMPORT', reason: 'invalid_bundle_structure' };
  }
  const globalKeys = (typeof globalThis !== 'undefined' && Array.isArray(globalThis.__GENIE_TRUSTED_RECEIVER_KEYS))
    ? globalThis.__GENIE_TRUSTED_RECEIVER_KEYS
    : [];
  const trustedKeys = Array.isArray(options.trustedReceiverKeys)
    ? options.trustedReceiverKeys
    : options.trustedReceiverPub
      ? [options.trustedReceiverPub]
      : globalKeys;

  if (!trustedKeys || trustedKeys.length === 0) {
    return { verified: false, status: 'UNVERIFIED_IMPORT', reason: 'missing_trusted_receiver_key' };
  }
  const rawReceipt = bundle.accepted.receipt;
  if (!rawReceipt) {
    return { verified: false, status: 'UNVERIFIED_IMPORT', reason: 'missing_receipt' };
  }
  const envCheck = verifyReceiptEnvelope(rawReceipt, trustedKeys);
  if (!envCheck.verified) {
    return { verified: false, status: 'UNVERIFIED_IMPORT', reason: envCheck.reason };
  }
  if (bundle.receiver_public_key && bundle.receiver_public_key !== envCheck.signer_pub) {
    return { verified: false, status: 'UNVERIFIED_IMPORT', reason: 'bundle_receiver_key_mismatch' };
  }
  const p = envCheck.payload;
  if (p.schema !== 'openline.guard.receipt.v1' || p.status !== 'COMMITTED') {
    return { verified: false, status: 'UNVERIFIED_IMPORT', reason: 'receipt_not_committed' };
  }
  const projectId = String(bundle.project_id || '');
  if (!projectId || p.target?.table !== 'genie_accepted' || p.target?.id !== projectId || p.task_id !== `task-${projectId}`) {
    return { verified: false, status: 'UNVERIFIED_IMPORT', reason: 'receipt_project_target_mismatch' };
  }
  let computedStateSha = sha256Hex(bundle.accepted.state);
  if (computedStateSha !== bundle.accepted.state_sha256 && typeof bundle.accepted.state_canonical_json === 'string') {
    try {
      const parsedCanonical = JSON.parse(bundle.accepted.state_canonical_json);
      if (canonicalJson(parsedCanonical) === canonicalJson(bundle.accepted.state)) {
        computedStateSha = sha256Hex(bundle.accepted.state_canonical_json);
      }
    } catch (_) {}
  }
  if (computedStateSha !== bundle.accepted.state_sha256) {
    return { verified: false, status: 'UNVERIFIED_IMPORT', reason: 'state_sha256_mismatch' };
  }
  const accVersion = Number(bundle.accepted.version ?? bundle.version ?? 0);
  if (bundle.version !== undefined && bundle.accepted.version !== undefined && Number(bundle.version) !== Number(bundle.accepted.version)) {
    return { verified: false, status: 'UNVERIFIED_IMPORT', reason: 'bundle_version_mismatch' };
  }
  const expectedReqPayload = {
    amount: 1,
    project_id: projectId,
    state_sha256: computedStateSha,
    version: accVersion
  };
  const expectedReqSha = sha256Hex(expectedReqPayload);
  if (p.payload_sha256 !== expectedReqSha) {
    return { verified: false, status: 'UNVERIFIED_IMPORT', reason: 'stale_or_mismatched_state_binding' };
  }
  if (typeof p.effect_sha256 !== 'string' || !/^[0-9a-f]{64}$/.test(p.effect_sha256)) {
    return { verified: false, status: 'UNVERIFIED_IMPORT', reason: 'missing_or_invalid_effect_sha256' };
  }
  if (bundle.accepted.effect_sha256 && bundle.accepted.effect_sha256 !== p.effect_sha256) {
    return { verified: false, status: 'UNVERIFIED_IMPORT', reason: 'effect_sha256_mismatch' };
  }
  if (Array.isArray(bundle.receipts) && bundle.receipts.length > 0) {
    const r0 = bundle.receipts[0];
    if (r0.receipt_id && r0.receipt_id !== p.receipt_id) {
      return { verified: false, status: 'UNVERIFIED_IMPORT', reason: 'receipt_id_index_mismatch' };
    }
    if (r0.sha256 && r0.sha256 !== computedStateSha) {
      return { verified: false, status: 'UNVERIFIED_IMPORT', reason: 'receipt_list_sha256_mismatch' };
    }
  }
  return {
    verified: true,
    status: 'RECEIVER_VERIFIED',
    reason: 'verified',
    receipt_id: p.receipt_id,
    signer_pub: envCheck.signer_pub,
    state_sha256: computedStateSha,
    effect_sha256: p.effect_sha256,
    payload_sha256: envCheck.payload_sha256,
    version: accVersion
  };
}

// ============================================================================
// Graph Nodes, Domains & Constraint/Counterfactual Intelligence
// ============================================================================

const node = (id, label, category, detail, stage = 'planned', extra = {}) => ({
  id,
  label,
  category,
  detail,
  state: stage,
  ...extra
});
const e = (from, to, kind = 'depends_on') => ({ from, to, kind });

export const DEMOS = {
  barber: {
    title: 'The Barber Studio',
    subtitle: 'Mobile chair dispatch, conflict guard & repeat cadence',
    wish: 'Build a mobile barber booking application',
    domain_unit: 'bookings/day',
    baseline_metrics: {
      daily_capacity: 18,
      unit: 'bookings/day',
      avg_ticket_usd: 42,
      margin_per_loaf_usd: 32,
      fixed_cost_usd: 110,
      daily_revenue_usd: 756,
      uncertainty_pct: 8,
      double_book_risk: '0% (Conflict Guard Active)'
    },
    nodes: [
      node('wish', 'Your wish', 'intent', 'Build a booking tool for a mobile barber.', 'accepted', {
        capacity: 40, unit: 'bookings/day', role: 'Owner intent & acceptance boundary'
      }),
      node('customers', 'Customers', 'data', 'Local customer records; no external service.', 'planned', {
        capacity: 36, unit: 'bookings/day', subparts: ['Client Roster', 'Cut Notes', 'VIP History']
      }),
      node('services', 'Services', 'data', 'Prices and durations for available services.', 'planned', {
        capacity: 32, unit: 'bookings/day', subparts: ['Fade (45m · $45)', 'Beard Trim (20m · $25)', 'Full Cut (60m · $60)']
      }),
      node('calendar', 'Calendar', 'interface', 'Appointment times and availability (1 chair · 18 slots/day).', 'planned', {
        capacity: 18, unit: 'bookings/day', subparts: ['Chair 1 Slot Grid', 'Travel Buffer (15m)', 'Daylight Window']
      }),
      node('conflicts', 'Conflict checks', 'logic', 'Prevent overlapping appointments and travel collisions.', 'planned', {
        capacity: 28, unit: 'bookings/day', subparts: ['Overlap Detector', 'Route Gap Guard', 'Atomic Slot Lock']
      }),
      node('bookings', 'Booking screen', 'interface', 'Working appointment creation, editing, and status workflow.', 'planned', {
        capacity: 24, unit: 'bookings/day', subparts: ['Quick-Book Form', 'Status Toggle', 'Live Day Total']
      }),
      node('receipts', 'Portable data', 'artifact', 'JSON/CSV-ready owner data with local persistence.', 'planned', {
        capacity: 35, unit: 'bookings/day', subparts: ['LocalStorage Vault', 'CSV Escaper', 'Receipt Ledger']
      }),
      node('exports', 'Exportable app', 'artifact', 'Standalone zero-dependency HTML application ready to keep.', 'planned', {
        capacity: 35, unit: 'bookings/day', subparts: ['Single-File HTML', 'Offline Runtime', 'Zero Lock-In Bundle']
      })
    ],
    edges: [
      e('wish', 'customers'),
      e('wish', 'services'),
      e('wish', 'calendar'),
      e('customers', 'bookings'),
      e('services', 'bookings'),
      e('calendar', 'conflicts'),
      e('conflicts', 'bookings'),
      e('bookings', 'receipts'),
      e('receipts', 'exports')
    ],
    paths: [
      {
        id: 'team',
        label: 'Add a second barber',
        detail: 'Expand calendar from 1 chair (18/day) to 2 chairs (32/day). Shifts limit to Booking screen (24/day).',
        after: 'calendar',
        delta: {
          node: 'calendar',
          capacity_delta: 14,
          capex_usd: 2400,
          fixed_cost_delta_usd: 95,
          revenue_delta_usd: 504,
          summary: 'Splits calendar into Chair 1 & Chair 2 parallel dispatch lanes (Calendar 18 → 32 bookings/day; Booking screen 24/day becomes binding bottleneck)'
        }
      },
      {
        id: 'recurring',
        label: 'Recurring visits',
        detail: 'Add 2-week / 4-week repeat booking flow (+6 booking screen throughput, 24 → 30/day).',
        after: 'bookings',
        delta: {
          node: 'bookings',
          capacity_delta: 6,
          capex_usd: 0,
          fixed_cost_delta_usd: 10,
          revenue_delta_usd: 168,
          summary: 'Adds repeat cadence selector to booking screen (Booking screen 24 → 30/day; unlocks 28/day when paired with 2nd barber)'
        }
      },
      {
        id: 'route_opt',
        label: 'Compact route zones',
        detail: 'Cluster mobile stops by ZIP code (+8 calendar slots/day, 18 → 26/day, $0 CapEx).',
        after: 'calendar',
        delta: {
          node: 'calendar',
          capacity_delta: 8,
          capex_usd: 0,
          fixed_cost_delta_usd: 5,
          summary: 'Clusters mobile stops by neighborhood zone (Calendar 18 → 24 bookings/day; matches Booking screen ceiling without 2nd chair CapEx)'
        }
      },
      {
        id: 'portable',
        label: 'Keep what I have',
        detail: 'Preserve accepted barber studio state and export standalone app + verified graph.',
        after: 'exports',
        export: true
      }
    ]
  },
  bakery: {
    title: 'Hearth & Crumb',
    subtitle: 'Steam-deck baking, fermentation & morning counter flow',
    wish: 'Design a neighborhood bakery',
    domain_unit: 'loaves/day',
    baseline_metrics: {
      daily_capacity: 174,
      unit: 'loaves/day',
      margin_per_loaf_usd: 4.5,
      fixed_cost_usd: 140,
      net_daily_usd: 643,
      uncertainty_pct: 7
    },
    nodes: [
      node('wish', 'Your wish', 'intent', 'Design a small neighborhood bakery.', 'accepted', {
        capacity: 500, unit: 'loaves/day', role: 'Owner vision & capital boundary'
      }),
      node('demand', 'Demand', 'data', 'Neighborhood morning & cafe wholesale demand (320 loaves/day).', 'planned', {
        capacity: 320, unit: 'loaves/day', subparts: ['Walk-In Morning Rush (210)', 'Local Cafe Accounts (110)']
      }),
      node('ingredients', 'Ingredients', 'resource', 'Organic flour, levain bulk fermentation, and 280-loaf cold retarder rack.', 'planned', {
        capacity: 280, unit: 'loaves/day', subparts: ['Stone-Milled Flour Silo', 'Levain Culture Mother', '280-Loaf Proofing Rack']
      }),
      node('staff', 'Staff', 'resource', '1 lead baker shaping & loading limit: 240 loaves/day per 8h shift.', 'planned', {
        capacity: 240, unit: 'loaves/day', subparts: ['Lead Baker (240 loaves/day)', 'Bench Shaping Table', '05:00–13:00 Shift']
      }),
      node('oven', 'Oven', 'resource', '1 steam-injected deck oven: 24 loaves/batch, 50-min cycle = 174 loaves/day.', 'planned', {
        capacity: 174, unit: 'loaves/day', subparts: ['Hearth Deck #1 (24 loaves)', 'Steam Injection Manifold', '50m Thermal Recovery']
      }),
      node('schedule', 'Production plan', 'logic', 'Compute throughput from oven, staffing, and proofing constraints.', 'planned', {
        capacity: 360, unit: 'loaves/day', subparts: ['Batch Sequencer', 'Bottleneck Solver', 'Margin Calculator']
      }),
      node('shop', 'Shop experience', 'interface', 'Espresso & warm loaf counter service flow (300 loaves/day).', 'planned', {
        capacity: 300, unit: 'loaves/day', subparts: ['Cooling Wire Wall', 'Slicing & Wrapping Station', 'Counter POS']
      }),
      node('scenario', 'What-if scenario', 'artifact', 'Compare proposing a 2nd oven against the 240-loaf Baker Staffing limit.', 'planned', {
        capacity: 400, unit: 'loaves/day', subparts: ['Accepted Baseline (174/day)', 'Proposed 2-Oven Model (240/day)', 'Labor Bottleneck Alert']
      })
    ],
    edges: [
      e('wish', 'demand'),
      e('wish', 'ingredients'),
      e('wish', 'staff'),
      e('wish', 'oven'),
      e('ingredients', 'schedule'),
      e('staff', 'schedule'),
      e('oven', 'schedule'),
      e('demand', 'shop'),
      e('schedule', 'shop'),
      e('shop', 'scenario')
    ],
    paths: [
      {
        id: 'oven2',
        label: 'Another oven?',
        detail: 'Add Deck Oven #2 (174 → 348 oven cap). Exposes Staff (240/day) as new bottleneck.',
        after: 'oven',
        delta: {
          node: 'oven',
          capacity_delta: 174,
          capex_usd: 18500,
          fixed_cost_delta_usd: 15,
          summary: 'Inserts Twin Steam Deck Oven #2 (Oven capacity 174 → 348 loaves/day; Staff 240 loaves/day becomes binding bottleneck)'
        }
      },
      {
        id: 'hours',
        label: 'Adjust shift schedule',
        detail: 'Staggered 04:30–14:30 bake shift lifts Staff 240 → 300 loaves/day (+$35/day overtime).',
        after: 'staff',
        delta: {
          node: 'staff',
          capacity_delta: 60,
          capex_usd: 0,
          fixed_cost_delta_usd: 35,
          summary: 'Staggers prep & bake shifts (Staff capacity 240 → 300 loaves/day; unlocks 280 loaves/day at low fixed cost)'
        }
      },
      {
        id: 'add_baker',
        label: 'Add a second baker',
        detail: 'Lift Staff limit 240 → 400 loaves/day (+$165/day wage) to unlock 2nd oven.',
        after: 'staff',
        delta: {
          node: 'staff',
          capacity_delta: 160,
          capex_usd: 600,
          fixed_cost_delta_usd: 165,
          summary: 'Adds Second Shaping Baker (Staff capacity 240 → 400 loaves/day; clamped at 280 loaves/day by Proofing Rack)'
        }
      },
      {
        id: 'retarder_rack',
        label: 'Add cold retarder rack',
        detail: 'Expand cold fermentation & proofing rack 280 → 340 loaves/day (+$12/day power).',
        after: 'ingredients',
        delta: {
          node: 'ingredients',
          capacity_delta: 60,
          capex_usd: 3200,
          fixed_cost_delta_usd: 12,
          summary: 'Adds 2nd Roll-In Retarder Proofer (Ingredients/Proofing 280 → 340 loaves/day)'
        }
      },
      {
        id: 'portable',
        label: 'Keep what I have',
        detail: 'Preserve accepted bakery plan and export standalone calculator + JSONL trace.',
        after: 'scenario',
        export: true
      }
    ]
  },
  research: {
    title: 'The Evidence Atlas',
    subtitle: 'Primary archival verification & counterevidence synthesis',
    wish: 'Investigate why an old policy failed',
    domain_unit: 'verified claims',
    baseline_metrics: {
      daily_capacity: 12,
      unit: 'verified claims',
      margin_per_loaf_usd: 15,
      fixed_cost_usd: 40,
      uncertainty_pct: 10,
      primary_sources: 18,
      unresolved_disputes: 2
    },
    nodes: [
      node('wish', 'Question', 'intent', 'What happened, and what evidence supports it?', 'accepted', {
        capacity: 50, unit: 'verified claims'
      }),
      node('sources', 'Sources', 'data', 'Original archival documents and primary records (18 verified).', 'planned', {
        capacity: 18, unit: 'verified claims', subparts: ['Municipal Ledger 1998', 'Committee Transcript', 'Audit Memo']
      }),
      node('timeline', 'Timeline', 'data', 'Chronology, with exact dates and uncertainty intervals.', 'planned', {
        capacity: 22, unit: 'verified claims', subparts: ['Phase I Rollout', 'Budget Freeze Event', 'Post-Mortem Filing']
      }),
      node('hypotheses', 'Explanations', 'logic', 'Competing causal mechanisms tested against primary records.', 'planned', {
        capacity: 16, unit: 'verified claims', subparts: ['Procurement Delay', 'Staffing Attrition', 'Statutory Cap']
      }),
      node('counter', 'Counterarguments', 'logic', 'Evidence that could undermine or falsify the leading claim.', 'planned', {
        capacity: 12, unit: 'verified claims', subparts: ['Control City Comparison', 'Weather Confounder']
      }),
      node('claims', 'Claim map', 'interface', 'Which claims follow from which corroborated sources?', 'planned', {
        capacity: 15, unit: 'verified claims', subparts: ['Citation Link Graph', 'Confidence Weights']
      }),
      node('review', 'Review gate', 'interface', 'Keep unverified material out of accepted conclusions.', 'planned', {
        capacity: 14, unit: 'verified claims', subparts: ['Owner Sign-Off Gate', 'Quarantine Log']
      }),
      node('brief', 'Research brief', 'artifact', 'A sourced, revisable synthesis with inline citations.', 'planned', {
        capacity: 20, unit: 'verified claims', subparts: ['Executive Brief', 'Source Appendix', 'JSONL Audit Trail']
      })
    ],
    edges: [
      e('wish', 'sources'),
      e('wish', 'timeline'),
      e('sources', 'hypotheses'),
      e('timeline', 'hypotheses'),
      e('hypotheses', 'counter'),
      e('sources', 'claims'),
      e('counter', 'review'),
      e('claims', 'review'),
      e('review', 'brief')
    ],
    paths: [
      {
        id: 'challenge',
        label: 'Challenge the claim',
        detail: 'Add a counterevidence review (+6 falsification checks, 12 → 18). Shifts limit to Review gate (14).',
        after: 'counter',
        delta: { node: 'counter', capacity_delta: 6, capex_usd: 0, fixed_cost_delta_usd: 12, summary: 'Adds adversarial counterevidence matrix (Counterarguments 12 → 18; Review gate 14 becomes bottleneck)' }
      },
      {
        id: 'review_panel',
        label: 'Expand review gate',
        detail: 'Add dual-reviewer corroboration checklist (+4 review gate capacity, 14 → 18).',
        after: 'review',
        delta: { node: 'review', capacity_delta: 4, capex_usd: 0, fixed_cost_delta_usd: 8, summary: 'Expands Review Gate capacity 14 → 18 verified claims (unlocks 15 claims limited by Claim map)' }
      },
      {
        id: 'compare',
        label: 'Find a precedent',
        detail: 'Explore a parallel historical case (+4 primary sources, 18 → 22).',
        after: 'timeline',
        delta: { node: 'sources', capacity_delta: 4, capex_usd: 0, fixed_cost_delta_usd: 6, summary: 'Cross-links parallel municipal archive' }
      },
      {
        id: 'portable',
        label: 'Keep what I have',
        detail: 'Export the verified research graph and event trace.',
        after: 'brief',
        export: true
      }
    ]
  }
};

const VALID_STATES = new Set([
  'planned',
  'building',
  'ready',
  'tentative',
  'accepted',
  'rejected',
  'blocked',
  'stopped',
  'unknown_external_effect',
  'reopened'
]);
const VALID_CATEGORIES = new Set(['intent', 'data', 'resource', 'logic', 'interface', 'artifact', 'research', 'other']);

export function clone(x) {
  return JSON.parse(JSON.stringify(x));
}

export function registerDomainDefinition(key, def) {
  if (!key || typeof key !== 'string' || !def || typeof def !== 'object') {
    throw Error('Invalid domain registration');
  }
  DEMOS[key] = clone(def);
  return DEMOS[key];
}

export function validateGraph(g) {
  if (
    !g ||
    !VALID_SCHEMAS.has(g.schema) ||
    typeof g.title !== 'string' ||
    g.title.length > 120 ||
    !Array.isArray(g.nodes) ||
    !Array.isArray(g.edges) ||
    g.nodes.length < 1 ||
    g.nodes.length > 64 ||
    g.edges.length > 140
  ) {
    throw Error('Unsupported graph or size');
  }
  const ids = new Set();
  for (const n of g.nodes) {
    if (
      !n ||
      typeof n.id !== 'string' ||
      !/^[A-Za-z0-9_-]{1,48}$/.test(n.id) ||
      ids.has(n.id) ||
      typeof n.label !== 'string' ||
      n.label.length > 80 ||
      typeof n.detail !== 'string' ||
      n.detail.length > 400 ||
      !VALID_STATES.has(n.state) ||
      !VALID_CATEGORIES.has(n.category)
    ) {
      throw Error('Invalid node');
    }
    ids.add(n.id);
  }
  for (const x of g.edges) {
    if (!x || !ids.has(x.from) || !ids.has(x.to) || x.from === x.to || !['depends_on', 'informs', 'conflicts_with'].includes(x.kind)) {
      throw Error('Invalid link');
    }
  }
  if ((g.paths || []).length > 12) throw Error('Too many paths');
  return true;
}

// Compute active path deltas applied via branch_* nodes in the graph
function getActiveBranchDeltas(graph) {
  const deltas = [];
  for (const n of graph.nodes) {
    if (n.id.startsWith('branch_') && ['ready', 'tentative', 'accepted', 'building', 'planned'].includes(n.state) && n.state !== 'rejected') {
      if (Array.isArray(n.deltas)) {
        deltas.push(...n.deltas);
      } else if (n.delta) {
        deltas.push(n.delta);
      } else {
        const pid = n.id.slice('branch_'.length);
        const p = (graph.paths || []).find(x => x.id === pid);
        if (p?.delta) deltas.push(p.delta);
        if (Array.isArray(p?.deltas)) deltas.push(...p.deltas);
      }
    }
  }
  return deltas;
}

export function computeConstraintResonance(graph, paramOverrides = {}, extraDeltas = []) {
  const unit = graph.domain_unit || 'units/day';
  const baseMetrics = graph.baseline_metrics || {};
  const activeDeltas = [...getActiveBranchDeltas(graph), ...extraDeltas];
  const capacities = [];

  for (const n of graph.nodes) {
    if (n.category === 'intent' || n.id.startsWith('branch_') || n.id.startsWith('exp_') || n.id.startsWith('rej_') || n.id.startsWith('out_')) continue;
    const baseCap = typeof n.capacity === 'number' ? n.capacity : null;
    if (baseCap === null) continue;
    let effectiveCap = baseCap + (Number(paramOverrides[n.id]) || 0);
    for (const d of activeDeltas) {
      if (d && d.node === n.id) {
        effectiveCap += Number(d.capacity_delta) || 0;
      }
    }
    capacities.push({
      id: n.id,
      label: n.label,
      category: n.category,
      state: n.state,
      standing: n.standing || 'CURRENT',
      base_capacity: baseCap,
      effective_capacity: Math.max(1, effectiveCap),
      unit: n.unit || unit
    });
  }
  if (!capacities.length) {
    return {
      unit,
      system_throughput: 0,
      baseline_throughput: 0,
      bottleneck_id: null,
      bottleneck_label: 'None',
      next_bottleneck_id: null,
      next_bottleneck_label: 'None',
      third_bottleneck_id: null,
      third_bottleneck_label: 'None',
      nodes: [],
      affected_edges: []
    };
  }
  const baselineSorted = [...capacities].sort((a, b) => a.base_capacity - b.base_capacity);
  const effectiveSorted = [...capacities].sort((a, b) => a.effective_capacity - b.effective_capacity);
  const baselineThroughput = baselineSorted[0].base_capacity;
  const systemThroughput = effectiveSorted[0].effective_capacity;
  const bottleneck = effectiveSorted[0];
  const nextBottleneck = effectiveSorted[1] || effectiveSorted[0];
  const thirdBottleneck = effectiveSorted[2] || nextBottleneck;

  const marginPerUnit = Number(baseMetrics.margin_per_loaf_usd || baseMetrics.avg_ticket_usd || 4.5);
  const baseFixedCost = Number(baseMetrics.fixed_cost_usd || 0);
  let fixedCost = baseFixedCost;
  let totalCapexUsd = 0;
  for (const d of activeDeltas) {
    if (d?.fixed_cost_delta_usd) fixedCost += Number(d.fixed_cost_delta_usd);
    if (d?.capex_usd) totalCapexUsd += Number(d.capex_usd);
  }
  const baselineNetUsd = Math.round(baselineThroughput * marginPerUnit - baseFixedCost);
  const proposedNetUsd = Math.round(systemThroughput * marginPerUnit - fixedCost);
  const netDailyDeltaUsd = proposedNetUsd - baselineNetUsd;
  const paybackDays = totalCapexUsd > 0 && netDailyDeltaUsd > 0
    ? Math.ceil(totalCapexUsd / netDailyDeltaUsd)
    : totalCapexUsd === 0 && netDailyDeltaUsd > 0
      ? 0
      : null;

  const uncPct = Number(baseMetrics.uncertainty_pct || 7) / 100;
  const throughputLow = Math.round(systemThroughput * (1 - uncPct));
  const throughputHigh = Math.round(systemThroughput * (1 + uncPct));
  const netLowUsd = Math.round(throughputLow * marginPerUnit - fixedCost);
  const netHighUsd = Math.round(throughputHigh * marginPerUnit - fixedCost);

  // Determine affected production paths (edges connected to modified nodes or bottlenecks)
  const modifiedNodeIds = new Set(
    capacities.filter(c => c.effective_capacity !== c.base_capacity).map(c => c.id)
  );
  const affectedEdges = (graph.edges || [])
    .filter(ed => modifiedNodeIds.has(ed.from) || modifiedNodeIds.has(ed.to) || ed.from === bottleneck.id || ed.to === bottleneck.id)
    .map(ed => ({
      from: ed.from,
      to: ed.to,
      role: (ed.from === bottleneck.id || ed.to === bottleneck.id) ? 'binding_choke' : 'unlocked_flow'
    }));

  const enrichedNodes = capacities.map(c => ({
    ...c,
    capacity_delta: c.effective_capacity - c.base_capacity,
    shadow_slack: c.effective_capacity - systemThroughput,
    utilization_pct: Math.min(100, Math.round((systemThroughput / c.effective_capacity) * 100)),
    is_binding_bottleneck: c.id === bottleneck.id,
    is_secondary_bottleneck: c.id === nextBottleneck.id && nextBottleneck.id !== bottleneck.id,
    was_baseline_bottleneck: c.id === baselineSorted[0].id
  }));

  return {
    unit,
    baseline_throughput: baselineThroughput,
    system_throughput: systemThroughput,
    throughput_delta: systemThroughput - baselineThroughput,
    baseline_bottleneck_id: baselineSorted[0].id,
    baseline_bottleneck_label: baselineSorted[0].label,
    bottleneck_id: bottleneck.id,
    bottleneck_label: bottleneck.label,
    bottleneck_capacity: bottleneck.effective_capacity,
    bottleneck_shifted: bottleneck.id !== baselineSorted[0].id,
    next_bottleneck_id: nextBottleneck.id,
    next_bottleneck_label: nextBottleneck.label,
    next_bottleneck_capacity: nextBottleneck.effective_capacity,
    third_bottleneck_id: thirdBottleneck.id,
    third_bottleneck_label: thirdBottleneck.label,
    third_bottleneck_capacity: thirdBottleneck.effective_capacity,
    margin_per_unit_usd: marginPerUnit,
    baseline_fixed_cost_usd: baseFixedCost,
    proposed_fixed_cost_usd: fixedCost,
    total_capex_usd: totalCapexUsd,
    baseline_net_daily_usd: baselineNetUsd,
    proposed_net_daily_usd: proposedNetUsd,
    net_daily_delta_usd: netDailyDeltaUsd,
    payback_days: paybackDays,
    uncertainty_pct: Math.round(uncPct * 100),
    throughput_band: [throughputLow, throughputHigh],
    net_daily_band_usd: [netLowUsd, netHighUsd],
    affected_edges: affectedEdges,
    nodes: enrichedNodes
  };
}

// Evaluate any single or multi-delta intervention against the current graph state
export function evaluateInterventionCounterfactual(graph, pathItem, currentOverrides = {}) {
  const curRes = computeConstraintResonance(graph, currentOverrides);
  const deltas = Array.isArray(pathItem?.deltas)
    ? pathItem.deltas
    : pathItem?.delta
      ? [pathItem.delta]
      : [];
  if (!deltas.length) {
    return {
      id: pathItem?.id || 'noop',
      label: pathItem?.label || 'No-op',
      classification: 'EXPORT_OR_KEEP',
      throughput_before: curRes.system_throughput,
      throughput_after: curRes.system_throughput,
      throughput_gain: 0,
      net_daily_before_usd: curRes.proposed_net_daily_usd,
      net_daily_after_usd: curRes.proposed_net_daily_usd,
      net_daily_gain_usd: 0,
      capex_usd: 0,
      fixed_cost_delta_usd: 0,
      bottleneck_before: curRes.bottleneck_id,
      bottleneck_after: curRes.bottleneck_id,
      bottleneck_after_label: curRes.bottleneck_label,
      explanation: pathItem?.detail || 'Preserve current accepted state.'
    };
  }
  const postRes = computeConstraintResonance(graph, currentOverrides, deltas);
  const throughputGain = postRes.system_throughput - curRes.system_throughput;
  const netGainUsd = postRes.proposed_net_daily_usd - curRes.proposed_net_daily_usd;
  const capexUsd = deltas.reduce((s, d) => s + (Number(d.capex_usd) || 0), 0);
  const fixedDeltaUsd = deltas.reduce((s, d) => s + (Number(d.fixed_cost_delta_usd) || 0), 0);
  const totalNodeDelta = deltas.reduce((s, d) => s + (Number(d.capacity_delta) || 0), 0);

  let classification = 'DIRECT_UNLOCK';
  let explanation = '';
  if (totalNodeDelta > 0 && throughputGain === 0) {
    classification = 'COUNTERFACTUAL_TRAP';
    explanation = `Counterfactual Trap: +${totalNodeDelta} ${curRes.unit} local capacity yields +0 ${curRes.unit} system gain because ${curRes.bottleneck_label} (${curRes.system_throughput} ${curRes.unit}) still clamps flow.`;
  } else if (deltas.length > 1 && throughputGain > 0) {
    classification = 'SYNERGISTIC_COMBO';
    explanation = `Synergistic Unlock: Combining ${deltas.length} interventions lifts throughput ${curRes.system_throughput} → ${postRes.system_throughput} ${curRes.unit} (+$${netGainUsd}/day net); ceiling is ${postRes.bottleneck_label} (${postRes.bottleneck_capacity} ${curRes.unit}).`;
  } else if (postRes.bottleneck_id !== curRes.bottleneck_id && throughputGain > 0) {
    classification = 'BOTTLENECK_SHIFT';
    const targetNode = postRes.nodes.find(n => n.id === deltas[0].node);
    const wastedSlack = targetNode ? targetNode.shadow_slack : 0;
    explanation = `Bottleneck Shift: Lifts output ${curRes.system_throughput} → ${postRes.system_throughput} ${curRes.unit} (+$${netGainUsd}/day), shifting binding constraint from ${curRes.bottleneck_label} to ${postRes.bottleneck_label} (${wastedSlack} ${curRes.unit} unused headroom).`;
  } else {
    explanation = `Lifts system throughput ${curRes.system_throughput} → ${postRes.system_throughput} ${curRes.unit} (+$${netGainUsd}/day net).`;
  }

  return {
    id: pathItem.id,
    label: pathItem.label,
    classification,
    deltas: clone(deltas),
    throughput_before: curRes.system_throughput,
    throughput_after: postRes.system_throughput,
    throughput_gain: throughputGain,
    net_daily_before_usd: curRes.proposed_net_daily_usd,
    net_daily_after_usd: postRes.proposed_net_daily_usd,
    net_daily_gain_usd: netGainUsd,
    capex_usd: capexUsd,
    fixed_cost_delta_usd: fixedDeltaUsd,
    payback_days: capexUsd > 0 && netGainUsd > 0 ? Math.ceil(capexUsd / netGainUsd) : (capexUsd === 0 && netGainUsd > 0 ? 0 : null),
    bottleneck_before: curRes.bottleneck_id,
    bottleneck_before_label: curRes.bottleneck_label,
    bottleneck_after: postRes.bottleneck_id,
    bottleneck_after_label: postRes.bottleneck_label,
    throughput_band: postRes.throughput_band,
    net_daily_band_usd: postRes.net_daily_band_usd,
    explanation
  };
}

// Discover super-additive pairs of interventions (where P1 + P2 unlocks more than P1 alone + P2 alone)
export function discoverSynergisticCombos(graph, currentOverrides = {}) {
  const candidates = (graph.paths || []).filter(p => !p.export && p.delta && !graph.nodes.some(n => n.id === 'branch_' + p.id && n.state !== 'rejected'));
  const singleEvals = new Map();
  for (const p of candidates) {
    singleEvals.set(p.id, evaluateInterventionCounterfactual(graph, p, currentOverrides));
  }
  const combos = [];
  for (let i = 0; i < candidates.length; i++) {
    for (let j = i + 1; j < candidates.length; j++) {
      const a = candidates[i], b = candidates[j];
      if (a.delta.node === b.delta.node) continue;
      const evA = singleEvals.get(a.id);
      const evB = singleEvals.get(b.id);
      const comboItem = {
        id: `combo_${a.id}_${b.id}`,
        label: `Combo: ${a.label.replace(/\?$/, '')} + ${b.label.replace(/\?$/, '')}`,
        detail: `Synergistic dual intervention on ${a.delta.node} and ${b.delta.node}.`,
        after: b.after || a.after,
        deltas: [clone(a.delta), clone(b.delta)],
        component_ids: [a.id, b.id]
      };
      const evAB = evaluateInterventionCounterfactual(graph, comboItem, currentOverrides);
      const sumStandaloneGain = evA.throughput_gain + evB.throughput_gain;
      const synergyThroughputBonus = evAB.throughput_gain - sumStandaloneGain;
      const bestSingleNet = Math.max(evA.net_daily_gain_usd, evB.net_daily_gain_usd);
      const netAdvantageOverSingle = evAB.net_daily_gain_usd - bestSingleNet;

      if (synergyThroughputBonus > 0 && netAdvantageOverSingle > 0) {
        combos.push({
          ...comboItem,
          evaluation: evAB,
          synergy_throughput_bonus: synergyThroughputBonus,
          net_advantage_over_best_single_usd: netAdvantageOverSingle,
          standalone_gains: { [a.id]: evA.throughput_gain, [b.id]: evB.throughput_gain }
        });
      }
    }
  }
  combos.sort((x, y) => (y.evaluation.net_daily_gain_usd - x.evaluation.net_daily_gain_usd) || (x.evaluation.capex_usd - y.evaluation.capex_usd));
  return combos;
}

export function computeCounterfactualIntelligence(graph, paramOverrides = {}) {
  const resonance = computeConstraintResonance(graph, paramOverrides);
  const singleEvaluations = (graph.paths || [])
    .filter(p => !p.export)
    .map(p => evaluateInterventionCounterfactual(graph, p, paramOverrides));

  // Identify if any single intervention is dominated by another on the same node due to a 3rd-order bottleneck ceiling
  for (const ev of singleEvaluations) {
    const betterPeer = singleEvaluations.find(
      other =>
        other.id !== ev.id &&
        other.deltas?.[0]?.node === ev.deltas?.[0]?.node &&
        other.throughput_after >= ev.throughput_after &&
        other.throughput_gain > 0 &&
        other.net_daily_after_usd > ev.net_daily_after_usd
    );
    if (betterPeer) {
      ev.dominated_by = betterPeer.id;
      ev.dominated_reason = `Clamped at ${ev.throughput_after} ${resonance.unit} by 3rd-order constraint ${ev.bottleneck_after_label}; '${betterPeer.label}' achieves the same ${betterPeer.throughput_after} ${resonance.unit} output for $${betterPeer.net_daily_after_usd - ev.net_daily_after_usd}/day higher net profit.`;
    }
  }

  const synergisticCombos = discoverSynergisticCombos(graph, paramOverrides);
  const traps = singleEvaluations.filter(e => e.classification === 'COUNTERFACTUAL_TRAP');

  return {
    resonance,
    single_interventions: singleEvaluations,
    counterfactual_traps: traps,
    synergistic_combos: synergisticCombos,
    recommended_next: synergisticCombos[0]
      ? { kind: 'synergistic_combo', id: synergisticCombos[0].id, label: synergisticCombos[0].label, net_gain_usd: synergisticCombos[0].evaluation.net_daily_gain_usd }
      : singleEvaluations.filter(e => e.throughput_gain > 0 && !e.dominated_by).sort((a, b) => b.net_daily_gain_usd - a.net_daily_gain_usd)[0] || null
  };
}

// Dynamically generate 2-4 genuinely distinct, state-relevant next opportunities + Keep What I Have
export function generateDynamicOpportunities(session) {
  const g = session.graph;
  const overrides = session.simOverrides || {};
  const intel = computeCounterfactualIntelligence(g, overrides);
  const res = intel.resonance;

  const activeBranchIds = new Set(
    g.nodes.filter(n => n.id.startsWith('branch_') && n.state !== 'rejected').map(n => n.id.slice('branch_'.length))
  );
  const opportunities = [];

  // 1. Primary bottleneck direct unlock(s) not yet applied (prefer non-dominated first)
  const remainingSingles = (g.paths || []).filter(p => !p.export && !activeBranchIds.has(p.id));
  const evaluatedRemaining = remainingSingles.map(p => ({
    path: p,
    eval: intel.single_interventions.find(e => e.id === p.id) || evaluateInterventionCounterfactual(g, p, overrides)
  }));

  const directUnlocks = evaluatedRemaining
    .filter(x => x.eval.throughput_gain > 0 && !x.eval.dominated_by)
    .sort((a, b) => b.eval.net_daily_gain_usd - a.eval.net_daily_gain_usd);

  for (const item of directUnlocks.slice(0, 2)) {
    opportunities.push({
      id: item.path.id,
      kind: item.eval.classification,
      label: item.path.label,
      detail: item.path.detail,
      after: item.path.after,
      delta: item.path.delta,
      evaluation: item.eval
    });
  }

  // 2. Emergent Synergistic Combo (if available and not yet applied)
  if (intel.synergistic_combos.length > 0 && opportunities.length < 3) {
    const topCombo = intel.synergistic_combos[0];
    if (!activeBranchIds.has(topCombo.id)) {
      opportunities.push({
        id: topCombo.id,
        kind: 'SYNERGISTIC_COMBO',
        label: topCombo.label,
        detail: `${topCombo.evaluation.explanation} (CapEx $${topCombo.evaluation.capex_usd.toLocaleString()}, +$${topCombo.evaluation.fixed_cost_delta_usd}/day op cost).`,
        after: topCombo.after,
        deltas: topCombo.deltas,
        component_ids: topCombo.component_ids,
        evaluation: topCombo.evaluation
      });
    }
  }

  // 3. If space remains, surface either a dominated comparison option or a counterfactual trap option so the user can explore why it is clamped
  if (opportunities.length < 3) {
    const trapOrDominated = evaluatedRemaining.find(
      x => !opportunities.some(o => o.id === x.path.id) && (x.eval.dominated_by || x.eval.classification === 'COUNTERFACTUAL_TRAP')
    );
    if (trapOrDominated) {
      opportunities.push({
        id: trapOrDominated.path.id,
        kind: trapOrDominated.eval.dominated_by ? 'TERTIARY_CEILING_OPTION' : trapOrDominated.eval.classification,
        label: trapOrDominated.path.label,
        detail: trapOrDominated.eval.dominated_reason || trapOrDominated.eval.explanation || trapOrDominated.path.detail,
        after: trapOrDominated.path.after,
        delta: trapOrDominated.path.delta,
        evaluation: trapOrDominated.eval
      });
    }
  }

  // 4. Always include 'Keep What I Have' (preserves accepted baseline, clears unaccepted exploratory drafts or exports)
  const keepPath = (g.paths || []).find(p => p.export) || {
    id: 'portable',
    label: 'Keep what I have',
    detail: 'Preserve accepted project state and export standalone app + verified graph.',
    after: g.nodes[g.nodes.length - 1]?.id || 'wish',
    export: true
  };
  const hasUnacceptedExploration = g.nodes.some(n => n.id.startsWith('branch_') && n.state !== 'accepted' && n.state !== 'rejected') ||
    Object.values(overrides).some(v => Number(v) !== 0);

  opportunities.push({
    id: keepPath.id,
    kind: 'KEEP_WHAT_I_HAVE',
    label: hasUnacceptedExploration ? 'Keep what I have (Revert preview)' : 'Keep what I have / export',
    detail: hasUnacceptedExploration
      ? `Discard unaccepted exploratory changes and preserve accepted baseline (${res.baseline_throughput} ${res.unit}, $${res.baseline_net_daily_usd}/day).`
      : keepPath.detail,
    after: keepPath.after,
    export: true,
    revert_exploratory: hasUnacceptedExploration
  });

  return opportunities.slice(0, 4);
}

export function createGraph(kind = 'barber') {
  const d = DEMOS[kind];
  if (!d) throw Error('Unknown example');
  const g = {
    schema: SCHEMA,
    schema_v04: SCHEMA_V04,
    schema_v05: SCHEMA_V05,
    id: 'demo-' + kind,
    title: d.title,
    subtitle: d.subtitle,
    wish: d.wish,
    domain_unit: d.domain_unit || 'units/day',
    baseline_metrics: clone(d.baseline_metrics || {}),
    source: 'LOCAL_SIMULATION_NOT_MODEL_EXECUTION',
    nodes: clone(d.nodes),
    edges: clone(d.edges),
    paths: clone(d.paths)
  };
  validateGraph(g);
  g.constraint_resonance = computeConstraintResonance(g);
  g.counterfactual_intelligence = computeCounterfactualIntelligence(g);
  return g;
}

export function createSession(graph = createGraph()) {
  validateGraph(graph);
  const g = clone(graph);
  const isVerifiedSource = g.source === 'RECEIVER_VERIFIED_ENGINE_STATE' && Boolean(g._cryptographically_verified);
  if (!isVerifiedSource && g.source === 'RECEIVER_VERIFIED_ENGINE_STATE') {
    g.source = 'UNVERIFIED_CLAIM_DOWNGRADED';
  }
  g.constraint_resonance = computeConstraintResonance(g);
  g.counterfactual_intelligence = computeCounterfactualIntelligence(g);
  return {
    graph: g,
    events: [],
    sequence: 0,
    clock: 0,
    simOverrides: {},
    assemblyStage: 'assembled',
    liveServerConnected: false,
    receiverAttested: isVerifiedSource,
    verificationStatus: isVerifiedSource ? 'RECEIVER_VERIFIED' : 'SIMULATED_PREVIEW',
    verificationReason: isVerifiedSource ? 'verified' : 'local_simulation',
    verifiedReceipt: null,
    lastCounterfactual: null
  };
}

export function getNode(session, id) {
  return session.graph.nodes.find(n => n.id === id);
}

export function dependencies(session, id) {
  return session.graph.edges
    .filter(e => e.to === id && e.kind === 'depends_on')
    .map(e => getNode(session, e.from))
    .filter(Boolean);
}

export function dependents(session, id) {
  return session.graph.edges
    .filter(e => e.from === id && e.kind === 'depends_on')
    .map(e => getNode(session, e.to))
    .filter(Boolean);
}

const ALLOWED_TRANSITIONS = {
  planned: ['building', 'blocked', 'tentative', 'stopped'],
  building: ['ready', 'tentative', 'blocked', 'stopped'],
  ready: ['accepted', 'rejected', 'blocked', 'tentative', 'stopped', 'unknown_external_effect'],
  tentative: ['accepted', 'rejected', 'blocked', 'ready', 'stopped', 'unknown_external_effect'],
  accepted: ['reopened', 'stopped'],
  rejected: ['building', 'planned', 'reopened'],
  blocked: ['building', 'planned', 'reopened'],
  stopped: ['reopened', 'planned', 'building', 'ready'],
  unknown_external_effect: ['accepted', 'rejected', 'blocked', 'reopened'],
  reopened: ['building', 'ready', 'tentative', 'accepted', 'rejected']
};

export function sendEvent(session, actor, nodeId, to, reason, fromExpected, options = {}) {
  const n = getNode(session, nodeId);
  if (!n) throw Error('Node absent');
  const from = n.state;
  if (fromExpected && from !== fromExpected) throw Error('State mismatch');
  const allowed = ALLOWED_TRANSITIONS[from] || [];
  if (!allowed.includes(to)) throw Error('Illegal transition ' + from + ' -> ' + to);
  if (to === 'building' && dependencies(session, nodeId).some(d => !['ready', 'accepted', 'reopened'].includes(d.state))) {
    throw Error('Unmet dependency');
  }
  const validActors = new Set(['local-demo-worker', 'local-owner', 'genie-worker-a', 'genie-worker-b', 'receiver-guard']);
  if (!validActors.has(actor)) throw Error('Actor is not authorized in this local demonstration');
  if (['accepted', 'rejected', 'stopped', 'reopened'].includes(to) && !['local-owner', 'receiver-guard'].includes(actor)) {
    throw Error('Only local owner may accept/reject');
  }

  // Cryptographic verification gate for event-level RECEIVER_VERIFIED claims:
  // Either the session holds a verified bundle receipt for this graph, OR options provides a valid signed receipt + trustedReceiverKeys.
  let isCryptoVerified = false;
  let verifiedReceiptId = null;
  let verifiedStateSha = null;
  let verificationNote = null;

  if (session.receiverAttested && session.verifiedReceipt && session.verifiedReceipt.verified) {
    isCryptoVerified = true;
    verifiedReceiptId = session.verifiedReceipt.receipt_id;
    verifiedStateSha = session.verifiedReceipt.state_sha256;
  } else if (options.receipt && options.trustedReceiverKeys) {
    const rcptCheck = verifyReceiptEnvelope(options.receipt, options.trustedReceiverKeys);
    if (rcptCheck.verified && rcptCheck.payload.status === 'COMMITTED') {
      isCryptoVerified = true;
      verifiedReceiptId = rcptCheck.payload.receipt_id;
      verifiedStateSha = options.state_sha256 || rcptCheck.payload.payload_sha256;
    } else {
      verificationNote = rcptCheck.reason;
    }
  } else if (options.verified) {
    // Caller requested verified=true without cryptographic proof: fail closed to UNVERIFIED_EVENT
    verificationNote = 'unverified_claim_missing_cryptographic_receipt';
  }

  const preResonance = computeConstraintResonance(session.graph, session.simOverrides || {});
  n.state = to;
  if (to === 'accepted') n.standing = 'CURRENT';
  if (to === 'reopened') n.standing = 'QUESTIONED_BY_RECALL';
  session.sequence++;
  session.clock++;
  const postResonance = computeConstraintResonance(session.graph, session.simOverrides || {});
  session.graph.constraint_resonance = postResonance;
  session.graph.counterfactual_intelligence = computeCounterfactualIntelligence(session.graph, session.simOverrides || {});

  const isUnverifiedClaim = Boolean(options.unverifiedImport || verificationNote);
  const evLevel = isCryptoVerified
    ? 'RECEIVER_ED25519_ATTESTED'
    : isUnverifiedClaim
      ? 'UNVERIFIED_NOT_ATTESTED'
      : 'SIMULATED_NOT_ATTESTED';
  const evSource = isCryptoVerified
    ? 'RECEIVER_VERIFIED_EVENT'
    : isUnverifiedClaim
      ? 'UNVERIFIED_IMPORT_EVENT'
      : 'SIMULATED_PREVIEW_EVENT';

  const msg = {
    schema: EVENT_SCHEMA,
    schema_v04: EVENT_SCHEMA_V04,
    schema_v05: EVENT_SCHEMA_V05,
    graph_id: session.graph.id,
    seq: session.sequence,
    actor: {
      id: actor,
      mode: isCryptoVerified ? 'RECEIVER_ATTESTED' : isUnverifiedClaim ? 'UNVERIFIED_IMPORT' : 'SIMULATED_LOCAL'
    },
    kind: 'NODE_STATE_TRANSITION',
    subject: nodeId,
    pre_state: from,
    post_state: to,
    authorization: to === 'ready' ? 'tentative' : to,
    reason: String(reason || '').slice(0, 140),
    basis: dependencies(session, nodeId).map(x => ({ node: x.id, state: x.state })),
    constraint_delta: {
      pre_bottleneck: preResonance.bottleneck_id,
      post_bottleneck: postResonance.bottleneck_id,
      system_throughput: postResonance.system_throughput,
      unit: postResonance.unit
    },
    evidence: {
      level: evLevel,
      source: evSource,
      receipt_id: isCryptoVerified ? (options.receipt_id || verifiedReceiptId) : null,
      state_sha256: isCryptoVerified ? (options.state_sha256 || verifiedStateSha) : null,
      ...(verificationNote ? { verification_error: verificationNote } : {})
    },
    logical_time: session.clock
  };
  session.events.push(msg);
  return msg;
}

// Decision Recall: reopening an accepted node visibly questions and reopens downstream dependent nodes
export function propagateDecisionRecall(session, nodeId, reason = 'Owner reopened upstream assumption') {
  const target = getNode(session, nodeId);
  if (!target) throw Error('Node absent');
  const affected = [];
  if (target.state === 'accepted' || target.state === 'ready') {
    if (target.state === 'accepted') {
      sendEvent(session, 'local-owner', nodeId, 'reopened', reason);
    } else {
      target.standing = 'QUESTIONED_BY_RECALL';
    }
    affected.push(nodeId);
  }
  const queue = [nodeId];
  const visited = new Set([nodeId]);
  while (queue.length > 0) {
    const cur = queue.shift();
    for (const dep of dependents(session, cur)) {
      if (!visited.has(dep.id)) {
        visited.add(dep.id);
        dep.standing = 'QUESTIONED_BY_RECALL';
        if (dep.state === 'accepted') {
          sendEvent(session, 'receiver-guard', dep.id, 'reopened', `Decision Recall: upstream '${cur}' reopened`);
        }
        affected.push(dep.id);
        queue.push(dep.id);
      }
    }
  }
  return affected;
}

export function tick(session) {
  const building = session.graph.nodes.find(n => n.state === 'building');
  if (building) return sendEvent(session, 'local-demo-worker', building.id, 'ready', 'Simulated component ready');
  const candidate = session.graph.nodes.find(
    n => n.state === 'planned' && dependencies(session, n.id).every(d => ['ready', 'accepted', 'reopened'].includes(d.state))
  );
  if (candidate) return sendEvent(session, 'local-demo-worker', candidate.id, 'building', 'Simulated assembly step');
  return null;
}

export function resetExploration(session) {
  session.simOverrides = {};
  session.graph.nodes = session.graph.nodes.filter(n => !n.id.startsWith('branch_') || n.state === 'accepted');
  const validIds = new Set(session.graph.nodes.map(n => n.id));
  session.graph.edges = session.graph.edges.filter(e => validIds.has(e.from) && validIds.has(e.to));
  session.graph.constraint_resonance = computeConstraintResonance(session.graph, {});
  session.graph.counterfactual_intelligence = computeCounterfactualIntelligence(session.graph, {});
  session.lastCounterfactual = null;
  return session.graph.constraint_resonance;
}

export function addPath(session, pathId) {
  let path = (session.graph.paths || []).find(p => p.id === pathId);
  if (!path && String(pathId).startsWith('combo_')) {
    const combos = discoverSynergisticCombos(session.graph, session.simOverrides || {});
    path = combos.find(c => c.id === pathId);
  }
  if (!path) throw Error('Unknown path');
  if (path.export) return { export: true };

  const id = 'branch_' + path.id;
  const existing = getNode(session, id);
  if (existing) {
    session.graph.constraint_resonance = computeConstraintResonance(session.graph, session.simOverrides || {});
    session.graph.counterfactual_intelligence = computeCounterfactualIntelligence(session.graph, session.simOverrides || {});
    return { node: existing, already: true, resonance: session.graph.constraint_resonance, counterfactual: session.lastCounterfactual };
  }
  const ref = getNode(session, path.after);
  if (!ref) throw Error('Branch source missing');
  if (session.graph.nodes.length >= 64 || session.graph.edges.length >= 140) throw Error('Graph limit');

  const cfEval = evaluateInterventionCounterfactual(session.graph, path, session.simOverrides || {});
  const preResonance = computeConstraintResonance(session.graph, session.simOverrides || {});

  session.graph.nodes.push(
    node(id, path.label, 'artifact', path.detail, 'planned', {
      branch_of: path.after,
      delta: path.delta ? clone(path.delta) : null,
      deltas: path.deltas ? clone(path.deltas) : null,
      counterfactual: cfEval
    })
  );
  session.graph.edges.push(e(path.after, id));
  const postResonance = computeConstraintResonance(session.graph, session.simOverrides || {});
  session.graph.constraint_resonance = postResonance;
  session.graph.counterfactual_intelligence = computeCounterfactualIntelligence(session.graph, session.simOverrides || {});
  session.lastCounterfactual = cfEval;

  const isCryptoVerified = Boolean(session.receiverAttested && session.verifiedReceipt?.verified);
  session.events.push({
    schema: EVENT_SCHEMA,
    schema_v04: EVENT_SCHEMA_V04,
    schema_v05: EVENT_SCHEMA_V05,
    graph_id: session.graph.id,
    seq: ++session.sequence,
    actor: { id: 'local-owner', mode: isCryptoVerified ? 'RECEIVER_ATTESTED' : 'SIMULATED_LOCAL' },
    kind: 'EXPLORE_BRANCH',
    subject: id,
    pre_state: 'absent',
    post_state: 'planned',
    authorization: 'tentative',
    reason: path.detail,
    basis: [{ node: ref.id, state: ref.state }],
    constraint_delta: {
      pre_bottleneck: preResonance.bottleneck_id,
      post_bottleneck: postResonance.bottleneck_id,
      pre_throughput: preResonance.system_throughput,
      post_throughput: postResonance.system_throughput,
      bottleneck_shifted: postResonance.bottleneck_shifted,
      classification: cfEval.classification,
      net_daily_delta_usd: postResonance.net_daily_delta_usd,
      unit: postResonance.unit
    },
    evidence: {
      level: isCryptoVerified ? 'RECEIVER_ED25519_ATTESTED' : 'SIMULATED_NOT_ATTESTED',
      source: isCryptoVerified ? 'RECEIVER_VERIFIED_EVENT' : 'SIMULATED_PREVIEW_EVENT'
    },
    logical_time: ++session.clock
  });
  return { node: getNode(session, id), already: false, resonance: postResonance, counterfactual: cfEval };
}

export function replayEventTrace(initialGraph, events, options = {}) {
  const base = clone(initialGraph);
  base.nodes = base.nodes.filter(n => !n.id.startsWith('branch_')).map(n => ({
    ...n,
    state: n.category === 'intent' ? 'accepted' : 'planned'
  }));
  base.edges = base.edges.filter(x => !x.to.startsWith('branch_') && !x.from.startsWith('branch_'));
  const session = createSession(base);
  for (const ev of events) {
    if (!ev || ev.decorative_only) continue;
    if (!VALID_EVENT_SCHEMAS.has(ev.schema)) throw Error('Unsupported event schema in replay');
    if (ev.kind === 'EXPLORE_BRANCH') {
      const pathId = String(ev.subject || '').replace(/^branch_/, '');
      addPath(session, pathId);
    } else if (ev.kind === 'NODE_STATE_TRANSITION') {
      sendEvent(session, ev.actor?.id || 'local-demo-worker', ev.subject, ev.post_state, ev.reason, ev.pre_state, {
        receipt: ev.evidence?.receipt || options.receipt,
        trustedReceiverKeys: options.trustedReceiverKeys,
        receipt_id: ev.evidence?.receipt_id,
        state_sha256: ev.evidence?.state_sha256
      });
    }
  }
  return session;
}

export function projectGenieBundleToLivingGraph(bundle, options = {}) {
  if (!bundle || !bundle.accepted || !bundle.accepted.state) {
    throw Error('Invalid Genie project bundle');
  }
  const verification = verifyGenieBundleReceipt(bundle, options);
  const isVerified = verification.verified === true;

  const st = bundle.accepted.state;
  const family = String(bundle.project_family || st.project_family || 'custom');
  const baseKind = family.includes('bakery') || String(bundle.project_id).includes('bakery')
    ? 'bakery'
    : family.includes('microgrid') || String(bundle.project_id).includes('microgrid')
      ? (DEMOS.microgrid ? 'microgrid' : 'barber')
      : 'barber';
  const g = createGraph(baseKind);
  g.id = bundle.project_id;
  g.title = bundle.title || st.title || g.title;
  g.subtitle = isVerified
    ? `Receiver-verified project (v${verification.version} · ${verification.state_sha256.slice(0, 10)})`
    : `Unverified imported bundle (${verification.reason})`;
  g.source = isVerified ? 'RECEIVER_VERIFIED_ENGINE_STATE' : 'UNVERIFIED_EXTERNAL_BUNDLE';
  if (isVerified) g._cryptographically_verified = true;

  const sess = createSession(g);
  sess.receiverAttested = isVerified;
  sess.verificationStatus = verification.status;
  sess.verificationReason = verification.reason;
  sess.verifiedReceipt = isVerified ? verification : null;

  const receiptId = isVerified ? verification.receipt_id : null;
  const stateSha = isVerified ? verification.state_sha256 : null;

  for (const n of sess.graph.nodes) {
    if (n.category === 'intent') continue;
    sendEvent(sess, 'genie-worker-a', n.id, 'building', 'Genie autonomous worker build step', 'planned', {
      unverifiedImport: !isVerified, receipt_id: receiptId, state_sha256: stateSha
    });
    sendEvent(sess, 'genie-worker-a', n.id, 'ready', 'Verified by headless Playwright & artifact check', 'building', {
      unverifiedImport: !isVerified, receipt_id: receiptId, state_sha256: stateSha
    });
    sendEvent(sess, 'receiver-guard', n.id, 'accepted', isVerified ? `Committed v${verification.version} (${stateSha.slice(0, 8)})` : `Unverified bundle state (${verification.reason})`, 'ready', {
      unverifiedImport: !isVerified, receipt_id: receiptId, state_sha256: stateSha
    });
  }

  for (const exp of bundle.exploratory || []) {
    if (exp.status === 'EXPLORATORY_PENDING') {
      const nid = 'exp_' + String(exp.proposal_id).replace(/[^A-Za-z0-9_-]/g, '').slice(0, 24);
      sess.graph.nodes.push(node(nid, exp.summary.slice(0, 40), 'artifact', `Exploratory proposal (${exp.proposer_worker}): ${exp.summary}`, 'tentative'));
      const anchor = getNode(sess, 'bookings') || getNode(sess, 'schedule') || sess.graph.nodes[0];
      sess.graph.edges.push(e(anchor.id, nid));
    }
  }

  for (const rej of bundle.rejected || []) {
    const nid = 'rej_' + String(rej.rejection_id).replace(/[^A-Za-z0-9_-]/g, '').slice(0, 24);
    sess.graph.nodes.push(node(nid, 'Rejected change', 'other', `Rejected (${rej.reason}) — Accepted SHA preserved (${String(rej.preserved_accepted_sha256).slice(0, 8)})`, 'rejected'));
    const anchor = getNode(sess, 'conflicts') || getNode(sess, 'schedule') || sess.graph.nodes[0];
    sess.graph.edges.push(e(anchor.id, nid, 'conflicts_with'));
  }

  if (bundle.stopped) {
    const target = getNode(sess, 'exports') || sess.graph.nodes[sess.graph.nodes.length - 1];
    if (target && target.state === 'accepted') {
      sendEvent(sess, 'local-owner', target.id, 'stopped', 'Owner emergency STOP active', 'accepted', {
        unverifiedImport: !isVerified, receipt_id: receiptId, state_sha256: stateSha
      });
    }
  }
  sess.graph.constraint_resonance = computeConstraintResonance(sess.graph, sess.simOverrides);
  sess.graph.counterfactual_intelligence = computeCounterfactualIntelligence(sess.graph, sess.simOverrides);
  return sess;
}

export function generateStandaloneAppHtml(session) {
  const g = session.graph;
  const res = computeConstraintResonance(g, session.simOverrides || {});
  const isBakery = g.id.includes('bakery');
  const isMicrogrid = g.id.includes('microgrid');
  const isCidery = g.id.includes('cidery');
  const title = g.title || 'OpenLine Genie Application';
  const defaultRecords = isBakery
    ? [
        { name: 'Country Sourdough Batard (Batch #1)', qty: 24, rate: 8.5, status: 'Baked & Cooled' },
        { name: 'Seeded Rye Hearth Loaf (Batch #2)', qty: 24, rate: 9.0, status: 'In Steam Deck Oven' },
        { name: 'Morning Croissant & Brioche Tray', qty: 36, rate: 4.75, status: 'Proofing Rack' }
      ]
    : isMicrogrid
      ? [
          { name: 'Community Clinic Cold-Storage Feeder', qty: 48, rate: 0.22, status: 'Protected Critical Load' },
          { name: 'Rooftop Array Block A+B Dispatch', qty: 180, rate: 0.18, status: 'Grid-Forming Active' }
        ]
      : isCidery
        ? [
            { name: 'Honeycrisp Wild-Ferment Batch #14', qty: 80, rate: 6.5, status: 'Cold Filtration' },
            { name: 'Orchard Blend Sparkling Cans', qty: 80, rate: 7.0, status: 'Bright Tank Ready' }
          ]
        : [
            { name: 'Marcus Vance — Skin Fade + Beard Lineup', qty: 1, rate: 55, status: 'Confirmed 10:00 AM' },
            { name: 'Devon Brooks — Classic Taper & Hot Towel', qty: 1, rate: 45, status: 'Confirmed 11:15 AM' },
            { name: 'Elena Rostova — Kids Scissor Cut (Mobile Stop)', qty: 2, rate: 35, status: 'Reminder Queued' }
          ];

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${title} — Standalone Local-First App</title>
<style>
  *{box-sizing:border-box}
  body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;margin:0;padding:18px;background:#081120;color:#eef6ff}
  .wrap{max-width:880px;margin:0 auto;display:flex;flex-direction:column;gap:14px}
  .card{background:#101f38;border:1px solid #2d4a73;border-radius:14px;padding:16px}
  .badge{display:inline-block;padding:4px 9px;border-radius:999px;background:#134e4a;color:#6ef6e6;font-size:11px;font-weight:600}
  h1{margin:8px 0 4px;font-size:22px}
  p{margin:0;color:#a8c0dd;font-size:13px}
  .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin-top:12px}
  .kpi{background:#0b1629;border:1px solid #243b5e;border-radius:10px;padding:10px}
  .kpi strong{display:block;font-size:18px;color:#7af8de}
  .kpi span{font-size:11px;color:#93aecf}
  .form-row{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
  input,select{padding:9px 11px;border-radius:8px;border:1px solid #385883;background:#091324;color:#fff;font-size:13px;flex:1;min-width:120px}
  button{padding:9px 14px;border-radius:8px;border:1px solid #5eead4;background:#115e59;color:#fff;font-weight:600;cursor:pointer}
  table{width:100%;border-collapse:collapse;margin-top:10px;font-size:13px}
  th,td{text-align:left;padding:9px 8px;border-bottom:1px solid #1e3352}
  th{color:#9ab6d8;font-size:11px;text-transform:uppercase}
</style>
</head>
<body>
<div class="wrap">
  <div class="card">
    <span class="badge">STANDALONE ZERO-DEPENDENCY APPLICATION • LOCALSTORAGE PERSISTENCE • $0 LOCK-IN</span>
    <h1>${title}</h1>
    <p>${g.wish || g.subtitle} — Binding constraint: <strong>${res.bottleneck_label} (${res.system_throughput} ${res.unit})</strong></p>
    <div class="kpis">
      <div class="kpi"><strong id="kpi-cap">${res.system_throughput} ${res.unit}</strong><span>System Throughput</span></div>
      <div class="kpi"><strong id="kpi-bot">${res.bottleneck_label}</strong><span>Binding Bottleneck</span></div>
      <div class="kpi"><strong id="kpi-total">$0.00</strong><span>Active Record Value</span></div>
    </div>
  </div>
  <div class="card">
    <strong>Add Record / Schedule Item</strong>
    <div class="form-row">
      <input id="inp-name" type="text" placeholder="Client, batch, or load name">
      <input id="inp-qty" type="number" value="1" min="1">
      <input id="inp-rate" type="number" value="45" step="0.5">
      <select id="inp-status">
        <option value="Confirmed">Confirmed</option>
        <option value="In Progress">In Progress</option>
        <option value="Completed">Completed</option>
      </select>
      <button id="btn-add" type="button">Add Record</button>
    </div>
    <table>
      <thead><tr><th>Name</th><th>Qty</th><th>Rate</th><th>Subtotal</th><th>Status</th><th>Action</th></tr></thead>
      <tbody id="rows"></tbody>
    </table>
  </div>
</div>
<script>
(function(){
  var KEY = 'openline_genie_standalone_' + ${JSON.stringify(g.id)};
  var fallback = ${JSON.stringify(defaultRecords)};
  function load(){
    try {
      var raw = window.localStorage.getItem(KEY);
      if (raw) return JSON.parse(raw);
    } catch (_) {}
    return fallback.slice();
  }
  var records = load();
  function save(){
    try { window.localStorage.setItem(KEY, JSON.stringify(records)); } catch (_) {}
  }
  function render(){
    var tbody = document.getElementById('rows');
    tbody.innerHTML = '';
    var total = 0;
    records.forEach(function(r, idx){
      var sub = (Number(r.qty)||0) * (Number(r.rate)||0);
      total += sub;
      var tr = document.createElement('tr');
      tr.innerHTML = '<td></td><td></td><td></td><td></td><td></td><td><button type="button" data-del="'+idx+'">Remove</button></td>';
      tr.children[0].textContent = r.name;
      tr.children[1].textContent = String(r.qty);
      tr.children[2].textContent = '$' + Number(r.rate).toFixed(2);
      tr.children[3].textContent = '$' + sub.toFixed(2);
      tr.children[4].textContent = r.status;
      tbody.appendChild(tr);
    });
    document.getElementById('kpi-total').textContent = '$' + total.toFixed(2);
    Array.from(tbody.querySelectorAll('[data-del]')).forEach(function(b){
      b.addEventListener('click', function(){
        records.splice(Number(b.getAttribute('data-del')), 1);
        save(); render();
      });
    });
  }
  document.getElementById('btn-add').addEventListener('click', function(){
    var name = document.getElementById('inp-name').value.trim() || 'New Entry';
    var qty = Number(document.getElementById('inp-qty').value) || 1;
    var rate = Number(document.getElementById('inp-rate').value) || 0;
    var status = document.getElementById('inp-status').value || 'Confirmed';
    records.push({name: name, qty: qty, rate: rate, status: status});
    document.getElementById('inp-name').value = '';
    save(); render();
  });
  render();
})();
<\/script>
</body>
</html>`;
}

export function asExport(session) {
  validateGraph(session.graph);
  session.graph.constraint_resonance = computeConstraintResonance(session.graph, session.simOverrides || {});
  session.graph.counterfactual_intelligence = computeCounterfactualIntelligence(session.graph, session.simOverrides || {});
  const exportGraph = clone(session.graph);
  delete exportGraph._cryptographically_verified;
  return {
    protocol: 'openline.graph-communication-export.v0.5',
    compatible_protocol: 'openline.graph-communication-export.v0.4',
    legacy_protocol: 'openline.graph-communication-export.v0.1',
    verification_status: session.verificationStatus || (session.receiverAttested ? 'RECEIVER_VERIFIED' : 'SIMULATED_PREVIEW'),
    notice: session.receiverAttested
      ? 'RECEIVER-ATTESTED ENGINE PROJECTION. Signed Ed25519 receipts cryptographically verified against pinned ReceiverGuard keys.'
      : session.verificationStatus === 'UNVERIFIED_IMPORT'
        ? `UNVERIFIED IMPORT (${session.verificationReason || 'missing_receipt'}). Do not treat as receiver-attested.`
        : 'SIMULATED PREVIEW STATE. Local deterministic model; not cryptographically attested by ReceiverGuard.',
    graph: exportGraph,
    constraint_resonance: clone(session.graph.constraint_resonance),
    counterfactual_intelligence: clone(session.graph.counterfactual_intelligence),
    events: clone(session.events),
    standalone_app_html: generateStandaloneAppHtml(session)
  };
}

export function importGraphData(data, options = {}) {
  if (data && data.accepted && data.accepted.state && !data.graph) {
    return projectGenieBundleToLivingGraph(data, options);
  }
  const g = clone(data?.graph || data);
  delete g._cryptographically_verified;
  validateGraph(g);

  // Check if imported graph claims receiver verification without valid bundle receipt proof
  let isVerified = false;
  let verStatus = 'SIMULATED_PREVIEW';
  let verReason = 'local_simulation';
  if (data?.bundle && options?.trustedReceiverKeys) {
    const check = verifyGenieBundleReceipt(data.bundle, options);
    isVerified = check.verified;
    verStatus = check.status;
    verReason = check.reason;
  } else if (g.source === 'RECEIVER_VERIFIED_ENGINE_STATE' || data?.verification_status === 'RECEIVER_VERIFIED') {
    isVerified = false;
    verStatus = 'UNVERIFIED_IMPORT';
    verReason = 'imported_graph_missing_pinned_receipt_verification';
    g.source = 'UNVERIFIED_IMPORT';
  }

  if (isVerified) g._cryptographically_verified = true;
  const s = createSession(g);
  s.receiverAttested = isVerified;
  s.verificationStatus = verStatus;
  s.verificationReason = verReason;

  if (Array.isArray(data?.events)) {
    s.events = clone(data.events).map(ev => {
      if (!isVerified && (ev.evidence?.source === 'RECEIVER_VERIFIED_EVENT' || ev.evidence?.level === 'RECEIVER_ED25519_ATTESTED')) {
        return {
          ...ev,
          actor: { ...(ev.actor || {}), mode: 'UNVERIFIED_IMPORT' },
          evidence: {
            ...(ev.evidence || {}),
            level: 'UNVERIFIED_NOT_ATTESTED',
            source: 'UNVERIFIED_IMPORT_EVENT',
            verification_error: 'downgraded_unverified_import'
          }
        };
      }
      return ev;
    });
    s.sequence = s.events.length;
  }
  return s;
}

export function plainEventLines(session) {
  return session.events.map(e => JSON.stringify(e)).join('\n') + (session.events.length ? '\n' : '');
}
