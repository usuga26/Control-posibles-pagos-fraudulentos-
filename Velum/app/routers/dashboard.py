"""Router del Dashboard de VELUM.

Endpoints:
- GET /api/dashboard/stats?periodo=hoy|semana|mes
- GET /api/dashboard/timeline-sliding-window/{usuario_id}
"""
from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Usuario, Transaccion, Anomalia
from app.detector import detector
from app.schemas import DashboardStatsResponse, ErrorResponse, TimelineResponse
from app.services.dashboard_service import get_dashboard_stats, get_timeline, get_users_directory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get(
    "/stats",
    response_model=DashboardStatsResponse,
    responses={
        500: {"model": ErrorResponse},
    },
    summary="Obtener estadísticas consolidadas del dashboard",
)
def get_stats(
    periodo: Literal["hoy", "semana", "mes", "todo", "todos"] = Query(
        default="hoy",
        description="Periodo de consulta: hoy, semana, mes o todo",
    ),
    db: Session = Depends(get_db),
):
    """Retorna métricas consolidadas del sistema para el periodo especificado:

    - Totales por estado (Aprobadas, Sospechosas, Rechazadas)
    - Resumen de anomalías (% del total, monto en riesgo, recurrentes)
    - Distribución por nivel de severidad y estado de revisión
    - Actividad transaccional y anomalías por hora del día
    - Detección de hora pico y tendencia porcentual vs periodo previo
    - Distribución por método de pago
    """
    try:
        return get_dashboard_stats(db, periodo=periodo)
    except Exception as exc:
        logger.error("Error al calcular estadísticas del dashboard: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "error": {"code": "INTERNAL_ERROR", "message": str(exc)}},
        )


@router.get(
    "/timeline-sliding-window/{identifier}",
    response_model=TimelineResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Usuario no encontrado"},
        500: {"model": ErrorResponse},
    },
    summary="Visualización cronológica de ventana deslizante por usuario (ID o Email)",
)
def get_user_timeline(
    identifier: str,
    db: Session = Depends(get_db),
):
    """Construye la serie de tiempo para un usuario especificado por su ID o Email."""
    usuario = None
    if identifier.isdigit():
        usuario = db.get(Usuario, int(identifier))
    if not usuario:
        usuario = db.query(Usuario).filter(Usuario.email == identifier.strip().lower()).first()

    # Si no existe aún y es email, auto-crear usuario para la ventana
    if not usuario and ("@" in identifier):
        from app.models import EstadoUsuario
        usuario = Usuario(
            email=identifier.strip().lower(),
            nombre=identifier.split("@")[0],
            estado=EstadoUsuario.ACTIVO,
        )
        db.add(usuario)
        db.commit()
        db.refresh(usuario)

    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "success": False,
                "error": {
                    "code": "USER_NOT_FOUND",
                    "message": f"Usuario {identifier} no encontrado",
                },
            },
        )

    try:
        timeline = get_timeline(db, usuario_id=usuario.id)
        return timeline
    except Exception as exc:
        logger.error("Error al obtener timeline para usuario %s: %s", identifier, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "error": {"code": "INTERNAL_ERROR", "message": str(exc)}},
        )


@router.get(
    "/users-directory",
    summary="Obtener directorio de usuarios con metricas adaptadas al periodo",
)
def get_directory(
    periodo: str = Query(default="todos", description="Filtro de periodo: hoy, semana, mes o todos"),
    db: Session = Depends(get_db),
):
    """Retorna la lista de usuarios con metricas de volumen, anomalias y riesgo adaptadas al periodo."""
    try:
        users = get_users_directory(db, periodo=periodo)
        return {"success": True, "periodo": periodo, "users": users}
    except Exception as exc:
        logger.error("Error al obtener directorio de usuarios: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "error": {"code": "INTERNAL_ERROR", "message": str(exc)}},
        )


@router.post(
    "/reset",
    summary="Limpiar base de datos y memoria",
)
def reset_data(db: Session = Depends(get_db)):
    """Elimina todas las transacciones, anomalías y vacía el detector en memoria."""
    try:
        db.query(Anomalia).delete(synchronize_session=False)
        db.query(Transaccion).delete(synchronize_session=False)
        db.query(Usuario).delete(synchronize_session=False)
        db.commit()
        detector.reset_all()
        return {
            "success": True,
            "message": "Todas las transacciones, anomalías y ventanas en memoria fueron eliminadas con éxito",
        }
    except Exception as exc:
        db.rollback()
        logger.error("Error reseteando datos: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"success": False, "error": {"code": "INTERNAL_ERROR", "message": str(exc)}},
        )

