"""OpenLine Recall INV-001: receiver-owned *experimental* evidence-standing gate.

Not an authorization engine, remote effects protocol, or general provenance inference.
Only trusted, in-process receiver code can register dependencies and effects.
"""
from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass
from contextlib import contextmanager
from pathlib import Path
from typing import Callable

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def unb64(x: str) -> bytes:
    return base64.urlsafe_b64decode(x + "=" * (-len(x) % 4))


def public_hex(key: Ed25519PrivateKey) -> str:
    return key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()


def signed_event(key: Ed25519PrivateKey, *, source: str, revision: int,
                 digest: str, state: str = "VALID", expires_at: int | None = None) -> dict:
    data = dict(schema="openline.recall.source-event.v1", source=source, revision=revision,
                digest=digest, state=state, expires_at=expires_at)
    return {"statement": data, "signature": b64(key.sign(canonical(data)))}


class Rejected(Exception):
    """Fail-closed event, source, or recorded-work constraint."""


@dataclass(frozen=True)
class Standing:
    work_id: str
    status: str
    witness: tuple[str, ...]


class RecallLedger:
    """Local receiver-owned evidence ledger; untrusted workers cannot call this API.

    Caller controls pinned issuer keys and declares evidence dependency closure.
    BEGIN IMMEDIATE serializes evidence mutation against local effect entry.
    Does not protect external I/O or arbitrary same-process callbacks.
    """

    def __init__(self, database: str | Path, receiver_seed: bytes):
        if len(receiver_seed) != 32:
            raise ValueError("receiver seed must be exactly 32 bytes")
        self.db = str(database)
        self._signer = Ed25519PrivateKey.from_private_bytes(receiver_seed)
        self.receiver_public = public_hex(self._signer)
        with self._conn() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS issuers(
              source TEXT PRIMARY KEY, public_key TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sources(
              source TEXT PRIMARY KEY, revision INTEGER NOT NULL, digest TEXT NOT NULL,
              state TEXT NOT NULL, expires_at INTEGER, signed_event TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS work(
              work_id TEXT PRIMARY KEY, support_sets TEXT NOT NULL,
              advisory TEXT NOT NULL, complete INTEGER NOT NULL CHECK(complete IN (0,1)),
              signature TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS links(
              source TEXT NOT NULL, work_id TEXT NOT NULL,
              PRIMARY KEY(source,work_id));
            CREATE INDEX IF NOT EXISTS links_by_work ON links(work_id);
            CREATE TABLE IF NOT EXISTS effects(
              task_id TEXT PRIMARY KEY, work_id TEXT NOT NULL,
              receipt TEXT NOT NULL, signature TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS application_effects(
              task_id TEXT PRIMARY KEY, work_id TEXT NOT NULL, note TEXT NOT NULL);
            """)

    @contextmanager
    def _conn(self):
        c = sqlite3.connect(self.db, timeout=8, isolation_level=None)
        try:
            c.execute("PRAGMA busy_timeout=8000")
            with c:
                yield c
        finally:
            c.close()

    def pin_source(self, source: str, issuer_public: str):
        """Receiver-only trust configuration. Once pinned, replacement is refused."""
        if not source or not isinstance(source, str):
            raise Rejected("invalid_source")
        try:
            if len(bytes.fromhex(issuer_public)) != 32:
                raise ValueError("bad key length")
        except (ValueError, TypeError) as exc:
            raise Rejected("invalid_issuer_public_key") from exc
        with self._conn() as c:
            c.execute("BEGIN IMMEDIATE")
            old = c.execute("SELECT public_key FROM issuers WHERE source=?", (source,)).fetchone()
            if old and old[0] != issuer_public:
                raise Rejected("issuer_replacement_not_authorized")
            c.execute("INSERT OR IGNORE INTO issuers VALUES (?,?)", (source, issuer_public))
            c.commit()

    def apply_event(self, event: dict, *, now: int | None = None) -> list[Standing]:
        """Verify exact signed event and atomically advance source standing.

        Return impacted work only. A missing source or forged event fails closed.
        """
        try:
            statement, signature = event["statement"], unb64(event["signature"])
            source, revision = statement["source"], statement["revision"]
            if (statement["schema"] != "openline.recall.source-event.v1"
                or not isinstance(revision, int) or isinstance(revision, bool) or revision < 1
                or statement["state"] not in ("VALID", "REVOKED", "CORRECTED", "SUPERSEDED", "EXPIRED")
                or not isinstance(statement["digest"], str) or len(statement["digest"]) != 64
                or any(z not in "0123456789abcdef" for z in statement["digest"])
                or (statement["expires_at"] is not None and (type(statement["expires_at"]) is not int))):
                raise Rejected("invalid_source_statement")
        except (KeyError, TypeError, ValueError, UnicodeError) as exc:
            raise Rejected("invalid_signed_event") from exc
        with self._conn() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT public_key FROM issuers WHERE source=?", (source,)).fetchone()
            if not row:
                raise Rejected("untrusted_source")
            try:
                Ed25519PublicKey.from_public_bytes(bytes.fromhex(row[0])).verify(signature, canonical(statement))
            except Exception as exc:
                raise Rejected("invalid_event_signature") from exc
            prior = c.execute("SELECT revision FROM sources WHERE source=?", (source,)).fetchone()
            if prior and revision <= prior[0]:
                raise Rejected("stale_or_replayed_source_event")
            if not prior and revision != 1:
                raise Rejected("source_initial_revision_must_be_one")
            c.execute("INSERT INTO sources(source,revision,digest,state,expires_at,signed_event) "
                      "VALUES(?,?,?,?,?,?) ON CONFLICT(source) DO UPDATE SET "
                      "revision=excluded.revision,digest=excluded.digest,state=excluded.state,"
                      "expires_at=excluded.expires_at,signed_event=excluded.signed_event",
                      (source,revision,statement["digest"],statement["state"],
                       statement["expires_at"],canonical(event).decode()))
            touched = [r[0] for r in c.execute("SELECT work_id FROM links WHERE source=?", (source,))]
            result = [self._standing(c, work, now=now) for work in touched]
            c.commit()
            return result

    def register_work(self, work_id: str, *, support_sets: list[list[dict]],
                      advisory: list[str] | None = None, complete: bool = True) -> Standing:
        """Receiver declares disjunction of independent-support conjunctions.

        Incomplete/ambiguous dependency closure is never silently accepted.
        Every support tuple must bind the exact signed evidence digest/revision.
        """
        if not work_id or type(complete) is not bool or not support_sets:
            raise Rejected("invalid_dependency_declaration")
        if not all(isinstance(group, list) and group for group in support_sets):
            raise Rejected("empty_support_group")
        advisory = advisory or []
        with self._conn() as c:
            c.execute("BEGIN IMMEDIATE")
            if c.execute("SELECT 1 FROM work WHERE work_id=?", (work_id,)).fetchone():
                raise Rejected("work_id_already_registered")
            dependencies = set(advisory)
            advisory_bound = []
            for src in sorted(set(advisory)):
                row = c.execute("SELECT revision,digest FROM sources WHERE source=?", (src,)).fetchone()
                if row is None:
                    raise Rejected("advisory_source_not_verified")
                self._verify_stored_source(c,src)
                advisory_bound.append({"source":src,"revision":row[0],"digest":row[1]})
            for group in support_sets:
                for dep in group:
                    if not isinstance(dep, dict) or set(dep) != {"source", "revision", "digest"}:
                        raise Rejected("unverified_dependency_shape")
                    src, revision, digest = dep["source"], dep["revision"], dep["digest"]
                    if not isinstance(src, str) or type(revision) is not int or not isinstance(digest, str):
                        raise Rejected("invalid_dependency")
                    check = c.execute("SELECT revision,digest FROM sources WHERE source=?", (src,)).fetchone()
                    if check is None or check != (revision, digest):
                        raise Rejected("dependency_not_verified_at_registration")
                    dependencies.add(src)
            manifest = {"work_id": work_id, "support_sets": support_sets,
                        "advisory": advisory_bound, "complete": complete}
            signature = b64(self._signer.sign(canonical(manifest)))
            c.execute("INSERT INTO work VALUES(?,?,?,?,?)", (work_id,canonical(support_sets).decode(),
                      canonical(advisory_bound).decode(),int(complete),signature))
            c.executemany("INSERT INTO links VALUES(?,?)", [(src,work_id) for src in sorted(dependencies)])
            result = self._standing(c,work_id)
            c.commit()
            return result

    def _verify_stored_source(self, c: sqlite3.Connection, source: str) -> None:
        record=c.execute("SELECT revision,digest,state,expires_at,signed_event FROM sources WHERE source=?",(source,)).fetchone()
        pinned=c.execute("SELECT public_key FROM issuers WHERE source=?",(source,)).fetchone()
        if not record or not pinned:
            raise Rejected("missing_pinned_source")
        try:
            packet=json.loads(record[4]); statement=packet["statement"]
            expected={"schema":"openline.recall.source-event.v1","source":source,
                      "revision":record[0],"digest":record[1],"state":record[2],"expires_at":record[3]}
            if statement!=expected:raise ValueError("row claims differ from signed source")
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(pinned[0])).verify(
                unb64(packet["signature"]),canonical(statement))
        except Exception as exc:
            raise Rejected("stored_source_integrity_failure") from exc

    def _standing(self, c: sqlite3.Connection, work_id: str, *, now: int | None = None) -> Standing:
        row=c.execute("SELECT support_sets,advisory,complete,signature FROM work WHERE work_id=?",(work_id,)).fetchone()
        if not row:
            raise Rejected("unknown_work")
        now=int(time.time()) if now is None else now
        sets, advisory, complete=json.loads(row[0]),json.loads(row[1]),bool(row[2])
        manifest = {"work_id": work_id, "support_sets": sets,
                    "advisory": advisory, "complete": complete}
        try:
            self._signer.public_key().verify(unb64(row[3]), canonical(manifest))
        except Exception as exc:
            raise Rejected("receiver_work_manifest_tampered") from exc
        if not complete:
            return Standing(work_id,"UNRESOLVED",("dependency_closure_incomplete",))
        advisory_changed=[]
        for dep in advisory:
            rec=c.execute("SELECT revision,digest,state,expires_at FROM sources WHERE source=?",(dep["source"],)).fetchone()
            if rec is not None:
                self._verify_stored_source(c,dep["source"])
            if (rec is None or rec[0]!=dep["revision"] or rec[1]!=dep["digest"]
                or rec[2]!="VALID" or (rec[3] is not None and now>=rec[3])):
                advisory_changed.append(dep["source"])
        if advisory_changed:
            return Standing(work_id,"UNRESOLVED",tuple(sorted(advisory_changed)))
        broken=[]
        for group in sets:
            failures=[]
            for dep in group:
                rec=c.execute("SELECT revision,digest,state,expires_at FROM sources WHERE source=?",(dep["source"],)).fetchone()
                if rec is not None:
                    self._verify_stored_source(c, dep["source"])
                ok=(rec is not None and rec[0]==dep["revision"] and rec[1]==dep["digest"]
                    and rec[2]=="VALID" and (rec[3] is None or now < rec[3]))
                if not ok:
                    failures.append(dep["source"])
            if not failures:
                return Standing(work_id,"CURRENT",tuple(sorted(d["source"] for d in group)))
            broken.extend(failures)
        return Standing(work_id,"REOPEN",tuple(sorted(set(broken))))

    def standing(self, work_id: str, *, now: int | None = None) -> Standing:
        with self._conn() as c:
            c.execute("BEGIN IMMEDIATE")
            result=self._standing(c,work_id,now=now)
            c.commit()
            return result

    def effect(self, *, work_id: str, task_id: str, note: str, now: int | None = None,
               callback: Callable[[sqlite3.Connection],None] | None = None) -> dict:
        """Receiver-only single SQLite effect. Receipts prove commit, not outside world.

        Replays return original verified signed receipt without new writes.
        """
        if not task_id or not isinstance(task_id,str):
            raise Rejected("invalid_task_id")
        with self._conn() as c:
            c.execute("BEGIN IMMEDIATE")
            prev=c.execute("SELECT work_id,receipt,signature FROM effects WHERE task_id=?", (task_id,)).fetchone()
            if prev:
                if prev[0]!=work_id:
                    raise Rejected("task_collision")
                result={"receipt":json.loads(prev[1]),"signature":prev[2]}
                self.verify_receipt(result,self.receiver_public)
                c.commit()
                return result
            state=self._standing(c,work_id,now=now)
            if state.status!="CURRENT":
                raise Rejected("evidence_not_current:"+state.status)
            if callback is not None:
                callback(c)  # TRUSTED receiver-authored callback. No external effects guaranteed.
            c.execute("INSERT INTO application_effects VALUES(?,?,?)",(task_id,work_id,note))
            rec={"schema":"openline.recall.local-effect.v1","work_id":work_id,"task_id":task_id,
                 "decision":"COMMITTED", "evidence_witness":list(state.witness),
                 "scope":"receiver_local_sqlite_only"}
            signature=b64(self._signer.sign(canonical(rec)))
            c.execute("INSERT INTO effects VALUES(?,?,?,?)",(task_id,work_id,canonical(rec).decode(),signature))
            c.commit()
            return {"receipt":rec,"signature":signature}

    @staticmethod
    def verify_receipt(wrapped: dict, receiver_public: str) -> bool:
        try:
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(receiver_public)).verify(
                unb64(wrapped["signature"]),canonical(wrapped["receipt"]))
            if wrapped["receipt"]["schema"]!="openline.recall.local-effect.v1":
                raise Rejected("wrong_receipt_profile")
        except Exception as exc:
            raise Rejected("invalid_receiver_receipt") from exc
        return True

    def recorded_effects(self):
        with self._conn() as c:
            return c.execute("SELECT task_id,work_id,note FROM application_effects ORDER BY task_id").fetchall()
