import tempfile
import unittest
from pathlib import Path

from app.config import Settings
from app.data_manager.pending_service import LiveNormalizationData, PendingAbbreviationService
from app.normalizer.diacritic_restorer import SyncDiacriticRestorer
from app.normalizer.live_normalizer import (
    LiveNormalizerService,
    _remap_expanded_abbreviation_spans,
)


class FakePendingService:
    def __init__(self):
        self.submissions = []

    def get_approved_abbreviations(self):
        return {
            "đk": "đăng ký",
            "pk": "phải không",
        }

    def get_dictionary_words(self):
        return {"hôm", "nay", "đi", "thẻ", "ngân", "hàng", "phải", "không", "mai", "gặp"}

    def list_approved_abbreviations(self, abbr=None, domain="general"):
        records = [
            {
                "id": "abbr-dk",
                "abbr": "đk",
                "expanded": "đăng ký",
                "alternative_expansions": ["đúng không"],
                "domain": domain,
                "source": "sql_server",
            },
            {
                "id": "abbr-pk",
                "abbr": "pk",
                "expanded": "phải không",
                "alternative_expansions": [],
                "domain": domain,
                "source": "sql_server",
            },
        ]
        if not abbr:
            return records
        return [record for record in records if record["abbr"] == abbr]

    def get_live_normalization_data(self, domain="general", user_id=None):
        records = self.list_approved_abbreviations(domain=domain)
        return LiveNormalizationData(
            abbreviations=self.get_approved_abbreviations(),
            dictionary_words=self.get_dictionary_words(),
            approved_details={record["abbr"].lower(): record for record in records},
        )

    def submit_pending_abbreviation(self, **kwargs):
        self.submissions.append(kwargs)
        return {
            "abbr": kwargs["abbr"],
            "status": "PENDING_CREATED",
            "pending_id": f"pending-{kwargs['abbr']}",
            "has_suggested": False,
        }


class BulkUsageStatsRepository:
    """Mirrors the real repository, which now exposes a bulk writer."""

    def __init__(self, ready=True):
        self.bulk_calls = []
        self._ready = ready

    def is_ready(self):
        return self._ready

    def record_usage_bulk(self, usages, source_kind="live", max_rows=200):
        rows = list(usages)
        self.bulk_calls.append({"usages": rows, "source_kind": source_kind})
        return len(rows)


class FakeUsageStatsRepository:
    def __init__(self):
        self.calls = []

    def record_usage(
        self,
        abbr,
        expanded_chosen,
        source_kind="live",
        abbreviation_id=None,
    ):
        self.calls.append(
            {
                "abbr": abbr,
                "expanded_chosen": expanded_chosen,
                "source_kind": source_kind,
                "abbreviation_id": abbreviation_id,
            }
        )
        return True


class ChatPendingService(FakePendingService):
    def get_approved_abbreviations(self):
        return {
            "t": "tao",
            "mn": "m\u1ecdi ng\u01b0\u1eddi",
        }

    def get_dictionary_words(self):
        return {"cho", "bi\u1ebft", "b\u00e0n", "t\u00e1n"}

    def list_approved_abbreviations(self, abbr=None, domain="general"):
        records = [
            {
                "id": "abbr-t",
                "abbr": "t",
                "expanded": "tao",
                "alternative_expansions": [],
                "domain": domain,
                "source": "test",
            },
            {
                "id": "abbr-mn",
                "abbr": "mn",
                "expanded": "m\u1ecdi ng\u01b0\u1eddi",
                "alternative_expansions": [],
                "domain": domain,
                "source": "test",
            },
        ]
        if not abbr:
            return records
        return [record for record in records if record["abbr"] == abbr]


class UserOverridePendingService(FakePendingService):
    def get_approved_abbreviations(self):
        return {
            "dk": "dang ky",
            "pk": "phai khong",
        }

    def get_dictionary_words(self):
        return {"hom", "nay", "phai", "khong"}

    def list_approved_abbreviations(self, abbr=None, domain="general"):
        records = [
            {
                "id": "abbr-dk",
                "abbr": "dk",
                "expanded": "dang ky",
                "alternative_expansions": ["dung khong"],
                "domain": domain,
                "source": "sql_server",
            },
            {
                "id": "abbr-pk",
                "abbr": "pk",
                "expanded": "phai khong",
                "alternative_expansions": [],
                "domain": domain,
                "source": "sql_server",
            },
        ]
        if not abbr:
            return records
        return [record for record in records if record["abbr"] == abbr]

    def get_live_normalization_data(self, domain="general", user_id=None):
        records = self.list_approved_abbreviations(domain=domain)
        abbreviations = self.get_approved_abbreviations()
        if user_id == "user-1":
            records = [
                {
                    "id": "override-dk",
                    "abbr": "dk",
                    "expanded": "dieu kien",
                    "alternative_expansions": ["dang ky", "dung khong"],
                    "domain": domain,
                    "source": "user_personal",
                },
                *[record for record in records if record["abbr"] != "dk"],
            ]
            abbreviations = {**abbreviations, "dk": "dieu kien"}

        return LiveNormalizationData(
            abbreviations=abbreviations,
            dictionary_words=self.get_dictionary_words(),
            approved_details={record["abbr"].lower(): record for record in records},
        )


class NaturalSpeechPendingService(FakePendingService):
    def get_approved_abbreviations(self):
        return {"m": "m\u00e0y"}

    def get_dictionary_words(self):
        return {
            "\u00e1n",
            "b\u00e0i",
            "c\u01a1",
            "\u0111\u1ea5y",
            "\u0111\u1ebfn",
            "\u0111\u1ed3",
            "\u0111\u1ec3",
            "gi\u1edd",
            "kh\u00f3",
            "khuya",
            "l\u00e0m",
            "m",
            "m\u00f4n",
            "n\u00e0y",
            "n\u1eefa",
            "ph\u1ea3i",
            "s\u1edf",
            "t\u1eadn",
            "th\u1eadt",
            "th\u1ee9c",
            "v\u1eabn",
            "ch\u01b0a",
            "xong",
        }

    def list_approved_abbreviations(self, abbr=None, domain="general"):
        records = [
            {
                "id": "abbr-m",
                "abbr": "m",
                "expanded": "m\u00e0y",
                "alternative_expansions": [],
                "domain": domain,
                "source": "test",
            }
        ]
        if not abbr:
            return records
        return [record for record in records if record["abbr"] == abbr]

    def get_live_normalization_data(self, domain="general", user_id=None):
        records = self.list_approved_abbreviations(domain=domain)
        return LiveNormalizationData(
            abbreviations=self.get_approved_abbreviations(),
            dictionary_words=self.get_dictionary_words(),
            approved_details={record["abbr"].lower(): record for record in records},
            phrase_overrides={
                "m \u00e0": {
                    "expanded": "m \u00e0",
                    "source": "override",
                    "confidence": 1.0,
                }
            },
        )


class FakeSemanticVerifier:
    def __init__(
        self,
        verified_text,
        corrections=None,
        confidence=0.92,
        verified_chunks=1,
        total_chunks=1,
        status="verified",
        reason=None,
    ):
        self.verified_text = verified_text
        self.corrections = corrections or []
        self.confidence = confidence
        # ``verified_chunks == 0`` means the provider was never actually called,
        # which the service must not treat as an AI verification.
        self.verified_chunks = verified_chunks
        self.total_chunks = total_chunks
        self.status = status
        self.reason = reason
        self.calls = []

    def is_available(self):
        return True

    async def verify(self, **kwargs):
        self.calls.append(kwargs)

        class Result:
            verified_text = self.verified_text
            corrections = self.corrections
            confidence = self.confidence
            verified_chunks = self.verified_chunks
            total_chunks = self.total_chunks
            status = self.status
            reason = self.reason
            validated_output = True
            from_cache = False
            latency_ms = 0

        return Result()


class CountingPendingService(FakePendingService):
    def __init__(self):
        super().__init__()
        self.live_data_calls = 0

    def get_approved_abbreviations(self):
        return {
            "dk": "dang ky",
            "pk": "phai khong",
        }

    def get_dictionary_words(self):
        return {"hom", "nay", "mai", "gap", "doan", "cuoi", "giu", "nguyen"}

    def list_approved_abbreviations(self, abbr=None, domain="general"):
        records = [
            {
                "id": "abbr-dk",
                "abbr": "dk",
                "expanded": "dang ky",
                "alternative_expansions": [],
                "domain": domain,
                "source": "test",
            },
            {
                "id": "abbr-pk",
                "abbr": "pk",
                "expanded": "phai khong",
                "alternative_expansions": [],
                "domain": domain,
                "source": "test",
            },
        ]
        if not abbr:
            return records
        return [record for record in records if record["abbr"] == abbr]

    def get_live_normalization_data(self, domain="general", user_id=None):
        self.live_data_calls += 1
        return super().get_live_normalization_data(domain=domain, user_id=user_id)


class MutablePendingService(FakePendingService):
    def __init__(self):
        super().__init__()
        self._approved = {}

    def get_approved_abbreviations(self):
        return dict(self._approved)

    def get_dictionary_words(self):
        return {"mai", "gap", "doan", "cuoi"}

    def list_approved_abbreviations(self, abbr=None, domain="general"):
        records = [
            {
                "id": f"abbr-{key}",
                "abbr": key,
                "expanded": value,
                "alternative_expansions": [],
                "domain": domain,
                "source": "test",
            }
            for key, value in self._approved.items()
        ]
        if not abbr:
            return records
        return [record for record in records if record["abbr"] == abbr]


class LiveNormalizerTests(unittest.TestCase):
    def test_live_normalizer_keeps_natural_student_chat_context(self):
        word_map = {
            "bai": ["b\u00e0i"],
            "chua": ["ch\u01b0a"],
            "den": ["\u0111\u1ebfn"],
            "de": ["\u0111\u1ec3"],
            "gio": ["gi\u1edd"],
            "lam": ["l\u00e0m"],
            "nay": ["n\u00e0y"],
            "van": ["v\u1eabn"],
        }
        restorer = SyncDiacriticRestorer(word_map=word_map)
        service = LiveNormalizerService(
            Settings(data_dir=Path(tempfile.mkdtemp())),
            NaturalSpeechPendingService(),
            diacritic_restorer=restorer,
        )

        result = service.normalize_live(
            "mon do an co so nay kho that day m a, "
            "phai thuc den tan khuya de lam bai. Den gio van chua lam xong n\u1eefa",
            submitted_by="demo",
        )

        self.assertEqual(
            result.primary_output,
            "M\u00f4n \u0111\u1ed3 \u00e1n c\u01a1 s\u1edf n\u00e0y kh\u00f3 th\u1eadt \u0111\u1ea5y m \u00e0, "
            "ph\u1ea3i th\u1ee9c \u0111\u1ebfn t\u1eadn khuya \u0111\u1ec3 l\u00e0m b\u00e0i. "
            "\u0110\u1ebfn gi\u1edd v\u1eabn ch\u01b0a l\u00e0m xong n\u1eefa",
        )
        self.assertEqual(result.pending_submissions, [])

    def test_live_normalizer_returns_variants_for_alternative_meanings(self):
        settings = Settings(data_dir=Path(tempfile.mkdtemp()))
        service = LiveNormalizerService(settings, FakePendingService())

        result = service.normalize_live("hôm nay đi đk thẻ ngân hàng pk", submitted_by="demo")

        self.assertEqual(
            [variant.output for variant in result.variants],
            [
                "Hôm nay đi đk thẻ ngân hàng phải không",
                "Hôm nay đi đăng ký thẻ ngân hàng phải không",
                "Hôm nay đi đúng không thẻ ngân hàng phải không",
            ],
        )
        self.assertEqual(result.primary_output, "Hôm nay đi đk thẻ ngân hàng phải không")
        self.assertEqual(result.ambiguities[0].id, "đk:0")
        spans = result.to_payload()["expandedAbbreviations"]
        self.assertEqual(
            [
                {
                    "abbr": span["abbr"],
                    "expanded": result.primary_output[span["start"] : span["end"]],
                }
                for span in spans
            ],
            [{"abbr": "pk", "expanded": "phải không"}],
        )

    def test_live_change_metadata_maps_repeated_teencode_to_source_and_output(self):
        settings = Settings(data_dir=Path(tempfile.mkdtemp()))
        service = LiveNormalizerService(settings, FakePendingService())

        result = service.normalize_live("hôm nay pk pk", submitted_by="demo")

        teencode = [change for change in result.changes if "teencode" in change["kinds"]]
        self.assertEqual(
            [(change["originalText"], change["outputText"]) for change in teencode],
            [("pk", "phải không"), ("pk", "phải không")],
        )
        for change in teencode:
            self.assertEqual(
                result.primary_output[change["outputStart"] : change["outputEnd"]],
                change["outputText"],
            )

    def test_live_change_metadata_labels_diacritic_and_case_changes(self):
        settings = Settings(data_dir=Path(tempfile.mkdtemp()))
        restorer = SyncDiacriticRestorer({"toi": ["tôi"], "hoc": ["học"]})
        service = LiveNormalizerService(settings, FakePendingService(), restorer)

        result = service.normalize_live("toi di hoc", submitted_by="demo")

        self.assertEqual(
            [(change["originalText"], change["outputText"], change["kinds"]) for change in result.changes],
            [("toi", "Tôi", ["diacritic", "case"]), ("hoc", "học", ["diacritic", "case"])],
        )

    def test_live_change_metadata_labels_emoji_deletion_without_losing_following_offsets(self):
        settings = Settings(data_dir=Path(tempfile.mkdtemp()))
        service = LiveNormalizerService(settings, FakePendingService())

        result = service.normalize_live("mai :) gap", submitted_by="demo")

        deletion = next(change for change in result.changes if "deletion" in change["kinds"])
        self.assertEqual(deletion["originalText"], "mai :)")
        self.assertEqual(deletion["outputText"], "Mai")
        self.assertIn("case", deletion["kinds"])

    def test_usage_stats_are_written_once_per_request_not_once_per_span(self):
        settings = Settings(data_dir=Path(tempfile.mkdtemp()))
        usage_stats = BulkUsageStatsRepository()
        service = LiveNormalizerService(
            settings,
            FakePendingService(),
            usage_stats_repository=usage_stats,
        )

        service.normalize_live("hôm nay đi đk thẻ ngân hàng pk", submitted_by="demo")

        self.assertEqual(len(usage_stats.bulk_calls), 1)
        self.assertEqual(
            usage_stats.bulk_calls[0]["usages"],
            [("pk", "phải không")],
        )

    def test_usage_stats_are_skipped_entirely_when_the_table_is_not_deployed(self):
        settings = Settings(data_dir=Path(tempfile.mkdtemp()))
        usage_stats = BulkUsageStatsRepository(ready=False)
        service = LiveNormalizerService(
            settings,
            FakePendingService(),
            usage_stats_repository=usage_stats,
        )

        service.normalize_live("hôm nay đi đk thẻ ngân hàng pk", submitted_by="demo")

        self.assertEqual(usage_stats.bulk_calls, [])

    def test_live_normalizer_records_usage_stats_for_expanded_abbreviations(self):
        settings = Settings(data_dir=Path(tempfile.mkdtemp()))
        usage_stats = FakeUsageStatsRepository()
        service = LiveNormalizerService(
            settings,
            FakePendingService(),
            usage_stats_repository=usage_stats,
        )

        service.normalize_live("hôm nay đi đk thẻ ngân hàng pk", submitted_by="demo")

        self.assertEqual(
            usage_stats.calls,
            [
                {
                    "abbr": "pk",
                    "expanded_chosen": "phải không",
                    "source_kind": "live",
                    "abbreviation_id": None,
                },
            ],
        )

    def test_live_normalizer_respects_resolution_overrides(self):
        settings = Settings(data_dir=Path(tempfile.mkdtemp()))
        service = LiveNormalizerService(settings, FakePendingService())

        result = service.normalize_live(
            "hôm nay đi đk thẻ ngân hàng pk",
            submitted_by="demo",
            resolution_overrides={"đk:0": "đúng không"},
        )

        self.assertEqual(result.primary_output, "Hôm nay đi đúng không thẻ ngân hàng phải không")
        self.assertTrue(result.variants[0].is_primary)
        self.assertEqual(result.variants[0].resolutions[0].meaning, "đúng không")

    def test_live_normalizer_does_not_apply_user_override_as_primary_meaning(self):
        settings = Settings(data_dir=Path(tempfile.mkdtemp()))
        service = LiveNormalizerService(settings, UserOverridePendingService())

        result = service.normalize_live(
            "hom nay dk pk",
            submitted_by="demo",
            user_id="user-1",
        )

        self.assertEqual(result.primary_output, "Hom nay dk phai khong")
        self.assertEqual(result.ambiguities[0].selected, "dk")
        return

        result = service.normalize_live(
            "hﾃｴm nay ﾄ訴 ﾄ遡 th蘯ｻ ngﾃ｢n hﾃng pk",
            submitted_by="demo",
            user_id="user-1",
        )

        self.assertEqual(
            result.primary_output,
            "Hﾃｴm nay ﾄ訴 dieu kien th蘯ｻ ngﾃ｢n hﾃng ph蘯｣i khﾃｴng",
        )
        self.assertEqual(result.ambiguities[0].options[0], "dieu kien")

    def test_live_normalizer_keeps_unknown_abbreviation_pending_first(self):
        settings = Settings(data_dir=Path(tempfile.mkdtemp()))
        pending_service = FakePendingService()
        service = LiveNormalizerService(settings, pending_service)

        result = service.normalize_live("mai gặp abc", submitted_by="demo")

        self.assertEqual(pending_service.submissions[0]["abbr"], "abc")
        self.assertEqual(result.pending_submissions[0]["status"], "PENDING_CREATED")
        self.assertEqual(result.primary_output, "Mai gặp abc")

    def test_live_normalizer_defers_pending_for_open_typing_token(self):
        settings = Settings(data_dir=Path(tempfile.mkdtemp()))
        pending_service = FakePendingService()
        service = LiveNormalizerService(settings, pending_service)

        result = service.normalize_live("mai gặp abc", submitted_by="demo", input_method="typing")

        self.assertEqual(pending_service.submissions, [])
        self.assertEqual(result.pending_submissions, [])
        self.assertEqual(result.primary_output, "Mai gặp abc")

    def test_live_normalizer_submits_typing_pending_after_word_boundary(self):
        settings = Settings(data_dir=Path(tempfile.mkdtemp()))
        pending_service = FakePendingService()
        service = LiveNormalizerService(settings, pending_service)

        result = service.normalize_live("mai gặp abc ", submitted_by="demo", input_method="typing")

        self.assertEqual(pending_service.submissions[0]["abbr"], "abc")
        self.assertEqual(result.pending_submissions[0]["status"], "PENDING_CREATED")

    def test_live_normalizer_submits_repeated_unknown_once_per_request(self):
        settings = Settings(data_dir=Path(tempfile.mkdtemp()))
        pending_service = FakePendingService()
        service = LiveNormalizerService(settings, pending_service)

        result = service.normalize_live(
            "mai gặp abc abc ", submitted_by="demo", input_method="typing"
        )

        self.assertEqual(
            [submission["abbr"] for submission in pending_service.submissions], ["abc"]
        )
        self.assertEqual(len(result.pending_submissions), 1)

    def test_live_normalizer_preserves_emoji_and_blank_lines(self):
        settings = Settings(data_dir=Path(tempfile.mkdtemp()))
        service = LiveNormalizerService(settings, FakePendingService())

        result = service.normalize_live(
            "mai :)\n\n\ngap  abc",
            submitted_by="demo",
            input_method="paste",
        )

        self.assertEqual(result.primary_output, "Mai\n\n\ngap  abc")

    def test_live_normalizer_preserves_parenthesis_spacing(self):
        settings = Settings(data_dir=Path(tempfile.mkdtemp()))
        service = LiveNormalizerService(settings, FakePendingService())

        result = service.normalize_live("chao (ban)", submitted_by="demo")

        self.assertEqual(result.primary_output, "Chao (ban)")

    def test_live_normalizer_preserves_protected_literals(self):
        settings = Settings(data_dir=Path(tempfile.mkdtemp()))
        restorer = SyncDiacriticRestorer(
            {
                "nvidia": ["nìvidia"],
                "openai": ["ópenai"],
                "toi": ["tôi"],
            }
        )
        service = LiveNormalizerService(settings, FakePendingService(), restorer)

        result = service.normalize_live(
            "https://example.com/path?x=1 C++ C# 9/10 50% NVIDIA OpenAI. toi",
            submitted_by="demo",
        )

        self.assertEqual(
            result.primary_output,
            "https://example.com/path?x=1 C++ C# 9/10 50% NVIDIA OpenAI. Tôi",
        )

    def test_segmented_live_normalizer_preserves_original_separators(self):
        settings = Settings(
            data_dir=Path(tempfile.mkdtemp()),
            live_incremental_min_chars=10,
            live_incremental_chunk_words=3,
        )
        service = LiveNormalizerService(settings, MutablePendingService())

        result = service.normalize_live(
            "mai  gap abc.\n\n\ndoan cuoi abc.",
            submitted_by="demo",
            input_method="paste",
        )

        self.assertEqual(result.primary_output, "Mai  gap abc.\n\n\nDoan cuoi abc.")

    def test_live_normalizer_deduplicates_pending_across_long_text_segments(self):
        settings = Settings(
            data_dir=Path(tempfile.mkdtemp()),
            live_incremental_min_chars=10,
            live_incremental_chunk_words=3,
        )
        pending_service = MutablePendingService()
        service = LiveNormalizerService(settings, pending_service)

        result = service.normalize_live(
            "mai gap abc. doan cuoi abc.",
            submitted_by="demo",
            input_method="paste",
        )

        self.assertEqual(
            [submission["abbr"] for submission in result.pending_submissions], ["abc"]
        )

    def test_live_normalizer_segment_cache_expires_after_dictionary_invalidation(self):
        settings = Settings(
            data_dir=Path(tempfile.mkdtemp()),
            live_incremental_min_chars=10,
            live_incremental_chunk_words=3,
        )
        pending_service = MutablePendingService()
        service = LiveNormalizerService(settings, pending_service)
        text = "mai gap abc. doan cuoi giu nguyen."

        first = service.normalize_live(text, submitted_by="demo", input_method="paste")
        pending_service._approved["abc"] = "anh ban cu"
        PendingAbbreviationService.invalidate_live_normalization_cache()
        second = service.normalize_live(text, submitted_by="demo", input_method="paste")

        # "nguyen" stays lowercase: capitalisation is now applied once to the
        # joined text, so a segment boundary no longer invents a capital letter
        # in the middle of a sentence.
        self.assertEqual(first.primary_output, "Mai gap abc. Doan cuoi giu nguyen.")
        self.assertEqual(second.primary_output, "Mai gap anh ban cu. Doan cuoi giu nguyen.")

    def test_segmented_long_text_does_not_capitalise_mid_sentence(self):
        settings = Settings(
            data_dir=Path(tempfile.mkdtemp()),
            live_incremental_min_chars=10,
            live_incremental_chunk_words=3,
        )
        service = LiveNormalizerService(settings, FakePendingService())

        result = service.normalize_live(
            "hom nay toi di hoc va gap ban cu roi cung nhau an trua that vui",
            submitted_by="demo",
            input_method="paste",
        )

        words = result.primary_output.split()
        # Only the very first word may be capitalised — there is no punctuation
        # anywhere in the input.
        self.assertTrue(words[0][0].isupper())
        self.assertTrue(all(word[0].islower() for word in words[1:]), result.primary_output)

    def test_segmented_pending_budget_is_shared_across_segments(self):
        settings = Settings(
            data_dir=Path(tempfile.mkdtemp()),
            live_incremental_min_chars=10,
            live_incremental_chunk_words=2,
            live_max_pending_submissions=3,
        )
        pending_service = FakePendingService()
        service = LiveNormalizerService(settings, pending_service)

        result = service.normalize_live(
            "zza zzb zzc zzd zze zzf zzg zzh zzi zzj zzk zzl",
            submitted_by="demo",
            input_method="paste",
        )

        # The cap is per REQUEST, not per segment: applying it per segment let a
        # long paste multiply the moderation writes by the segment count.
        self.assertLessEqual(len(result.pending_submissions), 3)

    def test_live_normalizer_limits_pending_submissions_without_changing_output(self):
        settings = Settings(
            data_dir=Path(tempfile.mkdtemp()),
            live_max_pending_submissions=2,
        )
        pending_service = FakePendingService()
        service = LiveNormalizerService(settings, pending_service)

        result = service.normalize_live(
            "abc, bcd, cdf, dfg, fgh", submitted_by="demo", input_method="paste"
        )

        self.assertEqual(
            result.primary_output,
            "Abc, bcd, cdf, dfg, fgh",
        )
        self.assertEqual(
            [submission["abbr"] for submission in pending_service.submissions],
            ["abc", "bcd"],
        )
        self.assertEqual(len(result.pending_submissions), 2)
        self.assertIn("PENDING_LIMIT", result.error_types)

    def test_live_normalizer_does_not_request_meaning_for_regular_short_words(self):
        settings = Settings(
            data_dir=Path(tempfile.mkdtemp()),
            live_max_pending_submissions=12,
        )
        pending_service = FakePendingService()
        service = LiveNormalizerService(settings, pending_service)

        result = service.normalize_live(
            "form size dep emoji on g\u1eedi x\u00f3a",
            submitted_by="demo",
            input_method="paste",
        )

        actionable = [
            submission["abbr"]
            for submission in result.pending_submissions
            if submission.get("needs_user_meaning")
        ]
        self.assertEqual(actionable, [])

    def test_live_normalizer_reuses_unchanged_long_text_segments(self):
        settings = Settings(
            data_dir=Path(tempfile.mkdtemp()),
            live_incremental_min_chars=20,
            live_incremental_chunk_words=4,
        )
        pending_service = CountingPendingService()
        service = LiveNormalizerService(settings, pending_service)
        first_text = "hom nay dk. mai gap pk. doan cuoi giu nguyen."

        first = service.normalize_live(first_text, submitted_by="demo", input_method="paste")
        pending_service.live_data_calls = 0
        edited = service.normalize_live(
            "hom nay dk. mai gap dk. doan cuoi giu nguyen.",
            submitted_by="demo",
            input_method="typing",
        )

        self.assertEqual(
            first.primary_output,
            "Hom nay dang ky. Mai gap phai khong. Doan cuoi giu nguyen.",
        )
        self.assertEqual(
            edited.primary_output,
            "Hom nay dang ky. Mai gap dang ky. Doan cuoi giu nguyen.",
        )
        self.assertEqual(pending_service.live_data_calls, 1)

    def test_chat_context_keeps_noi_and_nghe_meanings(self):
        settings = Settings(data_dir=Path(tempfile.mkdtemp()))
        restorer = SyncDiacriticRestorer(
            word_map={
                "noi": ["n\u1ed9i", "n\u00f3i"],
                "biet": ["bi\u1ebft"],
                "nghe": ["ngh\u1ec7", "nghe"],
                "ban": ["b\u00e0n"],
                "tan": ["t\u00e1n"],
            },
            bigram_freq={"n\u00f3i_cho": 9},
        )
        service = LiveNormalizerService(
            settings,
            ChatPendingService(),
            diacritic_restorer=restorer,
        )

        result = service.normalize_live(
            "noi cho t biet dc k? T nghe mn ban tan.",
            submitted_by="demo",
            input_method="paste",
        )

        self.assertIn("N\u00f3i cho tao bi\u1ebft", result.primary_output)
        self.assertIn("Tao nghe m\u1ecdi ng\u01b0\u1eddi b\u00e0n t\u00e1n", result.primary_output)
        self.assertNotIn("N\u1ed9i cho", result.primary_output)
        self.assertNotIn("Tao ngh\u1ec7", result.primary_output)

    def test_build_variants_keeps_override_primary_when_it_falls_outside_first_combinations(self):
        settings = Settings(data_dir=Path(tempfile.mkdtemp()))
        service = LiveNormalizerService(settings, FakePendingService())
        token_groups = [
            {
                "type": "ambiguous",
                "value": "a",
                "abbr": f"x{index}",
                "token_index": index,
                "options": ["a", "b"],
                "ambiguity_id": f"x{index}:0",
            }
            for index in range(4)
        ]
        overrides = {f"x{index}:0": "b" for index in range(4)}

        variants = service._build_variants(token_groups, overrides)

        self.assertEqual(len(variants), 8)
        self.assertTrue(variants[0].is_primary)
        self.assertEqual(variants[0].output, "B b b b")

    def test_build_variants_collapses_large_ambiguity_sets_to_primary_output(self):
        settings = Settings(
            data_dir=Path(tempfile.mkdtemp()),
            live_variant_max_ambiguities=2,
        )
        service = LiveNormalizerService(settings, FakePendingService())
        token_groups = [
            {
                "type": "ambiguous",
                "value": "a",
                "abbr": f"x{index}",
                "token_index": index,
                "options": ["a", "b"],
                "ambiguity_id": f"x{index}:0",
            }
            for index in range(3)
        ]

        variants = service._build_variants(token_groups, {})

        self.assertEqual(len(variants), 1)
        self.assertEqual(variants[0].output, "A a a")
        self.assertTrue(variants[0].is_primary)

    def test_semantic_verification_auto_resolves_ambiguity_without_user_choice(self):
        settings = Settings(data_dir=Path(tempfile.mkdtemp()))
        verifier = FakeSemanticVerifier(
            verified_text="Hôm nay đi đăng ký thẻ ngân hàng phải không",
            confidence=0.93,
        )
        service = LiveNormalizerService(
            settings,
            FakePendingService(),
            semantic_verifier=verifier,
        )
        result = service.normalize_live("hôm nay đi đk thẻ ngân hàng pk", submitted_by="demo")

        result = self._run(
            service.apply_semantic_verification(
                result,
                original_text="hôm nay đi đk thẻ ngân hàng pk",
                word_map={},
            )
        )

        self.assertEqual(result.primary_output, "Hôm nay đi đăng ký thẻ ngân hàng phải không")
        self.assertEqual(result.ambiguities, [])
        self.assertEqual([variant.output for variant in result.variants], [result.primary_output])
        self.assertTrue(result.semantic_verified)
        self.assertEqual(result.semantic_confidence, 0.93)
        self.assertEqual(
            verifier.calls[0]["abbreviation_options"],
            {"đk": ["đăng ký", "đúng không"]},
        )

    def test_real_verifier_applies_inferred_teencode_without_claiming_certainty(self):
        from app.ai.semantic_verifier import SemanticVerifier
        from test_semantic_verifier import _StubClient
        import json

        client = _StubClient(json.dumps({
            "verified_text": "Hôm nay đi đăng ký thẻ ngân hàng phải không",
            "corrections": [["đk", "đăng ký"], ["pk", "phải không"]],
            "confidence": 0.55,
        }))
        service = LiveNormalizerService(
            Settings(data_dir=Path(tempfile.mkdtemp())), FakePendingService(),
            semantic_verifier=SemanticVerifier(ai_client=client, confidence_threshold=0.7),
        )
        source = "hôm nay đi đk thẻ ngân hàng pk"
        result = service.normalize_live(source, submitted_by="demo")
        result = self._run(service.apply_semantic_verification(result, original_text=source))
        self.assertEqual(result.primary_output, "Hôm nay đi đăng ký thẻ ngân hàng phải không")
        self.assertEqual(result.semantic_status, "uncertain")
        self.assertEqual(result.semantic_status_reason, "ai_inferred_meaning")
        self.assertFalse(result.semantic_verified)
        self.assertEqual(result.ambiguities, [])

    def test_ai_changes_are_marked_separately_from_dataset_changes(self):
        verifier = FakeSemanticVerifier(
            verified_text="Hôm nay đi đúng không thẻ ngân hàng phải không",
            corrections=[("đăng ký", "đúng không")],
        )
        service = LiveNormalizerService(Settings(data_dir=Path(tempfile.mkdtemp())), FakePendingService(), semantic_verifier=verifier)
        source = "hôm nay đi đk thẻ ngân hàng pk"
        result = service.normalize_live(source, submitted_by="demo")
        result = self._run(service.apply_semantic_verification(result, original_text=source))

        ai_changes = [change for change in result.changes if "ai" in change["kinds"]]
        self.assertTrue(ai_changes)
        self.assertTrue(all(change["outputText"] for change in ai_changes))
        self.assertTrue(any("teencode" in change["kinds"] for change in ai_changes))

    def test_real_verifier_skips_ai_without_semantic_signal(self):
        from app.ai.semantic_verifier import SemanticVerifier
        from test_semantic_verifier import _StubClient
        import json

        client = _StubClient(json.dumps({"verified_text": "ignored", "confidence": 0.99, "corrections": []}))
        service = LiveNormalizerService(
            Settings(data_dir=Path(tempfile.mkdtemp())), FakePendingService(),
            semantic_verifier=SemanticVerifier(ai_client=client),
        )
        result = service.normalize_live("xin chao", submitted_by="demo")
        result = self._run(service.apply_semantic_verification(result, original_text="xin chao"))
        self.assertEqual(client.complete.call_count, 0)
        self.assertEqual(result.semantic_status_reason, "no_semantic_signal")

    def test_low_confidence_full_text_rewrite_keeps_dataset_baseline(self):
        """A shape-valid but uncertain general rewrite must not degrade output."""
        from app.ai.semantic_verifier import SemanticVerifier
        from test_semantic_verifier import _StubClient
        import json

        client = _StubClient(json.dumps({
            "verified_text": "Tôi ăn ngủ.",
            "corrections": [["Tôi đi học.", "Tôi ăn ngủ."]],
            "confidence": 0.2,
        }))
        service = LiveNormalizerService(
            Settings(data_dir=Path(tempfile.mkdtemp())),
            FakePendingService(),
            semantic_verifier=SemanticVerifier(ai_client=client, confidence_threshold=0.7),
        )
        source = "Tôi đi học."
        result = service.normalize_live(source, submitted_by="demo")
        result = self._run(service.apply_semantic_verification(result, original_text=source))

        self.assertEqual(result.primary_output, source)
        self.assertEqual(result.semantic_status, "not_needed")
        self.assertEqual(result.semantic_status_reason, "no_semantic_signal")
        self.assertFalse(result.semantic_verified)
        self.assertEqual(client.complete.call_count, 0)

    def test_semantic_zero_verified_chunks_is_not_marked_verified(self):
        settings = Settings(data_dir=Path(tempfile.mkdtemp()))
        verifier = FakeSemanticVerifier(
            verified_text="ignored",
            confidence=0.99,
            verified_chunks=0,
            status="not_checked",
            reason="no_eligible_chunks",
        )
        service = LiveNormalizerService(
            settings,
            FakePendingService(),
            semantic_verifier=verifier,
        )
        result = service.normalize_live("hôm nay đi đk thẻ ngân hàng pk", submitted_by="demo")

        result = self._run(
            service.apply_semantic_verification(
                result,
                original_text="hôm nay đi đk thẻ ngân hàng pk",
                word_map={},
            )
        )

        self.assertFalse(result.semantic_verified)
        self.assertEqual(result.semantic_status, "not_checked")
        self.assertEqual(result.semantic_verified_chunks, 0)

    def test_semantic_partial_scope_is_reported_without_full_verification(self):
        settings = Settings(data_dir=Path(tempfile.mkdtemp()))
        verifier = FakeSemanticVerifier(
            verified_text="Hôm nay đi đăng ký thẻ ngân hàng phải không",
            confidence=0.99,
            verified_chunks=1,
            total_chunks=2,
        )
        service = LiveNormalizerService(
            settings,
            FakePendingService(),
            semantic_verifier=verifier,
        )
        result = service.normalize_live("hôm nay đi đk thẻ ngân hàng pk", submitted_by="demo")

        result = self._run(
            service.apply_semantic_verification(
                result,
                original_text="hôm nay đi đk thẻ ngân hàng pk",
                word_map={},
            )
        )

        self.assertFalse(result.semantic_verified)
        self.assertEqual(result.semantic_status, "partial")
        self.assertEqual((result.semantic_verified_chunks, result.semantic_total_chunks), (1, 2))

    def test_semantic_rate_limit_is_exposed_without_dropping_rule_output(self):
        settings = Settings(data_dir=Path(tempfile.mkdtemp()))
        verifier = FakeSemanticVerifier(
            verified_text="discarded",
            confidence=0.0,
            verified_chunks=0,
            status="quota",
            reason="rate_limited",
        )
        service = LiveNormalizerService(
            settings,
            FakePendingService(),
            semantic_verifier=verifier,
        )
        result = service.normalize_live("hôm nay đi đk thẻ ngân hàng pk", submitted_by="demo")
        original_output = result.primary_output

        result = self._run(
            service.apply_semantic_verification(
                result,
                original_text="hôm nay đi đk thẻ ngân hàng pk",
                word_map={},
            )
        )

        self.assertEqual(result.primary_output, original_output)
        self.assertEqual(result.semantic_status, "quota")
        self.assertFalse(result.semantic_verified)

    def test_semantic_verification_can_override_default_ambiguity_choice(self):
        settings = Settings(data_dir=Path(tempfile.mkdtemp()))
        verifier = FakeSemanticVerifier(
            verified_text="Hôm nay đi đúng không thẻ ngân hàng phải không",
            corrections=[("đăng ký", "đúng không")],
            confidence=0.95,
        )
        service = LiveNormalizerService(
            settings,
            FakePendingService(),
            semantic_verifier=verifier,
        )
        result = service.normalize_live("hôm nay đi đk thẻ ngân hàng pk", submitted_by="demo")

        result = self._run(
            service.apply_semantic_verification(
                result,
                original_text="hôm nay đi đk thẻ ngân hàng pk",
                word_map={},
            )
        )

        self.assertEqual(result.primary_output, "Hôm nay đi đúng không thẻ ngân hàng phải không")
        self.assertEqual(result.ambiguities, [])
        self.assertEqual(result.semantic_corrections, [("đăng ký", "đúng không")])
        self.assertIn("SEMANTIC", result.error_types)
        self.assertEqual(
            [
                {
                    "abbr": span["abbr"],
                    "expanded": result.primary_output[span["start"] : span["end"]],
                }
                for span in result.to_payload()["expandedAbbreviations"]
            ],
            [{"abbr": "pk", "expanded": "phải không"}],
        )

    def test_span_remap_does_not_highlight_short_accentless_words_as_abbreviations(self):
        output = "Hiện nay, đánh giá sản phẩm gia dụng gì cũng cần rõ ràng"

        remapped = _remap_expanded_abbreviation_spans(
            [
                {
                    "abbr": "j",
                    "expanded": "gì",
                    "start": 0,
                    "end": 2,
                    "source": "token",
                }
            ],
            output,
        )

        self.assertEqual(
            [
                {
                    "abbr": span["abbr"],
                    "expanded": output[span["start"] : span["end"]],
                }
                for span in remapped
            ],
            [{"abbr": "j", "expanded": "gì"}],
        )

        self.assertEqual(
            _remap_expanded_abbreviation_spans(
                [{"abbr": "j", "expanded": "gi", "source": "token"}],
                output,
            ),
            [],
        )

    def test_semantic_verification_receives_diacritic_change_options(self):
        settings = Settings(data_dir=Path(tempfile.mkdtemp()))
        verifier = FakeSemanticVerifier(
            verified_text="AI Studio chạy tốt",
            confidence=0.9,
        )
        service = LiveNormalizerService(
            settings,
            FakePendingService(),
            semantic_verifier=verifier,
        )
        result = service.normalize_live("placeholder", submitted_by="demo")
        result.diacritic_applied = True
        result.diacritic_changes = [("AI", "Ai"), ("tot", "tốt")]
        result.primary_output = "Ai Studio chạy tốt"
        result.variants[0].output = result.primary_output

        self._run(
            service.apply_semantic_verification(
                result,
                original_text="AI Studio chay tot",
                word_map={},
            )
        )

        self.assertEqual(
            verifier.calls[0]["diacritic_candidates"],
            {"ai": ["Ai", "AI"], "tot": ["tốt", "tot"]},
        )

    def _run(self, coro):
        import asyncio

        return asyncio.run(coro)


if __name__ == "__main__":
    unittest.main()
