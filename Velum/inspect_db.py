import sqlite3
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

conn = sqlite3.connect("appresso.db")
cursor = conn.cursor()
    
print("=" * 85)
print("📁 ESTRUCTURA Y TABLAS DE LA BASE DE DATOS (appresso.db)")
print("=" * 85)
tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';").fetchall()
for t in tables:
    tname = t[0]
    count = cursor.execute(f"SELECT count(*) FROM {tname}").fetchone()[0]
    print(f"• Tabla: {tname:<25} | Registros actuales: {count}")

print("\n" + "=" * 85)
print("👤 ÚLTIMOS USUARIOS REGISTRADOS (Tabla: usuarios)")
print("=" * 85)
cursor.execute("SELECT id, email, nombre, estado, fecha_creacion FROM usuarios ORDER BY id DESC LIMIT 6")
users = cursor.fetchall()
for u in users:
    created = u[4][:19] if u[4] else "N/A"
    print(f"ID: {u[0]:<4} | Email: {u[1]:<32} | Nombre: {u[2]:<16} | Estado: {u[3]:<10} | Creado: {created}")

print("\n" + "=" * 85)
print("💳 ÚLTIMAS TRANSACCIONES REGISTRADAS (Tabla: transacciones)")
print("=" * 85)
cursor.execute("SELECT id, id_txn, usuario_id, valor, fecha_txn, estado, metodo_pago FROM transacciones ORDER BY id DESC LIMIT 10")
txns = cursor.fetchall()
for tx in txns:
    fecha = tx[4][:19] if tx[4] else "N/A"
    print(f"ID: {tx[0]:<4} | Txn: {tx[1]:<25} | UserID: {tx[2]:<3} | Valor: ${float(tx[3]):>9.2f} | Estado: {tx[5]:<10} | Método: {tx[6]:<10} | Fecha: {fecha}")

print("\n" + "=" * 85)
print("🚨 ANOMALÍAS DE FRAUDE DETECTADAS POR SLIDING WINDOW (Tabla: anomalias)")
print("=" * 85)
cursor.execute("SELECT id, transaccion_id, tipo, nivel, cantidad_transacciones, ventana_segundos, estado_revision, fecha_creacion FROM anomalias ORDER BY id DESC LIMIT 6")
anoms = cursor.fetchall()
if anoms:
    for a in anoms:
        created = a[7][:19] if a[7] else "N/A"
        print(f"ID: {a[0]:<4} | TxnID: {a[1]:<4} | Tipo: {a[2]:<15} | Nivel: {a[3]:<8} | Ráfaga: {a[4]} txns en {a[5]}s | Estado: {a[6]:<10} | Fecha: {created}")
else:
    print("No hay anomalías registradas aún.")

print("\n" + "=" * 85)
print("📊 RESUMEN GENERAL DE ESTADOS TRANSACCIONALES")
print("=" * 85)
estados = cursor.execute("SELECT estado, count(*), sum(valor) FROM transacciones GROUP BY estado").fetchall()
for e in estados:
    total_val = float(e[2]) if e[2] else 0.0
    print(f"• Estado: {e[0]:<12} | Cantidad: {e[1]:<6} | Monto Total: ${total_val:,.2f}")
print("=" * 85)

conn.close()
