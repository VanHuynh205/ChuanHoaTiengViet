from pathlib import Path


from scripts.convert_data_to_json import (
    read_emoji_readme,
    read_emoji_sequences,
    read_emoji_test,
)


def _write_temp_file(tmp_path: Path, content: str) -> Path:
    target = tmp_path / "sample.txt"
    target.write_text(content, encoding="utf-8")
    return target


def test_read_emoji_test_parses_group_subgroup_and_entries(tmp_path):
    target = _write_temp_file(
        tmp_path,
        "\n".join(
            [
                "# emoji-test.txt",
                "# Date: 2025-08-04, 20:55:31 GMT",
                "# Version: 17.0",
                "# group: Smileys & Emotion",
                "# subgroup: face-smiling",
                "1F600 ; fully-qualified # 😀 E1.0 grinning face",
                "1F603 ; fully-qualified # 😃 E0.6 grinning face with big eyes",
                "",
            ]
        ),
    )

    payload = read_emoji_test(str(target))

    assert payload["metadata"]["version"] == "17.0"
    assert payload["metadata"]["date"] == "2025-08-04, 20:55:31 GMT"
    assert len(payload["entries"]) == 2
    assert payload["entries"][0] == {
        "id": payload["entries"][0]["id"],
        "code_points_raw": "1F600",
        "code_points": [{"type": "single", "value": "1F600"}],
        "status": "fully-qualified",
        "emoji": "😀",
        "unicode_version": "1.0",
        "name": "grinning face",
        "group": "Smileys & Emotion",
        "subgroup": "face-smiling",
        "source": "unicode_emoji_test",
        "approved": True,
        "created_at": "2025-01-01T00:00:00",
        "approved_by": "admin",
    }


def test_read_emoji_sequences_parses_ranges_and_comment_metadata(tmp_path):
    target = _write_temp_file(
        tmp_path,
        "\n".join(
            [
                "# emoji-sequences.txt",
                "# Date: 2025-07-25, 17:54:32 GMT",
                "# Version: 17.0",
                "231A..231B ; Basic_Emoji ; watch..hourglass done # E0.6 [2] (⌚..⌛)",
                "1F1FA 1F1F8 ; RGI_Emoji_Flag_Sequence ; flag: United States # E0.6 [1] (🇺🇸)",
                "",
            ]
        ),
    )

    payload = read_emoji_sequences(str(target), "unicode_emoji_sequences")

    assert payload["metadata"]["version"] == "17.0"
    assert len(payload["entries"]) == 2
    assert payload["entries"][0] == {
        "id": payload["entries"][0]["id"],
        "code_points_raw": "231A..231B",
        "code_points": [{"type": "range", "start": "231A", "end": "231B"}],
        "sequence_type": "Basic_Emoji",
        "description": "watch..hourglass done",
        "unicode_version": "0.6",
        "count": 2,
        "sample": "⌚..⌛",
        "source": "unicode_emoji_sequences",
        "approved": True,
        "created_at": "2025-01-01T00:00:00",
        "approved_by": "admin",
    }
    assert payload["entries"][1]["code_points"] == [
        {"type": "single", "value": "1F1FA"},
        {"type": "single", "value": "1F1F8"},
    ]
    assert payload["entries"][1]["sample"] == "🇺🇸"


def test_read_emoji_readme_extracts_file_lists(tmp_path):
    target = _write_temp_file(
        tmp_path,
        "\n".join(
            [
                "# Unicode Emoji",
                "This directory contains final data files for Unicode Emoji, Version 17.0",
                "",
                "Public/17.0.0/emoji/",
                "",
                "  emoji-sequences.txt",
                "  emoji-zwj-sequences.txt",
                "  emoji-test.txt",
                "",
                "The following related files are found in the UCD for Version 17.0",
                "",
                "Public/17.0.0/ucd/emoji/",
                "",
                "  emoji-data.txt",
                "  emoji-variation-sequences.txt",
                "",
                "For documentation, see UTS #51 Unicode Emoji, Version 17.0",
                "",
            ]
        ),
    )

    payload = read_emoji_readme(str(target))

    assert payload["metadata"]["title"] == "Unicode Emoji"
    assert payload["metadata"]["version"] == "17.0"
    assert payload["files"] == ["emoji-sequences.txt", "emoji-zwj-sequences.txt", "emoji-test.txt"]
    assert payload["related_files"] == ["emoji-data.txt", "emoji-variation-sequences.txt"]
    assert payload["documentation"] == "UTS #51 Unicode Emoji, Version 17.0"
