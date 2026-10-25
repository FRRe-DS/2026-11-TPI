from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from decimal import Decimal
import pymysql

app = FastAPI(title="M7 - Tarifas y Pagos")

# 1. Conexión directa a MySQL
def obtener_conexion():
    return pymysql.connect(
        host="localhost",
        port=3306,
        user="m7",          # o "root"
        password="admin",   # la que definiste en tu .env
        database="m7",      # el nombre que pusiste en tu .env
        cursorclass=pymysql.cursors.DictCursor
    )

# 2. Esquema de los datos que van a entrar por el endpoint
class EstimacionRequest(BaseModel):
    tipo_vehiculo: str  # 'auto' o 'moto'
    distancia_km: float
    tiempo_min: float

# 3. EL ENDPOINT (RF-7.1)
@app.post("/tarifas/estimar")
def estimar_tarifa(datos: EstimacionRequest):
    # Validaciones básicas
    if datos.distancia_km < 0 or datos.tiempo_min < 0:
        raise HTTPException(status_code=400, detail="M7_DATOS_INVALIDOS")

    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            # Buscamos los parámetros de la tabla que ya creaste en MySQL
            query = "SELECT * FROM parametros_tarifa WHERE tipo_vehiculo = %s"
            cursor.execute(query, (datos.tipo_vehiculo,))
            param = cursor.fetchone()

            if not param:
                raise HTTPException(status_code=404, detail="M7_SIN_PARAMETROS")

            # Fórmula: base + (por_km * km) + (por_min * min)
            base = float(param["base"])
            por_km = float(param["por_km"])
            por_min = float(param["por_min"])
            minima = float(param["minima"])

            costo_distancia = round(por_km * datos.distancia_km, 2)
            costo_tiempo = round(por_min * datos.tiempo_min, 2)
            subtotal = base + costo_distancia + costo_tiempo
            
            # La tarifa no puede ser menor a la mínima establecida
            total = round(max(subtotal, minima), 2)

            return {
                "tipo_vehiculo": datos.tipo_vehiculo,
                "base": base,
                "distancia": costo_distancia,
                "tiempo": costo_tiempo,
                "minima": minima,
                "minima_aplicada": subtotal < minima,
                "total": total,
                "moneda": "ARS"
            }
    finally:
        conexion.close()    