"""Script interactivo para visualizar Redis en funcionamiento (Módulo 7 - TPI).

Uso:
    python demo_redis.py
"""

import json
import time
import sys
from pathlib import Path

# Configurar salida UTF-8 para consola de Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Agregar backend al path para importar módulos de la app
BACKEND_DIR = Path(__file__).resolve().parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core import redis as redis_core
from app.core.config import settings


def linea(titulo=""):
    print("\n" + "=" * 25 + f" {titulo} " + "=" * 25)


def main():
    print("🚀 Iniciando prueba interactiva de Redis...")
    linea("1. ESTADO DE LA CONEXIÓN")
    print(f"Host configurado: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
    print(f"¿Redis habilitado en settings?: {settings.REDIS_ENABLED}")

    conectado = redis_core.ping_redis()
    if not conectado:
        print("❌ NO SE PUDO CONECTAR A REDIS.")
        print("\n👉 Para levantarlo con Docker ejecuta:")
        print("   docker compose up -d redis")
        print("\nLuego vuelve a ejecutar este script.")
        return

    print("✅ ¡Conexión exitosa con el servidor Redis (PONG recibido)!")

    linea("2. VISUALIZAR ESCRITURA Y LECTURA EN CACHÉ")
    clave = "tarifas:parametro:auto"
    datos_ejemplo = {
        "tipo_vehiculo": "auto",
        "base": 500.0,
        "por_km": 150.0,
        "por_min": 50.0,
        "minima": 800.0,
        "cargo_cancelacion": 400.0,
        "comision_pct": 15.0,
    }

    print(f"📝 Guardando datos en la clave: '{clave}' con TTL de 3600 segundos (1 hora)...")
    redis_core.guardar_cache(clave, datos_ejemplo, ttl_segundos=3600)
    print("   -> Datos guardados correctamente en memoria.")

    print(f"\n🔍 Leyendo la clave desde Redis...")
    recuperado = redis_core.obtener_cache(clave)
    print("   -> Valor recuperado de la memoria:")
    print(json.dumps(recuperado, indent=4))

    linea("3. TIEMPO DE EXPIRACIÓN (TTL)")
    client = redis_core.get_redis_client()
    if client:
        ttl = client.ttl(clave)
        print(f"⏳ Tiempo de vida restante para '{clave}': {ttl} segundos")

    linea("4. COMPARACIÓN DE LATENCIA (Rendimiento)")
    print("Simulando consulta con y sin Redis:")

    # Simular consulta a Base de Datos (con latencia típica de I/O de red/disco)
    t0 = time.perf_counter()
    time.sleep(0.035)  # simula 35 ms de latencia en MySQL
    _ = datos_ejemplo
    t_db = (time.perf_counter() - t0) * 1000

    # Consulta real a Redis
    t1 = time.perf_counter()
    _ = redis_core.obtener_cache(clave)
    t_redis = (time.perf_counter() - t1) * 1000

    print(f"   ⏱️  Consulta tradicional a MySQL (simulada): {t_db:.2f} ms")
    print(f"   ⚡ Consulta con caché en Redis:            {t_redis:.2f} ms")
    if t_redis > 0:
        mejora = round(t_db / t_redis, 1)
        print(f"   🔥 ¡Redis fue aproximadamente {mejora}x veces más rápido!")

    linea("5. LISTADO DE CLAVES ACTIVAS")
    if client:
        claves = client.keys("tarifas:*")
        print(f"Claves encontradas con patrón 'tarifas:*': {claves}")

    linea("6. INVALIDACIÓN DE CACHÉ")
    print("Simulando actualización de tarifas por un operador...")
    redis_core.eliminar_cache(clave)
    post_delete = redis_core.obtener_cache(clave)
    print(f"¿La clave '{clave}' sigue existiendo?: {post_delete is not None}")
    print("✅ Caché invalidada correctamente (el próximo request irá a la BD para refrescar).")

    linea("FIN DE LA DEMO")
    print("💡 Recuerda que también puedes ver las operaciones en vivo ejecutando:")
    print("   docker exec -it m7_redis redis-cli MONITOR\n")


if __name__ == "__main__":
    main()
