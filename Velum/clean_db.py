import sqlite3
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

conn = sqlite3.connect("appresso.db")
cursor = conn.cursor()

print("🧹 Limpiando base de datos...")
cursor.execute("PRAGMA foreign_keys = OFF;")
cursor.execute("DELETE FROM anomalias;")
cursor.execute("DELETE FROM transacciones;")
cursor.execute("DELETE FROM usuarios;")
cursor.execute("PRAGMA foreign_keys = ON;")
conn.commit()

cursor.execute("VACUUM;")
conn.commit()

print("✅ Tablas limpiadas exitosamente.")

tables = ["usuarios", "transacciones", "anomalias"]
for t in tables:
    count = cursor.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
    print(f"• {t}: {count} registros")

conn.close()
