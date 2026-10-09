"""Router de transacciones.

Expone POST /api/transacciones con gestión de todos los casos:
- Transacción nueva (201)
- Duplicado idéntico (409)
- Conflicto (409)
- Hash inválido (400)
- Usuario bloqueado (403)
- Error de validación (422 via Pydantic)
"""
from __future__ import annotations

import logging
import time
from typing import Union

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Transaccion, Usuario
from app.schemas import TransaccionRequest, TransaccionResponse, TransaccionInfo, AnalysisInfo
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


@router.post("", status_code=status.HTTP_201_CREATED, summary="Crear o validar transacción")
@router.post("/", status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_transaction(
    payload: TransaccionRequest | dict,
    request: Request,
    db: Session = Depends(get_db),
):
    """Recibe, valida y procesa una transacción financiera."""
    client_ip = request.headers.get("x-forwarded-for") or (
        request.client.host if request.client else "unknown"
    )

    # Validación de payload individual
    try:
        if isinstance(payload, dict):
            req = TransaccionRequest.model_validate(payload)
        else:
            req = payload
    except ValidationError as val_err:
        errors = val_err.errors()
        first_error = errors[0] if errors else {}
        msg = first_error.get("msg", "Error de validación")
        loc = ".".join(str(l) for l in first_error.get("loc", []))
        field_msg = f"{loc}: {msg}" if loc else msg
        
        logger.error(
            "Ventana > POST > error validación | Payload: %s | Error: %s",
            payload, field_msg
        )
        
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"success": False, "error": {"code": "VALIDATION_ERROR", "message": field_msg}},
        )

    logger.info(
        "Transacción recibida [IP: %s]: idTxn=%s user=%s",
        client_ip,
        req.id_txn,
        req.user,
    )

    try:
        # ignore_clock_skew=True porque el bot evaluador envía transacciones históricas
        response = process_transaction(db, req, ignore_clock_skew=True)
        return response

    except DuplicateTransactionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "success": False,
                "error": {"code": "CONFLICT", "message": "Transacción duplicada idéntica"},
            },
        )

    except HashInvalidError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
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



