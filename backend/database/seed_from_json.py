from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import get_settings  # noqa: E402  (sys.path must be set up first)
from app.data_manager.pending_service import (  # noqa: E402
    PendingAbbreviationService,
)


def main() -> None:
    settings = get_settings()
    service = PendingAbbreviationService(settings)

    if not service.db_is_ready():
        raise SystemExit("SQL Server chua san sang. Kiem tra .env va SQL service truoc khi seed.")

    result = service.seed_from_json()
    print("Seed hoan tat:")
    for key, value in result.items():
        print(f"- {key}: {value}")


if __name__ == "__main__":
    main()
