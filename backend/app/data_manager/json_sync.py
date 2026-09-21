from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Dict, Iterable, List, Set

from app.config import DEFAULT_DATA_DIR, LEGACY_DATA_DIR, Settings


class JsonDataStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.data_dir = settings.data_dir

    @property
    def abbreviations_path(self) -> Path:
        return self.data_dir / "abbreviations" / "teencode.json"

    @property
    def legacy_abbreviations_path(self) -> Path:
        return LEGACY_DATA_DIR / "teencode.json"

    @property
    def abbreviations_override_path(self) -> Path:
        return self.data_dir / "abbreviations" / "bootstrap_overrides.json"

    @property
    def approved_abbreviations_export_path(self) -> Path:
        return self.data_dir / "abbreviations" / "approved_abbreviations.json"

    @property
    def phrase_overrides_path(self) -> Path:
        return self.data_dir / "abbreviations" / "phrase_overrides.json"

    @property
    def mined_phrases_path(self) -> Path:
        return self.data_dir / "phrases" / "mined_phrases.json"

    @property
    def dictionary_dir(self) -> Path:
        return self.data_dir / "dictionaries"

    @property
    def legacy_dictionary_dir(self) -> Path:
        return LEGACY_DATA_DIR

    def load_abbreviations(self) -> Dict[str, str]:
        return {
            abbr: record["expanded"]
            for abbr, record in self.load_abbreviation_details().items()
            if record.get("expanded")
        }

    def load_abbreviation_records(self) -> List[dict]:
        records_by_key: Dict[tuple[str, str], dict] = {}
        for candidate in self._seed_abbreviation_paths():
            if candidate.exists():
                with candidate.open("r", encoding="utf-8-sig") as handle:
                    payload = json.load(handle)
                records_by_key.update(
                    self._records_by_abbreviation_and_domain(
                        payload.get("abbreviations", [])
                    )
                )

        if self.abbreviations_override_path.exists():
            with self.abbreviations_override_path.open("r", encoding="utf-8-sig") as handle:
                payload = json.load(handle)
            records_by_key.update(
                self._records_by_abbreviation_and_domain(
                    payload.get("abbreviations", [])
                )
            )

        if self.approved_abbreviations_export_path.exists():
            with self.approved_abbreviations_export_path.open("r", encoding="utf-8-sig") as handle:
                payload = json.load(handle)
            records_by_key.update(
                self._records_by_abbreviation_and_domain(
                    payload.get("abbreviations", [])
                )
            )

        return sorted(
            records_by_key.values(),
            key=lambda record: (record["abbr"], record["domain"]),
        )

    def load_abbreviation_details(self) -> Dict[str, dict]:
        details: Dict[str, dict] = {}
        for candidate in self._seed_abbreviation_paths():
            if candidate.exists():
                with candidate.open("r", encoding="utf-8-sig") as handle:
                    payload = json.load(handle)
                details.update(self._records_by_abbreviation(payload.get("abbreviations", [])))

        if self.abbreviations_override_path.exists():
            with self.abbreviations_override_path.open("r", encoding="utf-8-sig") as handle:
                payload = json.load(handle)
            details.update(self._records_by_abbreviation(payload.get("abbreviations", [])))

        if self.approved_abbreviations_export_path.exists():
            with self.approved_abbreviations_export_path.open("r", encoding="utf-8-sig") as handle:
                payload = json.load(handle)
            details.update(self._records_by_abbreviation(payload.get("abbreviations", [])))

        return details

    def _seed_abbreviation_paths(self) -> tuple[Path, ...]:
        if self.data_dir.resolve() == DEFAULT_DATA_DIR.resolve():
            return (self.legacy_abbreviations_path, self.abbreviations_path)
        return (self.abbreviations_path,)

    def load_phrase_overrides(self) -> Dict[str, dict]:
        """Return ``{phrase: {expanded, source, confidence}}`` from the override file."""
        return self._load_phrase_records(self.phrase_overrides_path, default_source="override")

    def load_mined_phrases(self) -> Dict[str, dict]:
        """Return mined phrase records produced by ``scripts/mine_phrases.py``."""
        return self._load_phrase_records(self.mined_phrases_path, default_source="mined")

    def _load_phrase_records(self, path: Path, *, default_source: str) -> Dict[str, dict]:
        if not path.exists():
            return {}
        try:
            with path.open("r", encoding="utf-8-sig") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return {}

        records: Dict[str, dict] = {}
        for item in payload.get("phrases", []):
            phrase = str(item.get("phrase") or "").strip().lower()
            expanded = str(item.get("expanded") or "").strip()
            if not phrase or not expanded:
                continue
            try:
                confidence = float(item.get("confidence", 1.0) or 1.0)
            except (TypeError, ValueError):
                confidence = 1.0
            records[phrase] = {
                "expanded": expanded,
                "source": str(item.get("source") or default_source),
                "confidence": confidence,
            }
        return records

    def load_dictionary_words(self) -> Set[str]:
        words: Set[str] = set()
        paths = sorted(self.dictionary_dir.glob("*.json"))
        if not paths:
            paths = sorted(self.legacy_dictionary_dir.glob("Viet*.json"))

        for path in paths:
            with path.open("r", encoding="utf-8-sig") as handle:
                payload = json.load(handle)
            for item in payload.get("words", []):
                word = str(item.get("word", "")).strip().lower()
                if word:
                    words.add(word)
        return words

    @classmethod
    def _records_by_abbreviation(cls, items: Iterable[dict]) -> Dict[str, dict]:
        return {record["abbr"]: record for record in cls._abbreviation_records(items)}

    @classmethod
    def _records_by_abbreviation_and_domain(
        cls, items: Iterable[dict]
    ) -> Dict[tuple[str, str], dict]:
        return {
            (record["abbr"], record["domain"]): record
            for record in cls._abbreviation_records(items)
        }

    @classmethod
    def _abbreviation_records(cls, items: Iterable[dict]) -> List[dict]:
        result: List[dict] = []
        for item in items:
            if item.get("approved") is False:
                continue
            abbr = str(item.get("abbr") or "").strip().lower()
            expanded = str(item.get("expanded") or "").strip()
            if not abbr or not expanded:
                continue
            domain = str(item.get("domain") or "general")
            alternatives = [
                meaning
                for meaning in cls._normalize_meanings(item.get("alternative_expansions", []))
                if meaning != expanded
            ]
            result.append(
                {
                    "id": str(item.get("id") or f"json:{domain}:{abbr}"),
                    "abbr": abbr,
                    "expanded": expanded,
                    "alternative_expansions": alternatives,
                    "domain": domain,
                    "source": str(item.get("source") or "json_seed"),
                    "created_at": item.get("created_at"),
                    "approved_by": item.get("approved_by"),
                }
            )
        return result

    @staticmethod
    def _normalize_meanings(value: object) -> List[str]:
        if isinstance(value, str):
            raw_items: object = [value]
        else:
            raw_items = value
        if not isinstance(raw_items, list):
            raw_items = [raw_items]

        normalized: List[str] = []
        for item in raw_items:
            cleaned = str(item or "").strip()
            if cleaned and cleaned not in normalized:
                normalized.append(cleaned)
        return normalized

    def export_approved_abbreviations(self, abbreviations: Iterable[dict]) -> Path:
        payload = {
            "abbreviations": [
                {
                    "id": record.get("id"),
                    "abbr": record.get("abbr"),
                    "expanded": record.get("expanded"),
                    "alternative_expansions": record.get("alternative_expansions", []),
                    "domain": record.get("domain", "general"),
                    "source": record.get("source", "sql_server"),
                    "approved": True,
                    "created_at": record.get("created_at"),
                    "approved_by": record.get("approved_by"),
                }
                for record in abbreviations
            ]
        }

        target = self.approved_abbreviations_export_path
        target.parent.mkdir(parents=True, exist_ok=True)

        with NamedTemporaryFile(
            "w", encoding="utf-8", delete=False, dir=str(target.parent)
        ) as temp_file:
            json.dump(payload, temp_file, ensure_ascii=False, indent=2)
            temp_file.write("\n")
            temp_name = temp_file.name

        os.replace(temp_name, target)
        return target
