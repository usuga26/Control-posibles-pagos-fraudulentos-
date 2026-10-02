"""Router de transacciones.

Expone POST /api/transacciones con gestión de todos los casos:
- Transacción nueva (201)
- Duplicado idéntico (200)
- Conflicto (409)
- Hash inválido (400)
- Usuario bloqueado (403)
- Error de validación (422 via Pydantic)
"""
from __future__ import annotations

import csv
import io
import json
import logging
import time
from typing import Union

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import EstadoTransaccion, Transaccion
from app.schemas import (
    AnalysisInfo,
    ErrorDetail,
    ErrorResponse,
    TransaccionInfo,
    TransaccionRequest,
    TransaccionResponse,
)
from app.services.transaction_service import (
    ClockSkewError,
    ConflictTransactionError,
    DuplicateTransactionError,
    HashInvalidError,
    UserBlockedError,
    process_transaction,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/transacciones", tags=["transacciones"])
v1_router = APIRouter(prefix="/api/v1/transactions", tags=["transacciones-v1"])


def process_batch_internal(
    items: list[dict | TransaccionRequest],
    db: Session,
    ignore_clock_skew: bool = True,
) -> dict:
    """Procesa una secuencia masiva de transacciones en O(N) total con O(1) amortizado por registro."""
    t_start = time.perf_counter()
    total = len(items)
    approved = 0
    suspicious = 0
    rejected = 0
    anomalies_count = 0
    errors: list[dict] = []

    for idx, item in enumerate(items):
        try:
            if isinstance(item, TransaccionRequest):
                req = item
            else:
                req = TransaccionRequest.model_validate(item)

            res = process_transaction(db, req, ignore_clock_skew=ignore_clock_skew)
            st = res.transaction.status
            if st == EstadoTransaccion.APROBADA.value:
                approved += 1
            elif st == EstadoTransaccion.SOSPECHOSA.value:
                suspicious += 1
            else:
                rejected += 1

            if res.analysis and res.analysis.anomaly_detected:
                anomalies_count += 1

        except DuplicateTransactionError:
            approved += 1
        except (UserBlockedError, HashInvalidError, ConflictTransactionError, ClockSkewError) as exc:
            rejected += 1
            if len(errors) < 20:
                errors.append({"index": idx, "error": str(exc)})
        except Exception as exc:
            rejected += 1
            if len(errors) < 20:
                errors.append({"index": idx, "error": str(exc)})

    elapsed = round(time.perf_counter() - t_start, 3)
    throughput = round(total / elapsed, 1) if elapsed > 0 else float(total)

    return {
        "success": True,
        "total_processed": total,
        "approved": approved,
        "suspicious": suspicious,
        "rejected": rejected,
        "anomalies_detected": anomalies_count,
        "elapsed_seconds": elapsed,
        "throughput_txns_per_sec": throughput,
        "sample_errors": errors,
    }


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Crear o validar una transacción (individual o lote)",
)
@v1_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Crear o validar una transacción (individual o lote v1)",
)
def create_transaction(
    payload: Union[TransaccionRequest, list[TransaccionRequest]],
    request: Request,
    db: Session = Depends(get_db),
):
    """Recibe, valida y procesa transacciones financieras (individual o lote)."""
    client_ip = request.headers.get("x-forwarded-for") or (
        request.client.host if request.client else "unknown"
    )

    if isinstance(payload, list):
        logger.info(
            "Lote recibido en endpoint principal [IP: %s]: %d transacciones",
            client_ip,
            len(payload),
        )
        return process_batch_internal(payload, db, ignore_clock_skew=True)

    logger.info(
        "Transacción recibida [IP: %s]: idTxn=%s user=%s",
        client_ip,
        payload.id_txn,
        payload.user,
    )

    try:
        response = process_transaction(db, payload)
        return response

    except DuplicateTransactionError as exc:
        txn = exc.txn
        # Construir análisis vacío (no tocamos la ventana en duplicados)
        analysis = AnalysisInfo(
            anomalyDetected=False,
            type=None,
            severity=None,
            transactionCount=None,
            windowSeconds=None,
        )
        duplicate_response = TransaccionResponse(
            success=True,
            duplicate=True,
            transaction=TransaccionInfo(
                id=txn.id,
                idTxn=txn.id_txn,
                status=txn.estado.value,
            ),
            analysis=analysis,
        )
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=duplicate_response.model_dump(by_alias=True),
        )

    except HashInvalidError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"success": False, "error": {"code": "HASH_INVALID", "message": str(exc)}},
        )

    except ClockSkewError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"success": False, "error": {"code": "CLOCK_SKEW", "message": str(exc)}},
        )

    except UserBlockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "success": False,
                "error": {
                    "code": f"USER_{exc.estado}",
                    "message": f"Usuario {exc.estado}: transacción rechazada",
                },
            },
        )

    except ConflictTransactionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "success": False,
                "error": {"code": "CONFLICT", "message": str(exc)},
            },
        )

    except Exception as exc:
        logger.error("Error interno procesando transacción: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {"code": "INTERNAL_ERROR", "message": "Error interno del servidor"},
            },
        )


@router.post("/batch", status_code=status.HTTP_200_OK, summary="Procesar lote masivo de transacciones (JSON)")
@v1_router.post("/batch", status_code=status.HTTP_200_OK, summary="Procesar lote masivo de transacciones (JSON v1)")
def process_batch(
    payload: list[TransaccionRequest],
    request: Request,
    ignore_clock_skew: bool = Query(True, description="Si es True, admite datasets históricos"),
    db: Session = Depends(get_db),
):
    """Recibe un array JSON masivo de transacciones y las evalúa en streaming en memoria."""
    client_ip = request.headers.get("x-forwarded-for") or (
        request.client.host if request.client else "unknown"
    )
    logger.info("Lote masivo recibido [IP: %s]: %d transacciones", client_ip, len(payload))
    return process_batch_internal(payload, db, ignore_clock_skew=ignore_clock_skew)


@router.post("/upload", status_code=status.HTTP_200_OK, summary="Carga de archivo pesado de transacciones (.json o .csv)")
@v1_router.post("/upload", status_code=status.HTTP_200_OK, summary="Carga de archivo pesado de transacciones (.json o .csv v1)")
async def upload_transactions_file(
    request: Request,
    file: UploadFile = File(..., description="Archivo pesado en formato .json o .csv"),
    ignore_clock_skew: bool = Query(True, description="Si es True, omite el desfase de reloj para datasets de prueba"),
    db: Session = Depends(get_db),
):
    """Procesa un archivo pesado (.json o .csv) enviado mediante multipart/form-data."""
    filename = file.filename or "unknown"
    client_ip = request.headers.get("x-forwarded-for") or (
        request.client.host if request.client else "unknown"
    )
    logger.info("Archivo pesado recibido [IP: %s]: filename=%s", client_ip, filename)

    contents = await file.read()
    if not contents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"success": False, "error": {"code": "EMPTY_FILE", "message": "El archivo está vacío"}},
        )

    text = contents.decode("utf-8-sig", errors="replace")
    items: list[dict] = []

    stripped_text = text.strip()
    is_json = (
        filename.lower().endswith(".json")
        or stripped_text.startswith("[")
        or stripped_text.startswith("{")
    )

    if is_json:
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                items = parsed
            elif isinstance(parsed, dict) and "transactions" in parsed:
                items = parsed["transactions"]
            else:
                items = [parsed]
        except json.JSONDecodeError:
            # Fallback a JSON Lines (NDJSON)
            items = []
            for line in text.splitlines():
                line = line.strip()
                if line:
                    try:
                        items.append(json.loads(line))
                    except Exception:
                        continue
    else:
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            norm_row = {}
            for k, v in row.items():
                if not k or v is None:
                    continue
                k_clean = k.strip()
                k_lower = k_clean.lower()
                if k_lower in ("idtxn", "id_txn", "id"):
                    norm_row["idTxn"] = v.strip()
                elif k_lower in ("user", "usuario", "email"):
                    norm_row["user"] = v.strip()
                elif k_lower in ("date", "fecha", "timestamp"):
                    norm_row["date"] = v.strip()
                elif k_lower in ("value", "valor", "monto"):
                    try:
                        norm_row["value"] = float(v.strip())
                    except ValueError:
                        norm_row["value"] = v.strip()
                elif k_lower in ("paymentmethod", "payment_method", "metodo_pago", "metodopago"):
                    norm_row["paymentMethod"] = v.strip()
                elif k_lower in ("hash", "sha256", "firma"):
                    norm_row["hash"] = v.strip()
                else:
                    norm_row[k_clean] = v.strip()
            if norm_row:
                items.append(norm_row)

    if not items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "error": {
                    "code": "NO_TRANSACTIONS_FOUND",
                    "message": "No se encontraron transacciones legibles en el archivo (se espera .json o .csv con encabezados válidos)",
                },
            },
        )

    result = process_batch_internal(items, db, ignore_clock_skew=ignore_clock_skew)
    result["filename"] = filename
    return result
