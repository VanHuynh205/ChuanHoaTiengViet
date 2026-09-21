"""Request-local bridge between live inference and the governed evidence store."""

from __future__ import annotations
import logging
import re

from app.data_manager.ai_meaning_repo import canonical

logger = logging.getLogger(__name__)


class RequestMeanings:
    def __init__(self, repository, *, request_id, user_id, session_id, domain, retry=False):
        self.repository = repository
        self.request_id, self.user_id, self.session_id = request_id, user_id, session_id
        self.domain, self.retry = domain, retry
        self.revision = None
        self.used = []

    def current(self):
        try:
            return self.revision is not None and self.repository.revision() == self.revision
        except Exception:
            return False  # fail closed on revocation checks

    def reuse(self, original_text, result):
        try:
            self.revision = self.repository.revision()
            choices = []
            for ambiguity in result.ambiguities:
                row = self.repository.reusable(ambiguity.abbr, self.domain, original_text)
                if row:
                    choices.append((ambiguity, row))
            if not self.current():
                return
            for ambiguity, row in choices:
                pattern = rf"(?<!\w){re.escape(ambiguity.abbr)}(?!\w)"
                matches = list(re.finditer(pattern, result.primary_output, re.I))
                if len(matches) != 1:
                    continue  # do not override a dataset expansion
                match = matches[0]
                result.primary_output = (
                    result.primary_output[: match.start()]
                    + row["meaning"]
                    + result.primary_output[match.end() :]
                )
                delta = len(row["meaning"]) - (match.end() - match.start())
                for span in result.expanded_abbreviations:
                    if span["start"] >= match.end():
                        span["start"] += delta
                        span["end"] += delta
                result.expanded_abbreviations.append(
                    dict(
                        abbr=ambiguity.abbr,
                        expanded=row["meaning"],
                        start=match.start(),
                        end=match.start() + len(row["meaning"]),
                        source="ai_conditional",
                        candidateId=row["id"],
                        revision=row["revision"],
                        policyVersion=row["policy_version"],
                    )
                )
                result.ambiguities.remove(ambiguity)
                self.used.append(row)
            if self.used:
                result.semantic_status = "uncertain"
                result.semantic_status_reason = "conditional_shared_meaning"
                for variant in result.variants:
                    if variant.is_primary:
                        variant.output = result.primary_output
        except Exception:
            logger.warning("AI meaning reuse unavailable")
            result.warnings.append("ai_meaning_reuse_unavailable")

    def capture(self, original_text, options, verification, result):
        if verification.from_cache or self.retry or not verification.verified_chunks:
            return
        corrections = getattr(verification, "evidence_corrections", None)
        if corrections is None:
            corrections = verification.corrections
        settings = self.repository.settings
        for before, after in corrections:
            proposal = next((p for p in (getattr(verification, "evidence_proposals", None) or [])
                             if p.get("before") == before and p.get("after") == after), {})
            abbr = canonical(str(before))
            if abbr not in {canonical(key) for key in options} or any(
                r["abbr"] == abbr for r in self.used
            ):
                continue
            try:
                row = self.repository.record(
                    abbr=abbr,
                    meaning=str(after),
                    domain=self.domain,
                    context=original_text,
                    request_id=self.request_id,
                    user_id=self.user_id,
                    session_id=self.session_id,
                    confidence=proposal.get("confidence", verification.confidence),
                    provider=settings.ai_provider,
                    model=proposal.get("model") or settings.nvidia_model,
                )
                matches = list(
                    re.finditer(
                        rf"(?<!\w){re.escape(str(after))}(?!\w)", result.primary_output, re.I
                    )
                )
                if len(matches) == 1 and not any(
                    canonical(str(s["abbr"])) == abbr for s in result.expanded_abbreviations
                ):
                    match = matches[0]
                    result.expanded_abbreviations.append(
                        dict(
                            abbr=abbr,
                            expanded=match[0],
                            start=match.start(),
                            end=match.end(),
                            source="ai_inferred",
                            candidateId=row["id"] if row else None,
                            revision=row["revision"] if row else None,
                            policyVersion=row["policy_version"] if row else None,
                        )
                    )
            except Exception:
                logger.warning("AI meaning evidence write failed")
                if "ai_meaning_evidence_write_failed" not in result.warnings:
                    result.warnings.append("ai_meaning_evidence_write_failed")
        # Evidence writes can advance revision. Never refresh a snapshot that used
        # shared rows: a simultaneous revoke must still invalidate that response.
        if not self.used:
            try:
                self.revision = self.repository.revision()
            except Exception:
                self.revision = None
