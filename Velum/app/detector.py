"""Detector de ventana deslizante (Sliding Window) para fraude en tiempo real.

Algoritmo:
1. Mantiene un deque por usuario con timestamps UNIX Epoch absolutos.
2. Ante cada nueva transacción, purga los timestamps fuera de [t - WINDOW_SECONDS, t].
3. Si el conteo después de la purga >= BASE_TRANSACTION_THRESHOLD → POSIBLE_FRAUDE.
4. La severidad se calcula con `calculate_severity` según la franja horaria.
5. Threading: un Lock por usuario garantiza consistencia en acceso concurrente.

Complejidad Espacial: O(K) estricta, garantizada por el uso de `collections.deque` con `maxlen` 
y consultas limitadas a la ventana de tiempo. K representa el máximo de transacciones en ventana.
"""
from __future__ import annotations

import logging
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Callable, NamedTuple

from app.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tipos y resultados
# ---------------------------------------------------------------------------

class DetectionResult(NamedTuple):
    """Resultado del análisis de una transacción."""
    anomaly_detected: bool
    transaction_count: int
    severity: str | None
    window_start: datetime | None
    window_end: datetime | None
    window_seconds: int


# ---------------------------------------------------------------------------
# Cálculo de severidad
# ---------------------------------------------------------------------------

def get_time_slot_reference(dt_bogota: datetime) -> tuple[str, int]:
    """Determina la franja horaria y su referencia de transacciones."""
    hour = dt_bogota.hour
    if 5 <= hour < 12:
        return "mañana", settings.ref_morning
    elif 12 <= hour < 20:
        return "tarde", settings.ref_afternoon
    else:
        return "noche", settings.ref_night


def calculate_severity(count: int, reference: int) -> str:
    """Calcula la severidad de una anomalía en O(1)."""
    ratio = count / reference
    if ratio < settings.severity_low:
        return "BAJO"
    elif ratio < settings.severity_medium:
        return "MEDIO"
    elif ratio < settings.severity_high:
        return "ALTO"
    else:
        return "CRITICO"


# ---------------------------------------------------------------------------
# Detector de ventana deslizante
# ---------------------------------------------------------------------------

class SlidingWindowDetector:
    """Detecta ráfagas sospechosas usando una ventana deslizante O(K)."""

    def __init__(
        self,
        window_seconds: int | None = None,
        threshold: int | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.window_seconds = window_seconds or settings.window_seconds
        self.threshold = threshold or settings.base_transaction_threshold
        self.clock: Callable[[], datetime] = clock or (lambda: datetime.now(timezone.utc))

        # O(K) Límite espacial máximo de seguridad
        self.MAX_K = 10000

        # Deques de timestamps UNIX Epoch por usuario: {user_email: deque[float]}
        self._windows: dict[str, deque[float]] = {}
        self._user_locks: dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()

    def _get_user_lock(self, user: str) -> threading.Lock:
        """Obtiene o crea el Lock para un usuario dado en O(1)."""
        if user not in self._user_locks:
            with self._global_lock:
                if user not in self._user_locks:
                    self._user_locks[user] = threading.Lock()
                    # Se garantiza complejidad O(K) restringiendo el crecimiento del deque
                    self._windows[user] = deque(maxlen=self.MAX_K)
        return self._user_locks[user]

    def _purge_old(self, user: str, now_epoch: float, current_window_seconds: int) -> None:
        """Elimina timestamps fuera de la ventana en O(1) amortizado."""
        window_start = now_epoch - current_window_seconds
        dq = self._windows[user]
        while dq and dq[0] < window_start:
            dq.popleft()

    def process(self, user: str, received_at: datetime) -> DetectionResult:
        """Procesa una transacción mediante flotantes absolutos UNIX Epoch."""
        now_epoch = received_at.timestamp()
        
        try:
            import zoneinfo
            bogota_tz = zoneinfo.ZoneInfo(settings.timezone)
        except Exception:
            from datetime import timezone as tz, timedelta
            bogota_tz = tz(timedelta(hours=-5))

        dt_bogota = received_at.astimezone(bogota_tz)
        slot_name, reference = get_time_slot_reference(dt_bogota)
        current_window_seconds = self.window_seconds
        
        try:
            lock = self._get_user_lock(user)
            with lock:
                self._purge_old(user, now_epoch, current_window_seconds)
                self._windows[user].append(now_epoch)
                count = len(self._windows[user])
                window_start_epoch = self._windows[user][0] if self._windows[user] else now_epoch

            anomaly_detected = count >= self.threshold

            if not anomaly_detected:
                return DetectionResult(
                    anomaly_detected=False,
                    transaction_count=count,
                    severity=None,
                    window_start=None,
                    window_end=None,
                    window_seconds=current_window_seconds,
                )

            severity = calculate_severity(count, reference)

            # Observabilidad Avanzada
            logger.warning(
                "Fraude detectado: User %s, Hora Epoch %f, Nivel %s, Conteo %d, Ventana %ds", 
                user, now_epoch, severity, count, current_window_seconds
            )

            dt_window_start = datetime.fromtimestamp(window_start_epoch, tz=timezone.utc)
            dt_window_end = datetime.fromtimestamp(now_epoch, tz=timezone.utc)

            return DetectionResult(
                anomaly_detected=True,
                transaction_count=count,
                severity=severity,
                window_start=dt_window_start,
                window_end=dt_window_end,
                window_seconds=current_window_seconds,
            )
        except Exception as e:
            logger.error("Error crítico en detector: User %s, Hora Epoch %f, Error: %s", user, now_epoch, str(e))
            raise

    def rebuild_from_history(self, user: str, timestamps: list[datetime]) -> None:
        """Reconstruye la ventana aplicando límites espaciales O(K)."""
        lock = self._get_user_lock(user)
        now = self.clock()
        now_epoch = now.timestamp()
        
        current_window_seconds = self.window_seconds
        window_start_epoch = now_epoch - current_window_seconds

        # Aplicar el límite O(K) de forma estricta cortando los últimos K elementos
        timestamps = timestamps[-self.MAX_K:] if len(timestamps) > self.MAX_K else timestamps

        norm_ts = []
        for ts in timestamps:
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            ts_epoch = ts.timestamp()
            if ts_epoch >= window_start_epoch:
                norm_ts.append(ts_epoch)

        with lock:
            self._windows[user] = deque(sorted(norm_ts), maxlen=self.MAX_K)

    def get_window_snapshot(self, user: str) -> list[float]:
        """Retorna copia inmutable de los timestamps Epoch en la ventana."""
        lock = self._get_user_lock(user)
        with lock:
            return list(self._windows.get(user, deque()))

    def reset_user(self, user: str) -> None:
        """Limpia la ventana de un usuario."""
        lock = self._get_user_lock(user)
        with lock:
            if user in self._windows:
                self._windows[user].clear()

    def reset_all(self) -> None:
        """Limpia todas las ventanas de todos los usuarios en memoria."""
        with self._global_lock:
            self._windows.clear()
            self._user_locks.clear()

# Instancia global del detector (singleton)
detector = SlidingWindowDetector()

