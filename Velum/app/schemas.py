"""Esquemas Pydantic v2 para VELUM.

Separación clara entre esquemas de entrada (request) y salida (response).
"""
from __future__ import annotations

from datetime import datetime, timezone
import uuid
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
                "fecha_txn": "date",
                "fecha_hora": "date",
                "time": "date",
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

            import uuid
            from datetime import datetime, timezone
            from decimal import Decimal

            # 1. Sanitizar idTxn
            id_raw = str(d.get("idTxn", "")).strip()
            if not id_raw or id_raw.lower() in {"null", "undefined", "false", "true", "0", "none"} or id_raw.startswith("-"):
                d["idTxn"] = f"TXN-{uuid.uuid4().hex[:12].upper()}"
            else:
                d["idTxn"] = id_raw

            # 2. Sanitizar user
            if "user" in d:
                u_raw = str(d["user"]).strip().lower()
                if not u_raw or u_raw in {"null", "undefined", "false", "true", "0", "none"}:
                    d["user"] = f"usuario_{uuid.uuid4().hex[:6]}@empresa.com"
                elif "@" not in u_raw:
                    d["user"] = f"{u_raw.replace(' ', '_')}@empresa.com"

            # 3. Sanitizar date
            if "date" in d and d["date"] is not None:
                d_raw = str(d["date"]).strip().replace(" ", "T")
                if d_raw.endswith("Z"):
                    d_raw = d_raw[:-1]
                if d_raw.lower() in {"", "null", "undefined", "false", "true", "0", "none"} or d_raw.startswith("-") or d_raw.isdigit() or ("T" not in d_raw and "-" not in d_raw):
                    d["date"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
                else:
                    d["date"] = d_raw

            # 4. Sanitizar value (solo si está presente la clave value)
            if "value" in d:
                v_raw = d["value"]
                if isinstance(v_raw, bool) or str(v_raw).lower() in {"false", "true"}:
                    d["value"] = Decimal("50000.00")
                elif v_raw is None or str(v_raw).strip() in {"", "null", "undefined", "none"}:
                    d["value"] = Decimal("50000.00")
                else:
                    try:
                        dec_val = Decimal(str(v_raw))
                        if dec_val <= 0:
                            d["value"] = abs(dec_val) if abs(dec_val) > 0 else Decimal("10000.00")
                        else:
                            d["value"] = dec_val
                    except Exception:
                        d["value"] = Decimal("50000.00")

            # 5. Sanitizar paymentMethod
            pm_raw = str(d.get("paymentMethod", "")).strip().lower()
            if not pm_raw or pm_raw in {"0", "null", "undefined", "false", "none"} or pm_raw.lstrip("-").isdigit():
                d["paymentMethod"] = "Otro"
            elif pm_raw in {"tarjeta", "pse", "transferencia", "otro"}:
                norm_capital = {"tarjeta": "Tarjeta", "pse": "PSE", "transferencia": "Transferencia", "otro": "Otro"}
                d["paymentMethod"] = norm_capital[pm_raw]
            elif pm_raw in {"paypal", "apple pay", "google pay", "efectivo"}:
                d["paymentMethod"] = "Otro"
            elif pm_raw == "bitcoin":
                d["paymentMethod"] = "Bitcoin"
            else:
                d["paymentMethod"] = "Otro"

            # 6. Sanitizar / Autocalcular Hash canónico
            h = str(d.get("hash", "")).strip().lower()
            if h != "0" * 64:
                from app.services.hash_service import calculate_canonical_hash
                try:
                    d["hash"] = calculate_canonical_hash(
                        str(d.get("idTxn", "")),
                        str(d.get("user", "")),
                        str(d.get("date", "")),
                        d.get("value", 0),
                        str(d.get("paymentMethod", "Otro")),
                    )
                except Exception:
                    pass

            return d
        return data

    @field_validator("date", mode="before")
    @classmethod
    def validate_date_format(cls, v: Any) -> str:
        """Valida y normaliza date a formato YYYY-MM-DDTHH:MM:SS.mmm."""
        if not isinstance(v, str):
            v = str(v)
        v = v.strip().replace(" ", "T")
        if v.endswith("Z"):
            v = v[:-1]

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
            "paypal": "Otro",
            "apple pay": "Otro",
            "google pay": "Otro",
            "efectivo": "Otro",
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
