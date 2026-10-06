"""Router de utilidades para el Simulador de VELUM.

Provee endpoints para gestionar y restablecer datos de las cuentas de prueba:
- POST /api/simulator/reset
- GET /api/simulator/users
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.detector import detector
from app.models import Anomalia, EstadoUsuario, Transaccion, Usuario

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/simulator", tags=["simulator"])

SIMULATION_EMAILS = ["b@b.com", "c@c.com", "aa@aa.com", "test@test.com"]


@router.post(
    "/reset",
    summary="Limpiar transacciones y anomalías de los usuarios de prueba o todo",
)
def reset_simulation_data(all_data: bool = True, db: Session = Depends(get_db)):
    """Elimina transacciones y anomalías generadas y vacía sus ventanas en memoria en el detector."""
    try:
        if all_data:
            db.query(Anomalia).delete(synchronize_session=False)
            db.query(Transaccion).delete(synchronize_session=False)
            db.commit()
            detector.reset_all()
            msg = "Todas las transacciones, anomalías y ventanas en memoria fueron eliminadas con éxito"
        else:
            users = db.query(Usuario).filter(Usuario.email.in_(SIMULATION_EMAILS)).all()
            user_ids = [u.id for u in users]

            if user_ids:
                txns = db.query(Transaccion).filter(Transaccion.usuario_id.in_(user_ids)).all()
                txn_ids = [t.id for t in txns]

                if txn_ids:
                    db.query(Anomalia).filter(Anomalia.transaccion_id.in_(txn_ids)).delete(synchronize_session=False)
                    db.query(Transaccion).filter(Transaccion.id.in_(txn_ids)).delete(synchronize_session=False)

                db.commit()

            # Limpiar ventanas en memoria del detector
            for email in SIMULATION_EMAILS:
                detector.reset_user(email)
            msg = "Datos de simulación y ventanas en memoria restablecidos con éxito"

        return {
            "success": True,
            "message": msg,
        }
    except Exception as exc:
        db.rollback()
        logger.error("Error al reiniciar datos de simulación: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "error": {"code": "RESET_FAILED", "message": str(exc)}},
        )


SIMULATION_EMAILS = ("b@b.com", "c@c.com", "aa@aa.com")


@router.get(
    "/users",
    summary="Obtener IDs y detalles de los usuarios de simulación y activos",
)
def get_simulation_users(db: Session = Depends(get_db)):
    """Retorna los usuarios registrados garantizando cuentas académicas en O(1) queries."""
    try:
        # 1. Consulta única en O(1) para verificar qué emails ya existen
        existing = {
            r[0] for r in db.query(Usuario.email).filter(Usuario.email.in_(SIMULATION_EMAILS)).all()
        }

        # 2. Inserción masiva segura solo de los faltantes
        new_users = [
            Usuario(email=em, nombre=em.split("@")[0], estado=EstadoUsuario.ACTIVO)
            for em in SIMULATION_EMAILS
            if em not in existing
        ]
        if new_users:
            db.add_all(new_users)
            db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("Auto-aprovisionamiento de usuarios omitido por concurrencia: %s", exc)

    # 3. Retorno ordenado
    users = db.query(Usuario).order_by(Usuario.id.asc()).all()
    return {
        "success": True,
        "users": [
            {
                "id": u.id,
                "email": u.email,
                "nombre": u.nombre,
                "estado": u.estado.value if hasattr(u.estado, "value") else str(u.estado),
            }
            for u in users
        ],
    }


@router.get(
    "/hash-vectors",
    summary="Obtener vectores oficiales de prueba para autotest del frontend",
)
def get_hash_vectors():
    """Retorna los vectores de tests/hash_vectors.json para autoverificación con WebCrypto."""
    from app.services.hash_service import load_test_vectors
    return {
        "success": True,
        "vectors": load_test_vectors(),
    }
