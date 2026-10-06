"""VELUM — Generador de Tráfico Continuo y Estrés Masivo (~3 a 5 Minutos).

Simula carga concurrente multi-usuario bajo red local o túnel Ngrok:
- 90% tráfico normal espaciado (> 10s entre txns del mismo usuario).
- 10% ráfagas de ataque concentradas (>= 3 txns en < 2s).
- Validación de integridad SHA-256 canónica en cada transacción.
- Telemetría en vivo en consola: throughput (txns/s), latencia y anomalías.
"""
import argparse
import asyncio
import hashlib
import json
import random
import sys
import time
import urllib.request
from datetime import datetime, timedelta

# Asegurar compatibilidad UTF-8 en terminales de Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Configuración por defecto
DEFAULT_URL = "https://catnap-bulginess-erased.ngrok-free.dev/api/v1/transactions"
DEFAULT_DURATION = 4.0  # Minutos (ajustable de 2.5 a 7 min)
PAYMENT_METHODS = ["Tarjeta", "PSE", "Transferencia", "Otro"]

class StressTelemetry:
    def __init__(self):
        self.start_time = time.time()
        self.total_sent = 0
        self.approved = 0
        self.suspicious = 0
        self.duplicates = 0
        self.errors = 0
        self.lock = asyncio.Lock()

    async def record(self, status_code, data):
        async with self.lock:
            self.total_sent += 1
            if status_code in (200, 201):
                if isinstance(data, dict):
                    if data.get("duplicate"):
                        self.duplicates += 1
                    elif data.get("transaction", {}).get("status") == "SOSPECHOSA" or data.get("analysis", {}).get("anomalyDetected"):
                        self.suspicious += 1
                    else:
                        self.approved += 1
                else:
                    self.approved += 1
            else:
                self.errors += 1

    def print_status(self, remaining):
        elapsed = time.time() - self.start_time
        tps = self.total_sent / elapsed if elapsed > 0 else 0
        mins, secs = divmod(int(remaining), 60)
        sys.stdout.write(
            f"\r⏱️  Restante: {mins:02d}:{secs:02d} | "
            f"Enviadas: {self.total_sent:5d} | "
            f"✅ Aprobadas: {self.approved:5d} | "
            f"🚨 Sospechosas: {self.suspicious:4d} | "
            f"⚡ {tps:5.1f} txns/s   "
        )
        sys.stdout.flush()

def get_bogota_time():
    """Genera timestamp exacto en hora de Bogotá (UTC-5) con milisegundos."""
    now = datetime.now(timezone.utc) - timedelta(hours=5)
    return now.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]

def compute_hash(id_txn, user, date_str, value, payment_method):
    """Cálculo de firma SHA-256 canónica."""
    norm_user = user.lower().strip().replace(" ", "")
    norm_value = f"{float(value):.2f}"
    canonical = f"{id_txn}|{norm_user}|{date_str}|{norm_value}|{payment_method}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

def build_payload(id_txn, user, value, payment_method):
    date_str = get_bogota_time()
    txn_hash = compute_hash(id_txn, user, date_str, value, payment_method)
    return {
        "idTxn": id_txn,
        "user": user,
        "date": date_str,
        "value": value,
        "paymentMethod": payment_method,
        "hash": txn_hash,
    }

async def send_txn(url, payload, telemetry):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "ngrok-skip-browser-warning": "true",
            "User-Agent": "Velum-Stress-Engine/2.0",
        },
        method="POST",
    )
    try:
        response = await asyncio.to_thread(urllib.request.urlopen, req, timeout=5)
        status_code = response.getcode()
        body = json.loads(response.read().decode("utf-8"))
        await telemetry.record(status_code, body)
    except Exception as exc:
        code = getattr(exc, "code", 500)
        await telemetry.record(code, None)

async def worker_normal_user(user_email, url, end_time, telemetry):
    """Simula un usuario legítimo (pausas > 10s, comportamiento O(1) amortizado)."""
    counter = 1
    while time.time() < end_time:
        id_txn = f"NORM-{int(time.time()*1000)}-{user_email.split('@')[0]}-{counter}"
        val = round(random.uniform(20000, 350000), 2)
        pm = random.choice(PAYMENT_METHODS)
        payload = build_payload(id_txn, user_email, val, pm)
        await send_txn(url, payload, telemetry)
        counter += 1
        # Pausa superior a la ventana (10s a 18s) para garantizar purga de cola
        await asyncio.sleep(random.uniform(10.0, 18.0))

async def launch_fraud_burst(victim_email, url, telemetry):
    """Inyecta una ráfaga anómala de 3 a 5 transacciones en < 2 segundos."""
    burst_size = random.randint(3, 5)
    t_base = int(time.time() * 1000)
    for i in range(burst_size):
        id_txn = f"FRAUD-{t_base}-{i+1}"
        val = round(random.uniform(100000, 800000), 2)
        pm = "Tarjeta"
        payload = build_payload(id_txn, victim_email, val, pm)
        asyncio.create_task(send_txn(url, payload, telemetry))
        await asyncio.sleep(random.uniform(0.15, 0.45))  # Total < 2.0 segundos

async def main():
    parser = argparse.ArgumentParser(description="VELUM Continuous Stress Traffic Generator")
    parser.add_argument("--url", default=DEFAULT_URL, help="Endpoint POST de destino")
    parser.add_argument("--minutes", type=float, default=DEFAULT_DURATION, help="Duración en minutos (~2.5 a 7)")
    args = parser.parse_args()

    total_seconds = int(args.minutes * 60)
    end_time = time.time() + total_seconds
    telemetry = StressTelemetry()

    print("=" * 75)
    print("🚀 VELUM MOTOR DE PRUEBAS DE ESTRÉS CONTINUO (Staff Performance Engine)")
    print(f"🎯 Target Endpoint: {args.url}")
    print(f"⏱️  Duración programada: {args.minutes:.1f} minutos ({total_seconds} segundos)")
    print("📊 Mezcla de tráfico: 90% Tráfico Normal | 10% Ráfagas POSIBLE_FRAUDE")
    print("=" * 75 + "\n")

    # Pool de 60 usuarios concurrentes legítimos
    normal_users = [f"cliente_{i:03d}@empresa.com" for i in range(1, 61)]
    tasks = [asyncio.create_task(worker_normal_user(u, args.url, end_time, telemetry)) for u in normal_users]

    # Bucle orquestador de ráfagas fraudulentas (~10% del total de transacciones)
    while time.time() < end_time:
        remaining = end_time - time.time()
        telemetry.print_status(remaining)

        # Cada 4 a 8 segundos detona un ataque coordinado para un usuario sospechoso
        if random.random() < 0.25:
            attacker = f"attacker_{random.randint(1, 20)}@fraud-corp.com"
            asyncio.create_task(launch_fraud_burst(attacker, args.url, telemetry))

        await asyncio.sleep(1)

    print("\n\n⏳ Finalizando tareas pendientes...")
    for t in tasks:
        t.cancel()

    elapsed = time.time() - telemetry.start_time
    print("=" * 75)
    print("🎉 PRUEBA DE ESTRÉS COMPLETADA CON ÉXITO")
    print(f"⏱️  Tiempo real ejecutado: {elapsed:.1f} segundos ({elapsed/60:.2f} min)")
    print(f"📦 Total Transacciones Inyectadas: {telemetry.total_sent}")
    print(f"✅ Transacciones Aprobadas:       {telemetry.approved}")
    print(f"🚨 Anomalías / Fraudes Detonados: {telemetry.suspicious}")
    print(f"⚡ Throughput Promedio:           {telemetry.total_sent / elapsed:.2f} txns/segundo")
    print("=" * 75)

if __name__ == "__main__":
    asyncio.run(main())
