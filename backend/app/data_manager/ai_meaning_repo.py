"""Transactional, context-scoped AI evidence. Never export these rows as dataset."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import hmac
import math
import re
import unicodedata
from uuid import uuid4

from sqlalchemy import (
    MetaData,
    Table,
    Column,
    Unicode,
    String,
    Integer,
    BigInteger,
    Float,
    Boolean,
    DateTime,
    Uuid,
    UniqueConstraint,
    select,
    insert,
    update,
    func,
    text,
)
from app.data_manager.db import get_session_factory
from app.utils.text_utils import protected_literal_spans

POLICY_VERSION = "context-v1-3requests-2users-3sessions"
STATES = {"candidate", "conditional_shared", "confirmed", "needs_review", "revoked"}
metadata = MetaData(schema="dbo")
candidates = Table(
    "ai_meaning_candidates",
    metadata,
    Column("id", Uuid(as_uuid=False), primary_key=True),
    Column("abbr", Unicode(100), nullable=False),
    Column("meaning", Unicode(500), nullable=False),
    Column("domain", Unicode(100), nullable=False),
    Column("status", Unicode(30), nullable=False),
    Column("scope_fingerprint", String(64), nullable=False),
    Column("provider", Unicode(100)),
    Column("model", Unicode(200)),
    Column("policy_version", Unicode(50), nullable=False),
    Column("confidence", Float, nullable=False),
    Column("evidence_count", Integer, nullable=False),
    Column("is_active", Boolean, nullable=False),
    Column("created_at", DateTime),
    Column("updated_at", DateTime),
    Column("revoked_at", DateTime),
    Column("revoked_by", Unicode(100)),
    Column("revision", BigInteger, nullable=False),
)
evidence = Table(
    "ai_meaning_evidence",
    metadata,
    Column("id", Uuid(as_uuid=False), primary_key=True),
    Column("candidate_id", Uuid(as_uuid=False)),
    Column("request_fingerprint", String(64), nullable=False),
    Column("actor_fingerprint", String(64), nullable=False),
    Column("user_fingerprint", String(64), nullable=False),
    Column("session_fingerprint", String(64), nullable=False),
    Column("context_fingerprint", String(64), nullable=False),
    Column("context_snippet", Unicode(500), nullable=False),
    Column("created_at", DateTime),
    UniqueConstraint("candidate_id", "request_fingerprint"),
    UniqueConstraint("candidate_id", "context_fingerprint"),
)
audit = Table(
    "ai_meaning_audit",
    metadata,
    Column("id", Uuid(as_uuid=False), primary_key=True),
    Column("candidate_id", Uuid(as_uuid=False)),
    Column("action", Unicode(30)),
    Column("actor", Unicode(100)),
    Column("reason", Unicode(500)),
    Column("revision", BigInteger),
    Column("created_at", DateTime),
)


def canonical(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


def context_scope(context: str, abbr: str) -> str | None:
    """Exact adjacent two-word anchor; no semantic similarity inferred from a hash."""
    words = list(re.finditer(r"[^\W\d_]+", context, re.UNICODE))
    positions = [i for i, word in enumerate(words) if canonical(word[0]) == canonical(abbr)]
    if len(positions) != 1:
        return None
    i = positions[0]
    adjacent = words[i + 1 : i + 3] if len(words[i + 1 : i + 3]) == 2 else words[max(0, i - 2) : i]
    if len(adjacent) != 2:
        return None
    protected = protected_literal_spans(context)
    if any(
        start < word.end() and end > word.start()
        for word in [words[i], *adjacent]
        for start, end in protected
    ):
        return None
    return canonical(" ".join(word[0] for word in adjacent))


def redact_context(context: str, abbr: str) -> str:
    """Persist only the abbreviation and two lower-case context words, never the sentence.

    Names, identifiers, numbers and literals are suppressed. The fingerprint is
    computed separately with HMAC; this excerpt cannot reconstruct the request.
    """
    scope = context_scope(context, abbr)
    if not scope:
        return "[redacted]"
    # Reject title-case anchors before case folding (names are not evidence text).
    safe = []
    for word in scope.split():
        occurrences = re.findall(rf"(?<!\w){re.escape(word)}(?!\w)", context, re.I)
        safe.append(word if occurrences and all(w.islower() for w in occurrences) else "[redacted]")
    return f"[redacted] {abbr} … {' '.join(safe)} [redacted]"[:500]


class AIMeaningRepository:
    def __init__(self, settings, session_factory=None):
        self.settings = settings
        self.factory = session_factory or get_session_factory(settings)

    def fingerprint(self, kind, value):
        return hmac.new(
            self.settings.auth_secret.encode(),
            f"ai-meaning:{kind}:{value}".encode(),
            hashlib.sha256,
        ).hexdigest()

    @contextmanager
    def transaction(self):
        if self.factory is None:
            raise RuntimeError("AI evidence storage unavailable")
        with self.factory() as session, session.begin():
            if session.bind.dialect.name == "mssql":
                # Serialize admission + transitions across workers, including empty ranges.
                session.execute(
                    text(
                        "DECLARE @r int; EXEC @r = sp_getapplock "
                        "@Resource='ai-meaning-policy-v1', @LockMode='Exclusive', "
                        "@LockOwner='Transaction', @LockTimeout=10000; "
                        "IF @r < 0 THROW 51000, 'AI meaning lock unavailable', 1;"
                    )
                )
            yield session

    def _audit(self, session, row, action, actor="policy", reason=""):
        session.execute(
            insert(audit).values(
                id=str(uuid4()),
                candidate_id=row["id"],
                action=action,
                actor=actor,
                reason=reason,
                revision=row["revision"],
                created_at=datetime.now(timezone.utc),
            )
        )

    def _transition(self, session, row, status, actor="policy", reason=""):
        row.update(
            status=status,
            revision=row["revision"] + 1,
            updated_at=datetime.now(timezone.utc),
            is_active=status != "revoked",
        )
        if status == "revoked":
            row.update(revoked_at=datetime.now(timezone.utc), revoked_by=actor)
        session.execute(update(candidates).where(candidates.c.id == row["id"]).values(**row))
        self._audit(session, row, status, actor, reason)

    def record(
        self,
        *,
        abbr,
        meaning,
        domain,
        context,
        request_id,
        user_id,
        session_id,
        confidence,
        provider,
        model,
        from_cache=False,
        retry=False,
        reused=False,
    ):
        if from_cache or retry or reused:
            return None
        abbr, meaning, domain = canonical(abbr), canonical(meaning), canonical(domain)
        scope = context_scope(context, abbr)
        protected = protected_literal_spans(context)
        occurrences = list(re.finditer(rf"(?<!\w){re.escape(abbr)}(?!\w)", context, re.I))
        has_source = any(
            not any(a < match.end() and b > match.start() for a, b in protected)
            for match in occurrences
        )
        if (
            not has_source
            or not request_id
            or not user_id
            or not session_id
            or not domain
            or not re.fullmatch(r"[^\W\d_]{1,20}", abbr)
            or abbr == meaning
            or not re.fullmatch(r"[^\W\d_]+(?: [^\W\d_]+){0,11}", meaning)
            or len(meaning) > 500
            or len(domain) > 100
            or not math.isfinite(confidence)
            or not 0 < confidence <= 1
        ):
            return None
        scope_hash = self.fingerprint("scope", scope or "unscoped")
        request_hash = self.fingerprint("request", request_id)
        # Copying/reformatting a sentence or changing identifiers cannot add evidence.
        masked = context
        for start, end in reversed(protected_literal_spans(context)):
            masked = masked[:start] + " literal " + masked[end:]
        context_hash = self.fingerprint(
            "context", " ".join(re.findall(r"[^\W\d_]+", canonical(masked)))
        )
        now = datetime.now(timezone.utc)
        with self.transaction() as session:
            peers = [
                dict(r)
                for r in session.execute(
                    select(candidates).where(
                        candidates.c.abbr == abbr,
                        candidates.c.domain == domain,
                        candidates.c.scope_fingerprint == scope_hash,
                    )
                ).mappings()
            ]
            row = next((r for r in peers if r["meaning"] == meaning), None)
            if row and row["status"] == "revoked":
                return row  # permanent tombstone; old evidence never resurrects it
            if row is None:
                row = dict(
                    id=str(uuid4()),
                    abbr=abbr,
                    meaning=meaning,
                    domain=domain,
                    scope_fingerprint=scope_hash,
                    status="candidate",
                    provider=provider[:100],
                    model=model[:200],
                    policy_version=POLICY_VERSION,
                    confidence=confidence,
                    evidence_count=0,
                    is_active=True,
                    revision=1,
                    created_at=now,
                    updated_at=now,
                )
                session.execute(insert(candidates).values(**row))
                self._audit(session, row, "created")
            duplicate = session.execute(
                select(evidence.c.id).where(
                    evidence.c.candidate_id == row["id"],
                    (evidence.c.request_fingerprint == request_hash)
                    | (evidence.c.context_fingerprint == context_hash),
                )
            ).first()
            if duplicate:
                return row
            user_hash = self.fingerprint("user", str(user_id))
            session_hash = self.fingerprint("session", str(session_id))
            session.execute(
                insert(evidence).values(
                    id=str(uuid4()),
                    candidate_id=row["id"],
                    request_fingerprint=request_hash,
                    actor_fingerprint=user_hash,
                    user_fingerprint=user_hash,
                    session_fingerprint=session_hash,
                    context_fingerprint=context_hash,
                    context_snippet=redact_context(context, abbr),
                    created_at=now,
                )
            )
            row.update(
                evidence_count=row["evidence_count"] + 1,
                revision=row["revision"] + 1,
                updated_at=now,
            )
            session.execute(update(candidates).where(candidates.c.id == row["id"]).values(**row))
            self._audit(session, row, "evidence_added")
            competing = [p for p in peers if p["meaning"] != meaning and p["status"] != "revoked"]
            if competing:
                for peer in [row, *competing]:
                    if peer["status"] != "needs_review":
                        self._transition(session, peer, "needs_review", reason="competing_meaning")
            elif scope and row["status"] == "candidate" and row["evidence_count"] >= 3:
                production = self.settings.app_env in {"production", "prod"}
                actor = (
                    evidence.c.user_fingerprint if production else evidence.c.session_fingerprint
                )
                actors = session.scalar(
                    select(func.count(func.distinct(actor))).where(
                        evidence.c.candidate_id == row["id"]
                    )
                )
                if actors >= (2 if production else 3):
                    self._transition(session, row, "conditional_shared", reason=POLICY_VERSION)
            return row

    def list(self, status=None, domain=None, abbr=None, offset=0, limit=50):
        query = select(candidates)
        for column, value in (
            (candidates.c.status, status),
            (candidates.c.domain, domain),
            (candidates.c.abbr, abbr),
        ):
            if value:
                query = query.where(column == canonical(value))
        with self.factory() as session:
            return [
                dict(row)
                for row in session.execute(
                    query.order_by(candidates.c.updated_at.desc(), candidates.c.id)
                    .offset(offset)
                    .limit(limit)
                ).mappings()
            ]

    def detail(self, candidate_id):
        with self.factory() as session:
            row = (
                session.execute(select(candidates).where(candidates.c.id == candidate_id))
                .mappings()
                .first()
            )
            if row is None:
                return None
            return dict(
                candidate=dict(row),
                evidence=[
                    dict(r)
                    for r in session.execute(
                        select(evidence.c.context_snippet, evidence.c.created_at)
                        .where(evidence.c.candidate_id == candidate_id)
                        .order_by(evidence.c.created_at.desc())
                        .limit(100)
                    ).mappings()
                ],
                audit=[
                    dict(r)
                    for r in session.execute(
                        select(audit)
                        .where(audit.c.candidate_id == candidate_id)
                        .order_by(audit.c.created_at.desc())
                        .limit(200)
                    ).mappings()
                ],
            )

    def moderate(self, ids, action, actor, reason):
        status = {"revoke": "revoked", "confirm": "confirmed"}[action]
        with self.transaction() as session:
            rows = [
                dict(r)
                for r in session.execute(
                    select(candidates).where(candidates.c.id.in_(ids))
                ).mappings()
            ]
            if len(rows) != len(set(ids)):
                raise ValueError("Candidate not found")
            for row in rows:
                if status == "confirmed":
                    if row["status"] == "revoked":
                        raise ValueError("Revoked candidates cannot be revived")
                    competing = session.execute(
                        select(candidates.c.id).where(
                            candidates.c.abbr == row["abbr"],
                            candidates.c.domain == row["domain"],
                            candidates.c.scope_fingerprint == row["scope_fingerprint"],
                            candidates.c.id != row["id"],
                            candidates.c.status != "revoked",
                        )
                    ).first()
                    if competing:
                        raise ValueError("Revoke competing meanings before confirming")
                self._transition(session, row, status, actor, reason)
        return rows

    def reusable(self, abbr, domain, context):
        scope = context_scope(context, abbr)
        if not scope:
            return None
        with self.factory() as session:
            rows = list(
                session.execute(
                    select(candidates).where(
                        candidates.c.abbr == canonical(abbr),
                        candidates.c.domain == canonical(domain),
                        candidates.c.scope_fingerprint == self.fingerprint("scope", scope),
                        candidates.c.policy_version == POLICY_VERSION,
                        candidates.c.status.in_(["conditional_shared", "confirmed"]),
                        candidates.c.is_active.is_(True),
                    )
                ).mappings()
            )
            return dict(rows[0]) if len(rows) == 1 else None

    def revision(self):
        with self.factory() as session:
            return int(session.scalar(select(func.coalesce(func.sum(candidates.c.revision), 0))))
