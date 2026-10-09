"""Esquemas Pydantic v2 para VELUM.

Validación estricta: datos inválidos se rechazan, nunca se fabrican.
Separación clara entre esquemas de entrada (request) y salida (response).
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models import (
    EstadoRevision,
    EstadoTransaccion,
    EstadoUsuario,
    MetodoPago,
    NivelAnomalia,
    TipoAnomalia,
)

# ---------------------------------------------------------------------------
# Esquemas de Request
# ---------------------------------------------------------------------------


class TransaccionRequest(BaseModel):
    """Payload de entrada para crear una transacción.

    Validación estricta sin sanitización:
    - Si un campo falta o tiene tipo incorrecto → 422
    - Sin aliases, sin normalización, sin valores por defecto inventados
    """

    id_txn: int = Field(alias="idTxn", ge=0)
    user: EmailStr
    date: str
    value: int | float = Field(ge=0)
    payment_method: str = Field(alias="paymentMethod", min_length=2)
    hash: str = Field(min_length=50)

    model_config = {"populate_by_name": True}

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        """Valida que date sea parseable como fecha ISO."""
        try:
            clean = v.replace("Z", "+00:00") if v.endswith("Z") else v
            datetime.fromisoformat(clean)
        except (ValueError, TypeError) as exc:
            raise ValueError(
                "El campo 'date' debe ser una fecha ISO válida "
                "(e.g. 2026-09-23T10:30:01.120)"
            ) from exc
        return v


# ---------------------------------------------------------------------------
# Esquemas de Response
# ---------------------------------------------------------------------------


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    success: bool = False
    error: ErrorDetail


class TransaccionInfo(BaseModel):
    id: int
    id_txn: int = Field(alias="idTxn")
    status: str

    model_config = {"populate_by_name": True}


class AnalysisInfo(BaseModel):
    anomaly_detected: bool = Field(alias="anomalyDetected")
    type: str | None = None
    severity: str | None = None
    transaction_count: int | None = Field(default=None, alias="transactionCount")
    window_seconds: int | None = Field(default=None, alias="windowSeconds")

    model_config = {"populate_by_name": True}


class TransaccionResponse(BaseModel):
    success: bool = True
    duplicate: bool = False
    transaction: TransaccionInfo
    analysis: AnalysisInfo


# ---------------------------------------------------------------------------
# Esquemas de Dashboard
# ---------------------------------------------------------------------------


class ByStatusStats(BaseModel):
    aprobadas: int = 0
    sospechosas: int = 0
    rechazadas: int = 0
    total: int = 0


class AnomaliaStats(BaseModel):
    total: int = 0
    porcentaje: float = 0.0
    monto_sospechoso: str = "0.00"
    usuarios_afectados: int = 0
    recurrentes: int = 0


class BySeverityStats(BaseModel):
    bajo: int = 0
    medio: int = 0
    alto: int = 0
    critico: int = 0


class ByRevisionStats(BaseModel):
    nueva: int = 0
    abierta: int = 0
    revisada: int = 0
    descartada: int = 0


class HourlyPoint(BaseModel):
    hora: int
    transacciones: int = 0
    anomalias: int = 0


class PaymentMethodStats(BaseModel):
    tarjeta: int = 0
    pse: int = 0
    transferencia: int = 0
    otro: int = 0


class DashboardStatsResponse(BaseModel):
    periodo: str
    by_status: ByStatusStats
    anomalias: AnomaliaStats
    by_severity: BySeverityStats
    by_revision: ByRevisionStats
    by_hour: list[HourlyPoint]
    pico_hora: int | None = None
    tendencia: float | None = None
    by_payment_method: PaymentMethodStats
    promedio_txns_usuario: float = 0.0


# ---------------------------------------------------------------------------
# Esquemas de Timeline (Ventana Deslizante)
# ---------------------------------------------------------------------------


class TimelineEntry(BaseModel):
    timestamp: str
    id_txn: str = Field(alias="idTxn")
    valor: str
    estado: str
    en_ventana: bool = Field(alias="enVentana")
    ventana_inicio: str | None = Field(default=None, alias="ventanaInicio")
    ventana_fin: str | None = Field(default=None, alias="ventanaFin")
    conteo_ventana: int = Field(alias="conteoVentana")
    severidad: str | None = None
    regla_detectada: str | None = Field(default=None, alias="reglaDetectada")

    model_config = {"populate_by_name": True}


class TimelineResponse(BaseModel):
    usuario_id: int
    email: str
    entries: list[TimelineEntry]
