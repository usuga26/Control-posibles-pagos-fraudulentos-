"""Configuración de la base de datos con SQLAlchemy 2.x.

Usa `DATABASE_URL` del entorno. En desarrollo: SQLite. En producción: PostgreSQL.
No usar `create_all`; las migraciones se gestionan con Alembic.
"""
from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


def _make_engine():
    """Crea el engine según la URL configurada."""
    url = settings.database_url
    kwargs: dict = {}

    if url.startswith("sqlite"):
        kwargs["connect_args"] = {
            "check_same_thread": False,
            "timeout": 60,  # Esperar hasta 60s antes de error de bloqueo bajo alta concurrencia
        }

    return create_engine(url, **kwargs)


engine = _make_engine()

# Optimizaciones de concurrencia e integridad en SQLite
if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")       # Concurrencia de múltiples lectores y un escritor sin bloqueos
        cursor.execute("PRAGMA synchronous=NORMAL")     # Rendimiento acelerado de I/O en disco seguro
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)


class Base(DeclarativeBase):
    """Base declarativa para todos los modelos ORM."""


def get_db():
    """Dependencia FastAPI que provee una sesión de BD y la cierra al terminar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
