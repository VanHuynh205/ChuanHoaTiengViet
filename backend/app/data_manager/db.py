from __future__ import annotations

from threading import RLock
from typing import Any, Callable, Optional, Tuple
from urllib.parse import quote_plus

from app.config import Settings, get_settings

create_engine: Any
sessionmaker: Any
text: Any

try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
except ImportError:  # pragma: no cover - optional dependency in early setup
    create_engine = None
    sessionmaker = None
    text = None


_ENGINE_CACHE: dict[Settings, Any] = {}
_SESSION_FACTORY_CACHE: dict[Settings, Optional[Callable[[], Any]]] = {}
_CACHE_LOCK = RLock()


def build_server_name(settings: Settings) -> str:
    if settings.sql_mode == "localdb":
        instance = settings.sql_instance or "MSSQLLocalDB"
        return f"(localdb)\\{instance}"
    if settings.sql_instance:
        return f"{settings.sql_host}\\{settings.sql_instance}"
    return settings.sql_host


def use_windows_authentication(settings: Settings) -> bool:
    return settings.sql_mode == "localdb" or settings.sql_auth in {"windows", "trusted", "integrated"}


def build_odbc_connection_string(settings: Optional[Settings] = None) -> str:
    config = settings or get_settings()
    server = build_server_name(config)

    parts = [
        f"DRIVER={{{config.sql_driver}}}",
        f"SERVER={server}",
        f"DATABASE={config.sql_database}",
        f"Encrypt={config.sql_encrypt}",
        f"TrustServerCertificate={config.sql_trust_server_certificate}",
    ]

    if use_windows_authentication(config):
        parts.append("Trusted_Connection=yes")
    else:
        parts.append(f"UID={config.sql_username}")
        parts.append(f"PWD={config.sql_password}")

    return ";".join(parts)


def build_sqlalchemy_url(settings: Optional[Settings] = None) -> str:
    config = settings or get_settings()
    odbc_connect = quote_plus(build_odbc_connection_string(config))
    return f"mssql+pyodbc:///?odbc_connect={odbc_connect}"


def create_sqlalchemy_engine(settings: Optional[Settings] = None) -> Any | None:
    config = settings or get_settings()
    if create_engine is None:
        return None
    with _CACHE_LOCK:
        cached = _ENGINE_CACHE.get(config)
        if cached is not None:
            return cached
        engine = create_engine(
            build_sqlalchemy_url(config),
            future=True,
            pool_pre_ping=True,
            echo=config.sql_echo,
        )
        _ENGINE_CACHE[config] = engine
        return engine


def get_session_factory(settings: Optional[Settings] = None) -> Optional[Callable[[], Any]]:
    config = settings or get_settings()
    if sessionmaker is None:
        return None
    with _CACHE_LOCK:
        if config in _SESSION_FACTORY_CACHE:
            return _SESSION_FACTORY_CACHE[config]
        engine = create_sqlalchemy_engine(config)
        if engine is None:
            return None
        factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
        _SESSION_FACTORY_CACHE[config] = factory
        return factory


def health_check(settings: Optional[Settings] = None) -> Tuple[bool, str]:
    if create_engine is None or text is None:
        return False, "SQLAlchemy/pyodbc chua duoc cai dat."

    engine = create_sqlalchemy_engine(settings)
    if engine is None:
        return False, "Khong tao duoc SQL engine."

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True, "OK"
    except Exception as exc:  # pragma: no cover - depends on local SQL Server
        return False, str(exc)
