from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from decimal import Decimal
import pymysql

app = FastAPI(title="M7 - Tarifas y Pagos")

def obtener_conexion():
    return pymysql.connect(
        host="localhost",
        port=3306,
        user="m7",
        password="admin",
        database="m7",
        cursorclass=pymysql.cursors.DictCursor
    )

class EstimacionRequest(BaseModel):
    tipo_vehiculo: str
    distancia_km: float
    tiempo_min: float

@app.post("/tarifas/estimar")
def estimar_tarifa(datos: EstimacionRequest):
    errores = []

    # 1. Validar tipo de vehículo ('auto' o 'moto')
    if datos.tipo_vehiculo.lower() not in ["auto", "moto"]:
        errores.append({
            "campo": "tipo_vehiculo",
            "error": "VEHICULO INVALIDO",
            "mensaje": f"El tipo de vehículo '{datos.tipo_vehiculo}' no es válido. Debe ser 'auto' o 'moto'."
        })

    # 2. Validar distancia (no negativa)
    if datos.distancia_km < 0:
        errores.append({
            "campo": "distancia_km",
            "error": "DISTANCIA NEGATIVA",
            "mensaje": "La distancia en km no puede ser negativa."
        })

    # 3. Validar tiempo (estrictamente mayor a 0)
    if datos.tiempo_min <= 0:
        errores.append({
            "campo": "tiempo_min",
            "error": "TIEMPO INVALIDO",
            "mensaje": "El tiempo en minutos debe ser mayor a 0."
        })

    # Si se detectó uno o más errores, lanzar HTTP 400 con la lista completa
    if errores:
        raise HTTPException(
            status_code=400,
            detail={
                "codigo": "M7_DATOS_INVALIDOS",
                "errores": errores
            }
        )

    # Consulta a la base de datos
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            query = "SELECT * FROM parametros_tarifa WHERE tipo_vehiculo = %s"
            cursor.execute(query, (datos.tipo_vehiculo.lower(),))
            param = cursor.fetchone()

            if not param:
                raise HTTPException(status_code=404, detail="M7_SIN_PARAMETROS")

            base = float(param["base"])
            por_km = float(param["por_km"])
            por_min = float(param["por_min"])
            minima = float(param["minima"])

            costo_distancia = round(por_km * datos.distancia_km, 2)
            costo_tiempo = round(por_min * datos.tiempo_min, 2)
            subtotal = base + costo_distancia + costo_tiempo
            
            total = round(max(subtotal, minima), 2)

            return {
                "tipo_vehiculo": datos.tipo_vehiculo.lower(),
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