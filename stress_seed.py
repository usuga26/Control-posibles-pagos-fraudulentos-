# stress_seed.py
import asyncio
import hashlib
import json
import random
import time
import urllib.request
from datetime import datetime, timedelta

# Configuración
# Puedes cambiar esta URL si usas Ngrok/Tunnelmole o un puerto distinto
BASE_URL = "http://localhost:8000/api/transacciones"
DURATION_MINUTES = 3
TOTAL_SECONDS = DURATION_MINUTES * 60
PAYMENT_METHODS = ["Tarjeta", "PSE", "Transferencia", "Otro"]

def get_bogota_time():
    """Genera timestamp con la zona horaria de Bogotá (UTC-5) exigida por el servidor."""
    now = datetime.utcnow() - timedelta(hours=5)
    return now.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]

def compute_hash(id_txn, user, date_str, value, payment_method):
    """Firma de integridad SHA-256 exacta a la de WebCrypto (simulator.js)"""
    norm_user = user.lower().strip().replace(" ", "")
    norm_value = f"{float(value):.2f}"
    canonical = f"{id_txn}|{norm_user}|{date_str}|{norm_value}|{payment_method}"
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()

def build_payload(user, is_attack=False, index=1):
    id_txn = f"STRESS-{int(time.time()*1000)}-{index}"
    date_str = get_bogota_time()
    value = round(random.uniform(1000, 500000), 2)
    payment_method = random.choice(PAYMENT_METHODS)
    
    txn_hash = compute_hash(id_txn, user, date_str, value, payment_method)
    return {
        "idTxn": id_txn,
        "user": user,
        "date": date_str,
        "value": value,
        "paymentMethod": payment_method,
        "hash": txn_hash
    }

async def send_request(payload):
    req = urllib.request.Request(BASE_URL, data=json.dumps(payload).encode('utf-8'), 
                                 headers={'Content-Type': 'application/json'}, method='POST')
    try:
        response = await asyncio.to_thread(urllib.request.urlopen, req)
        return response.getcode()
    except Exception as e:
        return getattr(e, 'code', 500)

async def simulate_normal_user():
    """Tráfico normal: Transacciones esporádicas con pausas largas (>10s)"""
    user = f"normal_{random.randint(1, 10000)}@test.com"
    end_time = time.time() + TOTAL_SECONDS
    
    while time.time() < end_time:
        payload = build_payload(user)
        await send_request(payload)
        await asyncio.sleep(random.uniform(10, 20)) # O(1) Memory Cleanup Test

async def simulate_fraud_burst():
    """5% de tráfico: Inyección concentrada de 3 a 5 transacciones en menos de 2s"""
    user = f"attacker_{random.randint(1, 1000)}@fraud.com"
    burst_size = random.randint(3, 5)
    
    tasks = []
    for i in range(burst_size):
        payload = build_payload(user, is_attack=True, index=i+1)
        tasks.append(send_request(payload))
        await asyncio.sleep(random.uniform(0.1, 0.4)) # Menos de 2s en total
    
    await asyncio.gather(*tasks)

async def main():
    print(f"🚀 Iniciando estrés continuo ({DURATION_MINUTES} minutos)...")
    print(f"🎯 Target URL: {BASE_URL}")
    print("🔥 Probando eficiencia amortizada O(1) de la Ventana Deslizante...\n")
    
    end_time = time.time() + TOTAL_SECONDS
    tasks = []
    
    # Lanzar inicialmente 100 hilos de usuarios "normales" concurrentes
    for _ in range(100):
        tasks.append(asyncio.create_task(simulate_normal_user()))

    # Bucle principal: lanzar ataques esporádicos mientras el tiempo corra
    while time.time() < end_time:
        if random.random() < 0.05:  # 5% de probabilidad en cada tick
            print(f"🚨 [ATAQUE DETECTADO] Inyectando ráfaga POSIBLE_FRAUDE...")
            tasks.append(asyncio.create_task(simulate_fraud_burst()))
        await asyncio.sleep(1)

    # Esperar finalización o cancelar tareas pendientes
    for t in tasks:
        t.cancel()
    
    print("\n✅ Prueba de estrés finalizada. Revisa el dashboard para confirmar rendimiento.")

if __name__ == "__main__":
    asyncio.run(main())
