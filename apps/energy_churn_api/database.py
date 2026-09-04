"""SQLite persistence for the hackathon demo."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import DateTime, Float, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

ROOT = Path(__file__).resolve().parents[2]
DATABASE_URL = f"sqlite:///{ROOT / 'data' / 'energy_churn.db'}"


class Base(DeclarativeBase):
    """Base SQLAlchemy model."""


class Customer(Base):
    """Synthetic pseudonymised customer profile."""

    __tablename__ = "customers"

    customer_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    tenure_months: Mapped[int] = mapped_column(Integer)
    sla_met_pct: Mapped[float] = mapped_column(Float)
    repeat_complaints: Mapped[int] = mapped_column(Integer)
    escalations: Mapped[int] = mapped_column(Integer)
    complaint_severity: Mapped[int] = mapped_column(Integer)
    sentiment_score: Mapped[float] = mapped_column(Float)
    nps_change: Mapped[float] = mapped_column(Float)
    csat_pct: Mapped[float] = mapped_column(Float)
    market_risk_index: Mapped[float] = mapped_column(Float)
    app_logins_30d: Mapped[int] = mapped_column(Integer)
    tariff_comparisons: Mapped[int] = mapped_column(Integer)
    direct_debit_cancelled: Mapped[int] = mapped_column(Integer)
    quote_requests: Mapped[int] = mapped_column(Integer)
    payment_days_late: Mapped[int] = mapped_column(Integer)


class Assessment(Base):
    """Latest explainable assessment for a customer."""

    __tablename__ = "assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[str] = mapped_column(String(20), index=True)
    volatility_score: Mapped[int] = mapped_column(Integer)
    risk_band: Mapped[str] = mapped_column(String(20))
    churn_probability: Mapped[float] = mapped_column(Float)
    drivers_json: Mapped[str] = mapped_column(Text)
    sentiment_label: Mapped[str] = mapped_column(String(20))
    recommendation: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class Intervention(Base):
    """Human-owned retention intervention state."""

    __tablename__ = "interventions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[str] = mapped_column(String(20), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    adviser_note: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class MarketSnapshot(Base):
    """Cached live or fallback market context."""

    __tablename__ = "market_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    market_risk_index: Mapped[float] = mapped_column(Float)
    price_eur_mwh: Mapped[float] = mapped_column(Float)
    price_change_pct: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(Text)
    source_mode: Mapped[str] = mapped_column(String(20))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def seed_database() -> None:
    """Create tables and seed only the synthetic customer cohort once."""
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        if session.query(Customer).count():
            return
        source = ROOT / "data" / "energy_churn_demo.csv"
        with source.open(newline="", encoding="utf-8") as csv_file:
            for row in csv.DictReader(csv_file):
                session.add(Customer(**{key: float(value) if "." in value else int(value) if key != "customer_id" else value for key, value in row.items()}))
        session.commit()


def get_session() -> Session:
    """Return a new database session for request handlers."""
    return SessionLocal()
