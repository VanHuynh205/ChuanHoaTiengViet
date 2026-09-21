import json
import os
import re
import uuid


# This script lives in ``backend/scripts/``; data folders are one level up.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEGACY_DATA_DIR = os.path.join(BASE_DIR, "DataTuVietTat_and_TuDienTiengViet")
ABBREVIATION_DIR = os.path.join(BASE_DIR, "data", "abbreviations")
DICTIONARY_DIR = os.path.join(BASE_DIR, "data", "dictionaries")
EMOJI_DIR = os.path.join(BASE_DIR, "data", "Emoji")
DEFAULT_CREATED_AT = "2025-01-01T00:00:00"
DEFAULT_APPROVED_BY = "admin"


def read_teencode(txt_path):
    data = []
    with open(txt_path, "r", encoding="utf-8") as f:
        for line in f:
            raw_line = line.strip()
            if not raw_line:
                continue

            parts = raw_line.split("\t")
            if len(parts) == 2:
                key, value = parts
            else:
                parts = re.split(r"\s{2,}", raw_line)
                if len(parts) != 2:
                    continue
                key, value = parts

            key = key.strip()
            value = value.strip()
            if key and value:
                data.append(
                    {
                        "id": str(uuid.uuid4()),
                        "abbr": key,
                        "expanded": value,
                        "domain": "text_normalization",
                        "source": "manual",
                        "approved": True,
                        "created_at": DEFAULT_CREATED_AT,
                        "approved_by": DEFAULT_APPROVED_BY,
                    }
                )
    return {"abbreviations": data}


def read_word_list(txt_path, dictionary_name):
    data = []
    with open(txt_path, "r", encoding="utf-8") as f:
        for line in f:
            word = line.strip()
            if not word:
                continue
            data.append(
                {
                    "id": str(uuid.uuid4()),
                    "word": word,
                    "dictionary": dictionary_name,
                    "source": "manual",
                    "approved": True,
                    "created_at": DEFAULT_CREATED_AT,
                    "approved_by": DEFAULT_APPROVED_BY,
                }
            )
    return {"words": data}


def parse_code_points(code_points_raw):
    parts = []
    for token in code_points_raw.split():
        if ".." in token:
            start, end = token.split("..", 1)
            parts.append({"type": "range", "start": start, "end": end})
        else:
            parts.append({"type": "single", "value": token})
    return parts


def parse_unicode_header(lines, source_name):
    metadata = {"source_file": source_name}
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# Date:"):
            metadata["date"] = stripped.removeprefix("# Date:").strip()
        elif stripped.startswith("# Version:"):
            metadata["version"] = stripped.removeprefix("# Version:").strip()
    return metadata


def read_emoji_test(txt_path):
    header_lines = []
    entries = []
    current_group = None
    current_subgroup = None

    with open(txt_path, "r", encoding="utf-8-sig") as f:
        for line in f:
            raw_line = line.rstrip("\n")
            stripped = raw_line.strip()

            if not stripped:
                continue

            if stripped.startswith("#"):
                header_lines.append(stripped)
                if stripped.startswith("# group:"):
                    current_group = stripped.removeprefix("# group:").strip()
                elif stripped.startswith("# subgroup:"):
                    current_subgroup = stripped.removeprefix("# subgroup:").strip()
                continue

            left, right = stripped.split("#", 1)
            code_points_raw, status = [part.strip() for part in left.split(";", 1)]
            comment = right.strip()

            match = re.match(r"^(?P<emoji>\S+)\s+E(?P<version>[0-9.]+)\s+(?P<name>.+)$", comment)
            if not match:
                continue

            entries.append(
                {
                    "id": str(uuid.uuid4()),
                    "code_points_raw": code_points_raw,
                    "code_points": parse_code_points(code_points_raw),
                    "status": status,
                    "emoji": match.group("emoji"),
                    "unicode_version": match.group("version"),
                    "name": match.group("name").strip(),
                    "group": current_group,
                    "subgroup": current_subgroup,
                    "source": "unicode_emoji_test",
                    "approved": True,
                    "created_at": DEFAULT_CREATED_AT,
                    "approved_by": DEFAULT_APPROVED_BY,
                }
            )

    return {
        "metadata": parse_unicode_header(header_lines, os.path.basename(txt_path)),
        "entries": entries,
    }


def read_emoji_sequences(txt_path, source_name):
    header_lines = []
    entries = []

    with open(txt_path, "r", encoding="utf-8-sig") as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue

            if stripped.startswith("#"):
                header_lines.append(stripped)
                continue

            fields_part, _, comment_part = stripped.partition("#")
            fields = [part.strip() for part in fields_part.split(";")]
            if len(fields) < 3:
                continue

            code_points_raw, sequence_type, description = fields[:3]
            comment = comment_part.strip()
            match = re.match(r"^E(?P<version>[0-9.]+)\s*\[(?P<count>\d+)\]\s*(?:\((?P<sample>.*)\))?$", comment)

            entries.append(
                {
                    "id": str(uuid.uuid4()),
                    "code_points_raw": code_points_raw,
                    "code_points": parse_code_points(code_points_raw),
                    "sequence_type": sequence_type,
                    "description": description,
                    "unicode_version": match.group("version") if match else None,
                    "count": int(match.group("count")) if match else None,
                    "sample": match.group("sample") if match else None,
                    "source": source_name,
                    "approved": True,
                    "created_at": DEFAULT_CREATED_AT,
                    "approved_by": DEFAULT_APPROVED_BY,
                }
            )

    return {
        "metadata": parse_unicode_header(header_lines, os.path.basename(txt_path)),
        "entries": entries,
    }


def read_emoji_readme(txt_path):
    title = None
    version = None
    files = []
    related_files = []
    documentation = None
    current_bucket = None

    with open(txt_path, "r", encoding="utf-8-sig") as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue

            if stripped.startswith("# ") and title is None:
                title = stripped.removeprefix("# ").strip()
                continue

            if "Version " in stripped and version is None:
                version_match = re.search(r"Version\s+([0-9.]+)", stripped)
                if version_match:
                    version = version_match.group(1)

            if re.fullmatch(r"Public/[0-9.]+/emoji/", stripped):
                current_bucket = files
                continue

            if re.fullmatch(r"Public/[0-9.]+/ucd/emoji/", stripped):
                current_bucket = related_files
                continue

            if stripped.startswith("For documentation, see "):
                documentation = stripped.removeprefix("For documentation, see ").strip()
                current_bucket = None
                continue

            if current_bucket is not None and stripped.endswith(".txt"):
                current_bucket.append(stripped)

    return {
        "metadata": {
            "source_file": os.path.basename(txt_path),
            "title": title,
            "version": version,
        },
        "files": files,
        "related_files": related_files,
        "documentation": documentation,
    }


def write_json(json_path, data):
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main():
    os.makedirs(ABBREVIATION_DIR, exist_ok=True)
    os.makedirs(DICTIONARY_DIR, exist_ok=True)
    os.makedirs(EMOJI_DIR, exist_ok=True)

    files = {
        "teencode": read_teencode,
        "Viet11K": read_word_list,
        "Viet22K": read_word_list,
        "Viet39K": read_word_list,
        "Viet74K": read_word_list,
    }

    for base_name, reader in files.items():
        txt_path = os.path.join(LEGACY_DATA_DIR, f"{base_name}.txt")
        if base_name == "teencode":
            json_path = os.path.join(ABBREVIATION_DIR, f"{base_name}.json")
        else:
            json_path = os.path.join(DICTIONARY_DIR, f"{base_name}.json")

        if not os.path.exists(txt_path):
            print(f"Bo qua {base_name}: khong tim thay file TXT.")
            continue

        if base_name == "teencode":
            data = reader(txt_path)
        else:
            data = reader(txt_path, base_name)
        write_json(json_path, data)
        print(f"Da tao {os.path.basename(json_path)}")

    emoji_files = {
        "emoji-test": (read_emoji_test, "emoji-test.txt"),
        "emoji-sequences": (lambda path: read_emoji_sequences(path, "unicode_emoji_sequences"), "emoji-sequences.txt"),
        "emoji-zwj-sequences": (
            lambda path: read_emoji_sequences(path, "unicode_emoji_zwj_sequences"),
            "emoji-zwj-sequences.txt",
        ),
        "ReadMe": (read_emoji_readme, "ReadMe.txt"),
    }

    for base_name, (reader, source_file) in emoji_files.items():
        txt_path = os.path.join(EMOJI_DIR, source_file)
        json_path = os.path.join(EMOJI_DIR, f"{base_name}.json")

        if not os.path.exists(txt_path):
            print(f"Bo qua {base_name}: khong tim thay file TXT.")
            continue

        data = reader(txt_path)
        write_json(json_path, data)
        print(f"Da tao {os.path.basename(json_path)}")


if __name__ == "__main__":
    main()
