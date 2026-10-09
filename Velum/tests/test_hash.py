"""Pruebas unitarias para el cálculo de hash HMAC-SHA256 y servicio de seguridad."""
from __future__ import annotations

import json
from decimal import Decimal

from app.security import safe_compare
from app.services.hash_service import compute_hash


def test_hash_tamper_detection():
    """Cualquier alteración en los campos debe producir un hash diferente."""
    h1 = compute_hash(1, "user@a.com", "2026-09-23T10:00:00.000", 100, "Tarjeta")
    # Modificar id
    h2 = compute_hash(2, "user@a.com", "2026-09-23T10:00:00.000", 100, "Tarjeta")
    # Modificar fecha por 1 ms
    h3 = compute_hash(1, "user@a.com", "2026-09-23T10:00:00.001", 100, "Tarjeta")
    # Modificar valor
    h4 = compute_hash(1, "user@a.com", "2026-09-23T10:00:00.000", 100.01, "Tarjeta")
    # Modificar método de pago
    h5 = compute_hash(1, "user@a.com", "2026-09-23T10:00:00.000", 100, "PSE")

    assert len({h1, h2, h3, h4, h5}) == 5


def test_safe_compare():
    """Prueba la comparación resistente a timing attacks con hmac.compare_digest."""
    assert safe_compare("abc123def", "abc123def") is True
    assert safe_compare("abc123def", "abc123deg") is False
    assert safe_compare("abc", "abcd") is False
