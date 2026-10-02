"""Esquemas Pydantic v2 para VELUM.

Separación clara entre esquemas de entrada (request) y salida (response).
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

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

PAYMENT_METHODS = {"Tarjeta", "PSE", "Transferencia", "Otro"}


class TransaccionRequest(BaseModel):
    """Payload de entrada para crear una transacción."""

    id_txn: str = Field(alias="idTxn", min_length=1, max_length=64)
    user: EmailStr
    date: str = Field(
        description="Formato YYYY-MM-DDTHH:MM:SS.mmm (milisegundos exactos, sin zona horaria)"
    )
    value: Decimal = Field(gt=0, decimal_places=2)
    payment_method: str = Field(alias="paymentMethod")
    hash: str = Field(min_length=64, max_length=64)

    model_config = {"populate_by_name": True}

    @model_validator(mode="before")
    @classmethod
    def normalize_aliases(cls, data: Any) -> Any:
        """Mapea en O(1) nombres de campos comunes en español, inglés o snake_case."""
        if isinstance(data, dict):
            mapping = {
                "id": "idTxn",
                "id_txn": "idTxn",
                "idTransaction": "idTxn",
                "id_transaccion": "idTxn",
                "email": "user",
                "usuario": "user",
                "client": "user",
                "cliente": "user",
                "fecha": "date",
                "timestamp": "date",
                "datetime": "date",
                "valor": "value",
                "monto": "value",
                "amount": "value",
                "payment_method": "paymentMethod",
                "metodo_pago": "paymentMethod",
                "metodopago": "paymentMethod",
                "metodoPago": "paymentMethod",
                "sha256": "hash",
                "signature": "hash",
                "token": "hash",
            }
            d = dict(data)
            for k_old, k_new in mapping.items():
                if k_old in d and k_new not in d:
                    d[k_new] = d.pop(k_old)
            return d
        return data

    @field_validator("date", mode="before")
    @classmethod
    def validate_date_format(cls, v: Any) -> str:
        """Valida y normaliza date a formato YYYY-MM-DDTHH:MM:SS.mmm."""
        if not isinstance(v, str):
            v = str(v)
        v = v.strip().replace(" ", "T").rstrip("Z")
        # Si no tiene milisegundos o tiene microsegundos, normalizar a exactamente 3 dígitos
        if "." not in v:
            v = f"{v}.000"
        else:
            base, ms = v.split(".", 1)
            ms = (ms + "000")[:3]
            v = f"{base}.{ms}"

        try:
            datetime.strptime(v, "%Y-%m-%dT%H:%M:%S.%f")
        except ValueError as exc:
            raise ValueError(
                "El campo 'date' debe tener formato YYYY-MM-DDTHH:MM:SS.mmm "
                "(e.g. 2026-09-23T10:30:01.120)"
            ) from exc
        return v

    @field_validator("payment_method", mode="before")
    @classmethod
    def validate_payment_method(cls, v: Any) -> str:
        """Valida y normaliza paymentMethod de forma flexible e insensible a mayúsculas."""
        if not isinstance(v, str):
            v = str(v)
        norm_map = {
            "tarjeta": "Tarjeta",
            "pse": "PSE",
            "transferencia": "Transferencia",
            "otro": "Otro",
        }
        v_clean = norm_map.get(v.strip().lower(), v.strip())
        if v_clean not in PAYMENT_METHODS:
            raise ValueError(
                f"paymentMethod debe ser uno de: {', '.join(sorted(PAYMENT_METHODS))}"
            )
        return v_clean

    @field_validator("hash", mode="before")
    @classmethod
    def validate_hash_format(cls, v: Any) -> str:
        """Valida que hash sea hex lowercase de 64 caracteres."""
        if not isinstance(v, str):
            v = str(v)
        v = v.strip().lower()
        if len(v) != 64 or not all(c in "0123456789abcdef" for c in v):
            raise ValueError("El hash debe ser hexadecimal en minúsculas de 64 caracteres")
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
    id_txn: str = Field(alias="idTxn")
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
