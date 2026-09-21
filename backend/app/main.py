from __future__ import annotations

from typing import Callable, Dict, Iterable, List

from app.bootstrap import build_pipeline
from app.config import get_settings
from app.data_manager.history_repo import HistoryRepository
from app.data_manager.pending_service import PendingAbbreviationService
from app.utils.logger import configure_logging, get_logger

# Re-export ``build_pipeline`` so existing callers (`from app.main import build_pipeline`)
# keep working while routes import from ``app.bootstrap`` directly.
__all__ = [
    "build_pipeline",
    "handle_add_meaning_command",
    "capture_pending_meanings",
    "run_cli",
]

logger = get_logger(__name__)
ADD_MEANING_COMMANDS = {"/them-nghia", "/add-meaning"}


def _approve_pending_for_future_use(
    pending_service: PendingAbbreviationService,
    pending_id: str,
    reviewer: str,
) -> dict:
    try:
        return pending_service.approve_pending_abbreviation(
            pending_id=pending_id,
            reviewer=reviewer,
            review_notes="CLI admin mode auto-approved pending suggestion for demo training.",
        )
    except Exception as exc:  # pragma: no cover - defensive runtime guard
        logger.exception("Khong the auto-approve pending '%s' trong che do admin CLI.", pending_id)
        return {
            "pending_id": pending_id,
            "status": "APPROVE_FAILED",
            "error": str(exc),
        }


def handle_add_meaning_command(
    pending_service: PendingAbbreviationService,
    command_text: str,
    submitted_by: str,
    input_func: Callable[[str], str] = input,
    output_func: Callable[[str], None] = print,
    auto_approve: bool = False,
) -> bool:
    parts = command_text.strip().split(maxsplit=2)
    if not parts or parts[0].lower() not in ADD_MEANING_COMMANDS:
        return False

    abbr = parts[1].strip() if len(parts) > 1 else ""
    meaning = parts[2].strip() if len(parts) > 2 else ""

    if not abbr:
        abbr = input_func("Nhap tu viet tat can them nghia: ").strip()
    if not meaning:
        meaning = input_func("Nhap nghia goc moi cho tu viet tat: ").strip()

    result = pending_service.add_abbreviation_meaning(
        abbr=abbr,
        meaning=meaning,
        reviewer=submitted_by,
        source="cli_manual_command",
        review_notes=(
            "CLI command add meaning." if auto_approve else "CLI command submitted meaning."
        ),
        approve_immediately=auto_approve,
    )
    status = result.get("status")
    normalized_abbr = result.get("abbr", abbr)

    if status == "APPROVED":
        output_func(
            f"Da duyet ngay nghia moi cho '{normalized_abbr}'. Nghia chinh cu van duoc giu, nghia moi se duoc them vao danh sach nghia bo sung."
        )
    elif status == "MEANING_ALREADY_APPROVED":
        output_func(
            f"Nghia nay da ton tai san cho '{normalized_abbr}', he thong khong tao them pending moi."
        )
    elif status in {"SUGGESTION_CAPTURED", "SUGGESTION_APPENDED", "SUGGESTION_ALREADY_EXISTS"}:
        output_func(
            f"Da ghi nhan nghia moi cho '{normalized_abbr}' vao pending. Nghia nay se co hieu luc sau khi duoc admin duyet."
        )
    elif status == "DB_UNAVAILABLE":
        output_func("Khong the them nghia moi vi SQL Server chua san sang.")
    else:
        output_func(f"Khong the them nghia moi cho '{normalized_abbr}' (trang thai: {status}).")
    return True


def capture_pending_meanings(
    pending_service: PendingAbbreviationService,
    pending_submissions: Iterable[Dict[str, object]],
    submitted_by: str,
    input_func: Callable[[str], str] = input,
    output_func: Callable[[str], None] = print,
    auto_approve: bool = False,
) -> List[dict]:
    captured_results: List[dict] = []
    prompted_abbreviations: set[str] = set()
    approved_pending_ids: set[str] = set()

    for item in pending_submissions:
        abbr = str(item.get("abbr", "")).strip().lower()
        pending_id = str(item.get("pending_id", "") or "").strip()
        needs_user_meaning = bool(item.get("needs_user_meaning"))
        can_add_more_meanings = bool(item.get("can_add_more_meanings"))
        has_suggested = bool(item.get("has_suggested"))
        if not abbr or not pending_id:
            continue

        if (
            auto_approve
            and has_suggested
            and not needs_user_meaning
            and not can_add_more_meanings
            and pending_id not in approved_pending_ids
        ):
            approval_result = _approve_pending_for_future_use(
                pending_service=pending_service,
                pending_id=pending_id,
                reviewer=submitted_by,
            )
            captured_results.append(approval_result)
            approved_pending_ids.add(pending_id)

            if approval_result.get("status") == "APPROVED":
                output_func(
                    f"Pending cua '{abbr}' da co nghia goc. He thong da duyet ngay va them vao data cho cac lan chay sau."
                )
            else:
                output_func(
                    f"Pending cua '{abbr}' da co nghia goc nhung chua duyet duoc ngay (trang thai: {approval_result.get('status')})."
                )
            continue

        if (not needs_user_meaning and not can_add_more_meanings) or abbr in prompted_abbreviations:
            continue

        prompted_abbreviations.add(abbr)
        if needs_user_meaning:
            output_func(f"\nTu viet tat '{abbr}' chua co nghia goc da duyet.")
            prompt = f"Nhap nghia goc cho '{abbr}' (bo trong de bo qua): "
        else:
            output_func(f"\nTu viet tat '{abbr}' da co nghia goc trong pending.")
            prompt = f"Nhap them nghia goc khac cho '{abbr}' (bo trong de giu nguyen): "

        meaning = input_func(prompt).strip()
        if not meaning:
            if auto_approve and has_suggested and pending_id not in approved_pending_ids:
                approval_result = _approve_pending_for_future_use(
                    pending_service=pending_service,
                    pending_id=pending_id,
                    reviewer=submitted_by,
                )
                captured_results.append(approval_result)
                approved_pending_ids.add(pending_id)

                if approval_result.get("status") == "APPROVED":
                    output_func(
                        f"Khong bo sung them nghia cho '{abbr}'. He thong da duyet pending hien tai va dong bo cho cac lan chay sau."
                    )
                else:
                    output_func(
                        f"Khong bo sung them nghia cho '{abbr}' va pending hien tai chua duyet duoc ngay (trang thai: {approval_result.get('status')})."
                    )
            elif needs_user_meaning:
                output_func(f"Bo qua '{abbr}'. Pending van duoc giu de duyet sau.")
            else:
                output_func(
                    f"Khong bo sung them nghia cho '{abbr}'. Pending hien tai van duoc giu nguyen."
                )
            continue

        capture_result = pending_service.capture_pending_suggestion(
            pending_id=pending_id,
            suggested=meaning,
            submitted_by=submitted_by,
        )
        captured_results.append(capture_result)

        status = capture_result.get("status")
        if auto_approve and status in {
            "SUGGESTION_CAPTURED",
            "SUGGESTION_ALREADY_EXISTS",
            "SUGGESTION_APPENDED",
        }:
            approval_result = _approve_pending_for_future_use(
                pending_service=pending_service,
                pending_id=pending_id,
                reviewer=submitted_by,
            )
            captured_results.append(approval_result)
            approved_pending_ids.add(pending_id)

            if approval_result.get("status") == "APPROVED":
                output_func(
                    f"Da duyet ngay '{abbr}' trong che do admin CLI. Tu nay da duoc them vao data cho cac lan chay sau."
                )
            else:
                output_func(
                    f"Da luu nghia goc cho '{abbr}' vao pending nhung chua duyet duoc ngay (trang thai: {approval_result.get('status')})."
                )
        elif status == "SUGGESTION_CAPTURED":
            output_func(
                f"Da luu nghia goc cho '{abbr}' vao pending. Nghia nay chi co hieu luc sau khi duoc admin duyet."
            )
        elif status == "SUGGESTION_APPENDED":
            output_func(
                f"Da bo sung them mot nghia goc cho '{abbr}' vao pending. Nghia cu van duoc giu nguyen cho den khi admin duyet."
            )
        elif status == "SUGGESTION_ALREADY_EXISTS":
            output_func(
                f"Nghia goc vua nhap cho '{abbr}' da ton tai truoc do, nen he thong giu nguyen du lieu hien tai."
            )
        elif status == "DB_UNAVAILABLE":
            output_func(f"Khong the luu nghia goc cho '{abbr}' vi SQL Server chua san sang.")
        else:
            output_func(f"Khong the cap nhat pending cho '{abbr}' (trang thai: {status}).")

    return captured_results


def run_cli() -> None:
    configure_logging()
    settings = get_settings()
    pipeline = build_pipeline(settings)
    history_repository = HistoryRepository(settings)
    runtime_actor = "cli_admin" if settings.cli_assume_admin else "cli_user"

    print("\n" + "=" * 40)
    print("HE THONG CHUAN HOA TIENG VIET")
    print("=" * 40)
    print("Nhap van ban can chuan hoa. Go 'exit' de thoat.")
    print("Lenh them nghia nhanh: /them-nghia <tu-viet-tat> <nghia-goc-moi>")
    if settings.cli_assume_admin:
        print(
            "Che do hien tai: Dang gia lap quyen admin de train va duyet ngay tu viet tat moi cho lan chay sau."
        )

    while True:
        user_input = input("\n>> ").strip()

        if user_input.lower() in {"exit", "quit", "thoat"}:
            break
        if not user_input:
            continue
        if handle_add_meaning_command(
            pending_service=pipeline.pending_service,
            command_text=user_input,
            submitted_by=runtime_actor,
            input_func=input,
            output_func=print,
            auto_approve=settings.cli_assume_admin,
        ):
            continue

        result = pipeline.normalize(user_input, submitted_by=runtime_actor)
        try:
            history_repository.log_normalization(
                input_text=user_input,
                output_text=result.normalized_text,
                error_types=result.error_types,
                source_kind="cli_rule_based",
                username_snapshot=runtime_actor,
            )
        except Exception:
            # History is best-effort telemetry for the CLI: a missing or offline
            # SQL Server must not kill the session after the result was produced.
            logger.warning("Khong luu duoc lich su chuan hoa vao SQL Server.", exc_info=True)
            print("Canh bao: khong luu duoc lich su vao database (SQL Server chua san sang).")
        print("\n--- KET QUA CHUAN HOA ---")
        print(f"Dong goc : {user_input}\n")
        print(f"Dong moi : {result.normalized_text}\n")
        print(f"Loi sua  : {', '.join(result.error_types) if result.error_types else 'khong'}")
        if result.pending_submissions:
            print("Pending  :")
            for item in result.pending_submissions:
                print(f"  - {item['abbr']}: {item['status']}")
        if result.warnings:
            print("Canh bao :")
            for warning in result.warnings:
                print(f"  - {warning}")
        print("-" * 30)
        capture_pending_meanings(
            pending_service=pipeline.pending_service,
            pending_submissions=result.pending_submissions,
            submitted_by=runtime_actor,
            auto_approve=settings.cli_assume_admin,
        )


if __name__ == "__main__":
    run_cli()
