"""SQLAlchemy models for SRAG database."""

from sqlalchemy import Boolean, Column, Date, Index, Integer, SmallInteger, String
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """SQLAlchemy declarative base class for SRAG database models."""

    pass


class SragCase(Base):
    """ORM model representing a SRAG case record.

    Maps to the ``srag.srag_cases`` table and stores notification dates,
    evolution, ICU admission, vaccination, and demographic fields.
    """

    __tablename__ = "srag_cases"
    __table_args__ = (
        Index("ix_srag_cases_dt_notific_caso_confirmado", "dt_notific", "caso_confirmado"),
        {"schema": "srag"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    dt_notific = Column(Date, index=True)
    dt_sin_pri = Column(Date)
    dt_interna = Column(Date)
    evolucao = Column(SmallInteger)
    evolucao_label = Column(String(30))
    dt_evoluca = Column(Date)
    uti = Column(SmallInteger)
    dt_entuti = Column(Date)
    dt_saiduti = Column(Date)
    vacina_cov = Column(SmallInteger)
    dose_1_cov = Column(Date)
    dose_2_cov = Column(Date)
    nu_idade_n = Column(SmallInteger)
    cs_sexo = Column(String(1))
    sg_uf_not = Column(String(2), index=True)
    classi_fin = Column(SmallInteger)
    caso_confirmado = Column(Boolean, index=True)
    sem_not = Column(SmallInteger)
    ano_notificacao = Column(SmallInteger, index=True)
