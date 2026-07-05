"""
PostgreSQL persistence via SQLAlchemy.  [production item 2]

Stores drug-label metadata (for DB-level dedupe by UNIQUE label_id) and chat
sessions/messages (for history + last-N conversation memory).

Defaults to a local SQLite file so the app and tests run with zero external
services; docker-compose provides a postgresql+psycopg:// DATABASE_URL.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    select,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)

from app.config import get_settings


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class DrugLabel(Base):
    """One indexed FDA drug label. label_id UNIQUE enforces dedupe at the DB."""
    __tablename__ = "drug_labels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    label_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    drug_name: Mapped[str] = mapped_column(String(256), default="")
    brand_name: Mapped[str] = mapped_column(String(256), default="")
    source_url: Mapped[str] = mapped_column(Text, default="")
    indexed_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class KV(Base):
    """Tiny key/value store for ingestion state (e.g. the growth watermark)."""
    __tablename__ = "kv_store"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class ChatSession(Base):
    """A chat session (table `sessions`)."""
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    messages: Mapped[list["Message"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class Message(Base):
    """A single chat message (user or assistant)."""
    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    citations: Mapped[list | None] = mapped_column(JSON, default=None)
    trace_id: Mapped[str | None] = mapped_column(String(64), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    session: Mapped[ChatSession] = relationship(back_populates="messages")


# --------------------------------------------------------------- engine wiring
_engine = None
_SessionLocal: sessionmaker | None = None


def _make_engine():
    url = get_settings().database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args, future=True)


def get_engine():
    """Lazily create the SQLAlchemy engine singleton."""
    global _engine, _SessionLocal
    if _engine is None:
        _engine = _make_engine()
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _engine


def _session() -> Session:
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal()


def init_db() -> None:
    """Create tables if they don't exist."""
    Base.metadata.create_all(get_engine())


def reset_engine() -> None:
    """Dispose the engine (used by tests / simulated restart)."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


# ------------------------------------------------------------ drug-label helpers
def record_labels(records: list) -> int:
    """Insert new drug labels; skip any whose label_id already exists.

    Returns the count of newly inserted labels (existing ones are no-ops).
    """
    if not records:
        return 0
    with _session() as s:
        existing = {
            row[0] for row in s.execute(select(DrugLabel.label_id)).all()
        }
        inserted = 0
        seen = set(existing)
        for r in records:
            if r.label_id in seen:
                continue
            seen.add(r.label_id)
            s.add(DrugLabel(
                label_id=r.label_id,
                drug_name=getattr(r, "drug_name", ""),
                brand_name=getattr(r, "brand_name", ""),
                source_url=getattr(r, "source_url", ""),
            ))
            inserted += 1
        s.commit()
        return inserted


def get_known_label_ids() -> set[str]:
    """All label ids already recorded (feeds ingestion dedupe)."""
    with _session() as s:
        return {row[0] for row in s.execute(select(DrugLabel.label_id)).all()}


# ------------------------------------------------------------- KV / watermark
def get_kv(key: str, default: str = "") -> str:
    """Read a small ingestion-state value (e.g. the growth watermark)."""
    with _session() as s:
        row = s.get(KV, key)
        return row.value if row is not None else default


def set_kv(key: str, value: str) -> None:
    """Upsert a small ingestion-state value."""
    with _session() as s:
        row = s.get(KV, key)
        if row is None:
            s.add(KV(key=key, value=value, updated_at=_utcnow()))
        else:
            row.value = value
            row.updated_at = _utcnow()
        s.commit()


# ---------------------------------------------------------------- chat helpers
def create_session(session_id: str | None = None) -> str:
    """Create a chat session and return its id."""
    sid = session_id or uuid.uuid4().hex
    with _session() as s:
        if s.get(ChatSession, sid) is None:
            s.add(ChatSession(id=sid))
            s.commit()
    return sid


def add_message(
    session_id: str,
    role: str,
    content: str,
    citations: list | None = None,
    trace_id: str | None = None,
) -> int:
    """Persist a message; auto-creates the session if missing. Returns row id."""
    with _session() as s:
        if s.get(ChatSession, session_id) is None:
            s.add(ChatSession(id=session_id))
            s.flush()
        msg = Message(
            session_id=session_id,
            role=role,
            content=content,
            citations=citations,
            trace_id=trace_id,
        )
        s.add(msg)
        s.commit()
        return msg.id


def _row_to_dict(m: Message) -> dict:
    return {
        "id": m.id,
        "role": m.role,
        "content": m.content,
        "citations": m.citations or [],
        "trace_id": m.trace_id,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


def get_messages(session_id: str) -> list[dict]:
    """All messages for a session in chronological order."""
    with _session() as s:
        rows = s.execute(
            select(Message).where(Message.session_id == session_id).order_by(Message.id)
        ).scalars().all()
        return [_row_to_dict(m) for m in rows]


def get_recent_messages(session_id: str, n: int | None = None) -> list[dict]:
    """Last N messages (chronological order) for conversation memory."""
    if n is None:
        n = get_settings().memory_window
    with _session() as s:
        rows = s.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.id.desc())
            .limit(n)
        ).scalars().all()
        return [_row_to_dict(m) for m in reversed(rows)]
