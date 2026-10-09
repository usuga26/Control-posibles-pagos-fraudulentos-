"""Servicio de hash HMAC-SHA256 para validación de integridad de transacciones.

Reproduce exactamente el cálculo del evaluador en JS:
    crypto.createHmac("sha256", LLAVE_SECRETA)
        .update(JSON.stringify(dataToHash), "utf8")
        .digest("hex")
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from decimal import Decimal
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

# Ruta a los vectores de prueba compartidos con el simulador JS
HASH_VECTORS_PATH = Path(__file__).resolve().parent.parent.parent / "tests" / "hash_vectors.json"


def compute_hash(
    id_txn: int,
    user: str,
    date: str,
    value: int | float | Decimal,
    payment_method: str,
) -> str:
    """Calcula HMAC-SHA256 del payload con llave secreta."""
    # Convertir Decimal a float/int si es necesario para que json.dumps coincida con JS
    if isinstance(value, Decimal):
        value = float(value)
    if isinstance(value, float) and value.is_integer():
        value = int(value)

    data_to_hash = {
        "idTxn": id_txn,
        "user": user,
        "date": date,
        "value": value,
        "paymentMethod": payment_method,
    }
    payload = json.dumps(data_to_hash, separators=(",", ":"))
    
    return hmac.new(
        settings.secret_key.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

calculate_canonical_hash = compute_hash

def load_test_vectors() -> list[dict]:
    """Carga los vectores de prueba desde tests/hash_vectors.json."""
    with HASH_VECTORS_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)
