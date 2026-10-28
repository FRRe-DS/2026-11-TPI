import json
import os
import re
import uuid
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import pymysql

app = FastAPI(title="M7 - Tarifas y Pagos")


def obtener_conexion():
    return pymysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "m7"),
        password=os.getenv("MYSQL_PASSWORD", "admin"),
        database=os.getenv("MYSQL_DATABASE", "m7"),
        cursorclass=pymysql.cursors.DictCursor,
    )


class EstimacionRequest(BaseModel):
    tipo_vehiculo: str
    distancia_km: float
    tiempo_min: float


class MedioPagoRequest(BaseModel):
    cliente_id: str
    tipo: str
    alias: str
    ultimos4: Optional[str] = None
    predeterminado: bool = False


class PagoAutorizarRequest(BaseModel):
    viaje_id: str
    cliente_id: str
    conductor_id: Optional[str] = None
    medio_pago_id: Optional[str] = None
    tipo_vehiculo: Literal["auto", "moto"]
    monto_estimado: float
    comision_pct: Optional[float] = None
    idempotency_key: str


class PagoCapturarRequest(BaseModel):
    pago_id: str
    monto_final: Optional[float] = None
    idempotency_key: str


class CargoCancelacionRequest(BaseModel):
    pago_id: str
    motivo: str = "Cancelación solicitada por el cliente"
    idempotency_key: str


class ReintegroRequest(BaseModel):
    pago_id: str
    monto: float
    motivo: str = "Reintegro por ajuste posterior"
    idempotency_key: str


class LiquidacionRequest(BaseModel):
    conductor_id: str
    desde: str
    hasta: str
    cantidad_viajes: int
    bruto: float
    comision: float
    neto: float
    idempotency_key: str


def validar_medio_pago(datos: MedioPagoRequest):
    errores = []

    if datos.tipo not in {"tarjeta", "billetera", "efectivo"}:
        errores.append({
            "campo": "tipo",
            "error": "TIPO INVALIDO",
            "mensaje": "El tipo de medio de pago debe ser 'tarjeta', 'billetera virtual' o 'efectivo'."
        })

    if not datos.alias or not datos.alias.strip():
        errores.append({
            "campo": "alias",
            "error": "ALIAS VACIO O INCOMPLETO",
            "mensaje": "El alias del medio de pago no puede estar vacío.",
        })

    if len(datos.alias.strip()) > 40:
        errores.append({
            "campo": "alias",
            "error": "ALIAS DEMASIADO LARGO",
            "mensaje": "El alias del medio de pago no puede superar los 40 caracteres.",
        })

    if datos.ultimos4 is not None:
        if not re.fullmatch(r"\d{4}", datos.ultimos4):
            errores.append({
                "campo": "ultimos4",
                "error": "ULTIMOS4 INVALIDO",
                "mensaje": "Los últimos 4 dígitos deben ser exactamente 4 números.",
            })

    if errores:
            raise HTTPException(
                status_code=400,
                detail={
                    "codigo": "M7_DATOS_INVALIDOS",
                    "errores": errores,
                },
            )


@app.get("/tarifas/parametros", tags=["Tarifas"])
def obtener_parametros():
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT * FROM parametros_tarifa")
            return cursor.fetchall()
    finally:
        conexion.close()


@app.post("/tarifas/estimar", tags=["Tarifas"])
def estimar_tarifa(datos: EstimacionRequest):
    errores = []

    if datos.tipo_vehiculo.lower() not in ["auto", "moto"]:
        errores.append({
            "campo": "tipo_vehiculo",
            "error": "VEHICULO INVALIDO",
            "mensaje": f"El tipo de vehículo '{datos.tipo_vehiculo}' no es válido. Debe ser 'auto' o 'moto'."
        })

    if datos.distancia_km < 0:
        errores.append({
            "campo": "distancia_km",
            "error": "DISTANCIA NEGATIVA",
            "mensaje": "La distancia en km no puede ser negativa."
        })

    if datos.tiempo_min <= 0:
        errores.append({
            "campo": "tiempo_min",
            "error": "TIEMPO INVALIDO",
            "mensaje": "El tiempo en minutos debe ser mayor a 0."
        })

    if errores:
        raise HTTPException(
            status_code=400,
            detail={
                "codigo": "M7_DATOS_INVALIDOS",
                "errores": errores,
            },
        )

    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT * FROM parametros_tarifa WHERE tipo_vehiculo = %s", (datos.tipo_vehiculo.lower(),))
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
                "moneda": "ARS",
            }
    finally:
        conexion.close()


@app.post("/pagos/medios", tags=["Pagos"])
def registrar_medio_pago(datos: MedioPagoRequest):
    validar_medio_pago(datos)

    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            try:
                if datos.predeterminado:
                    cursor.execute(
                        "UPDATE medios_pago SET predeterminado = FALSE WHERE cliente_id = %s",
                        (datos.cliente_id,),
                    )

                medio_id = str(uuid.uuid4())
                cursor.execute(
                    """
                    INSERT INTO medios_pago (id, cliente_id, tipo, alias, ultimos4, predeterminado)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (medio_id, datos.cliente_id, datos.tipo, datos.alias.strip(), datos.ultimos4, datos.predeterminado),
                )
                conexion.commit()

                return {
                    "id": medio_id,
                    "cliente_id": datos.cliente_id,
                    "tipo": datos.tipo,
                    "alias": datos.alias.strip(),
                    "ultimos4": datos.ultimos4,
                    "predeterminado": datos.predeterminado,
                }
            except pymysql.err.IntegrityError as exc:
                conexion.rollback()
                raise HTTPException(
                    status_code=400,
                    detail={
                        "codigo": "M7_MEDIO_PAGO_INVALIDO",
                        "mensaje": "Los datos del medio de pago no cumplen las reglas de validación del sistema.",
                        "detalle_db": str(exc),
                    },
                ) from exc
    finally:
        conexion.close()


@app.get("/pagos/medios/{cliente_id}", tags=["Pagos"])
def listar_medios_pago(cliente_id: str):
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM medios_pago WHERE cliente_id = %s ORDER BY predeterminado DESC, creado_en DESC",
                (cliente_id,),
            )
            return cursor.fetchall()
    finally:
        conexion.close()


@app.post("/pagos/autorizar", tags=["Pagos"])
def autorizar_pago(datos: PagoAutorizarRequest):
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM operaciones_financieras WHERE idempotency_key = %s LIMIT 1",
                (datos.idempotency_key,),
            )
            existente = cursor.fetchone()
            if existente:
                cursor.execute("SELECT * FROM pagos WHERE id = %s LIMIT 1", (existente["pago_id"],))
                pago_existente = cursor.fetchone()
                if pago_existente:
                    return {"mensaje": "Operación ya procesada", "pago": pago_existente, "idempotency_key": datos.idempotency_key}

            if datos.medio_pago_id:
                cursor.execute("SELECT * FROM medios_pago WHERE id = %s LIMIT 1", (datos.medio_pago_id,))
                medio = cursor.fetchone()
                if not medio:
                    raise HTTPException(status_code=404, detail="M7_MEDIO_PAGO_NO_ENCONTRADO")

            pago_id = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO pagos (
                    id, viaje_id, cliente_id, conductor_id, medio_pago_id, tipo_vehiculo,
                    monto_estimado, monto_final, comision_pct, estado, capturado_en,
                    liquidacion_id, creado_en, actualizado_en
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, NULL, %s, 'autorizado', NULL, NULL, NOW(), NOW())
                """,
                (
                    pago_id,
                    datos.viaje_id,
                    datos.cliente_id,
                    datos.conductor_id,
                    datos.medio_pago_id,
                    datos.tipo_vehiculo,
                    datos.monto_estimado,
                    datos.comision_pct if datos.comision_pct is not None else 0,
                ),
            )

            cursor.execute(
                """
                INSERT INTO operaciones_financieras (
                    id, pago_id, tipo, monto, resultado, motivo, idempotency_key, detalle, creado_en
                )
                VALUES (%s, %s, 'autorizacion', %s, 'ok', 'Autorización OK', %s, %s, NOW())
                """,
                (
                    str(uuid.uuid4()),
                    pago_id,
                    datos.monto_estimado,
                    datos.idempotency_key,
                    json.dumps({
                        "viaje_id": datos.viaje_id,
                        "cliente_id": datos.cliente_id,
                        "medio_pago_id": datos.medio_pago_id,
                        "monto_estimado": datos.monto_estimado,
                    }),
                ),
            )
            conexion.commit()

            cursor.execute("SELECT * FROM pagos WHERE id = %s LIMIT 1", (pago_id,))
            pago = cursor.fetchone()
            return {"mensaje": "Pago autorizado", "pago": pago, "idempotency_key": datos.idempotency_key}
    finally:
        conexion.close()


@app.post("/pagos/capturar", tags=["Pagos"])
def capturar_pago(datos: PagoCapturarRequest):
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM operaciones_financieras WHERE idempotency_key = %s LIMIT 1",
                (datos.idempotency_key,),
            )
            operacion = cursor.fetchone()
            if operacion:
                cursor.execute("SELECT * FROM pagos WHERE id = %s LIMIT 1", (operacion["pago_id"],))
                pago_existente = cursor.fetchone()
                if pago_existente:
                    return {"mensaje": "Captura ya procesada", "pago": pago_existente, "idempotency_key": datos.idempotency_key}

            cursor.execute("SELECT * FROM pagos WHERE id = %s LIMIT 1", (datos.pago_id,))
            pago = cursor.fetchone()
            if not pago:
                raise HTTPException(status_code=404, detail="M7_PAGO_NO_ENCONTRADO")

            if pago["estado"] not in ["autorizado", "cancelado_con_cargo"]:
                raise HTTPException(status_code=409, detail="M7_PAGO_ESTADO_NO_PERMITE_CAPTURA")

            monto_final = float(datos.monto_final) if datos.monto_final is not None else float(pago["monto_estimado"])
            cursor.execute(
                "UPDATE pagos SET monto_final = %s, estado = 'capturado', capturado_en = NOW(), actualizado_en = NOW() WHERE id = %s",
                (monto_final, datos.pago_id),
            )
            cursor.execute(
                """
                INSERT INTO operaciones_financieras (id, pago_id, tipo, monto, resultado, motivo, idempotency_key, detalle, creado_en)
                VALUES (%s, %s, 'captura', %s, 'ok', 'Captura exitosa', %s, %s, NOW())
                """,
                (
                    str(uuid.uuid4()),
                    datos.pago_id,
                    monto_final,
                    datos.idempotency_key,
                    json.dumps({"monto_final": monto_final, "pago_id": datos.pago_id}),
                ),
            )
            conexion.commit()

            cursor.execute("SELECT * FROM pagos WHERE id = %s LIMIT 1", (datos.pago_id,))
            pago_actualizado = cursor.fetchone()
            return {"mensaje": "Pago capturado", "pago": pago_actualizado, "idempotency_key": datos.idempotency_key}
    finally:
        conexion.close()


@app.post("/pagos/cancelar", tags=["Pagos"])
def cancelar_pago(datos: CargoCancelacionRequest):
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM operaciones_financieras WHERE idempotency_key = %s LIMIT 1",
                (datos.idempotency_key,),
            )
            operacion = cursor.fetchone()
            if operacion:
                cursor.execute("SELECT * FROM pagos WHERE id = %s LIMIT 1", (operacion["pago_id"],))
                pago_existente = cursor.fetchone()
                if pago_existente:
                    return {"mensaje": "Cargo de cancelación ya registrado", "pago": pago_existente, "idempotency_key": datos.idempotency_key}

            cursor.execute("SELECT * FROM pagos WHERE id = %s LIMIT 1", (datos.pago_id,))
            pago = cursor.fetchone()
            if not pago:
                raise HTTPException(status_code=404, detail="M7_PAGO_NO_ENCONTRADO")

            cursor.execute(
                "SELECT cargo_cancelacion FROM parametros_tarifa WHERE tipo_vehiculo = %s LIMIT 1",
                (pago["tipo_vehiculo"],),
            )
            param = cursor.fetchone()
            cargo = float(param["cargo_cancelacion"]) if param else 0.0

            cursor.execute(
                "UPDATE pagos SET monto_final = COALESCE(monto_final, monto_estimado), estado = 'cancelado_con_cargo', actualizado_en = NOW() WHERE id = %s",
                (datos.pago_id,),
            )
            cursor.execute(
                """
                INSERT INTO operaciones_financieras (id, pago_id, tipo, monto, resultado, motivo, idempotency_key, detalle, creado_en)
                VALUES (%s, %s, 'cargo_cancelacion', %s, 'ok', %s, %s, %s, NOW())
                """,
                (
                    str(uuid.uuid4()),
                    datos.pago_id,
                    cargo,
                    datos.motivo,
                    datos.idempotency_key,
                    json.dumps({"cargo_cancelacion": cargo, "motivo": datos.motivo}),
                ),
            )
            conexion.commit()

            cursor.execute("SELECT * FROM pagos WHERE id = %s LIMIT 1", (datos.pago_id,))
            pago_actualizado = cursor.fetchone()
            return {"mensaje": "Cargo de cancelación registrado", "cargo": cargo, "pago": pago_actualizado, "idempotency_key": datos.idempotency_key}
    finally:
        conexion.close()


@app.post("/pagos/reintegrar", tags=["Pagos"])
def reintegrar_pago(datos: ReintegroRequest):
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM operaciones_financieras WHERE idempotency_key = %s LIMIT 1",
                (datos.idempotency_key,),
            )
            operacion = cursor.fetchone()
            if operacion:
                cursor.execute("SELECT * FROM pagos WHERE id = %s LIMIT 1", (operacion["pago_id"],))
                pago_existente = cursor.fetchone()
                if pago_existente:
                    return {"mensaje": "Reintegro ya registrado", "pago": pago_existente, "idempotency_key": datos.idempotency_key}

            cursor.execute("SELECT * FROM pagos WHERE id = %s LIMIT 1", (datos.pago_id,))
            pago = cursor.fetchone()
            if not pago:
                raise HTTPException(status_code=404, detail="M7_PAGO_NO_ENCONTRADO")

            monto_total = float(pago["monto_final"]) if pago["monto_final"] is not None else float(pago["monto_estimado"])
            if float(datos.monto) < 0 or float(datos.monto) > monto_total:
                raise HTTPException(status_code=400, detail="M7_MONTO_REINTEGRO_INVALIDO")

            nuevo_estado = "reintegrado" if float(datos.monto) >= monto_total else "reintegrado_parcial"
            cursor.execute(
                "UPDATE pagos SET estado = %s, actualizado_en = NOW() WHERE id = %s",
                (nuevo_estado, datos.pago_id),
            )
            cursor.execute(
                """
                INSERT INTO operaciones_financieras (id, pago_id, tipo, monto, resultado, motivo, idempotency_key, detalle, creado_en)
                VALUES (%s, %s, 'reintegro', %s, 'ok', %s, %s, %s, NOW())
                """,
                (
                    str(uuid.uuid4()),
                    datos.pago_id,
                    datos.monto,
                    datos.motivo,
                    datos.idempotency_key,
                    json.dumps({"monto_reintegrado": datos.monto, "estado": nuevo_estado}),
                ),
            )
            conexion.commit()

            cursor.execute("SELECT * FROM pagos WHERE id = %s LIMIT 1", (datos.pago_id,))
            pago_actualizado = cursor.fetchone()
            return {"mensaje": "Reintegro registrado", "pago": pago_actualizado, "monto_reintegrado": datos.monto, "idempotency_key": datos.idempotency_key}
    finally:
        conexion.close()


@app.get("/pagos/{viaje_id}", tags=["Pagos"])
def obtener_pago_por_viaje(viaje_id: str):
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT * FROM pagos WHERE viaje_id = %s LIMIT 1", (viaje_id,))
            pago = cursor.fetchone()
            if not pago:
                raise HTTPException(status_code=404, detail="M7_PAGO_NO_ENCONTRADO")
            return pago
    finally:
        conexion.close()


@app.get("/pagos/{viaje_id}/historial", tags=["Pagos"])
def historial_financiero(viaje_id: str):
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT * FROM pagos WHERE viaje_id = %s LIMIT 1", (viaje_id,))
            pago = cursor.fetchone()
            if not pago:
                raise HTTPException(status_code=404, detail="M7_PAGO_NO_ENCONTRADO")
            cursor.execute(
                "SELECT * FROM operaciones_financieras WHERE pago_id = %s ORDER BY creado_en DESC",
                (pago["id"],),
            )
            return cursor.fetchall()
    finally:
        conexion.close()


@app.post("/liquidaciones", tags=["Liquidaciones"])
def crear_liquidacion(datos: LiquidacionRequest):
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM liquidaciones WHERE idempotency_key = %s LIMIT 1",
                (datos.idempotency_key,),
            )
            existente = cursor.fetchone()
            if existente:
                return {"mensaje": "Liquidación ya registrada", "liquidacion": existente, "idempotency_key": datos.idempotency_key}

            liquidacion_id = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO liquidaciones (
                    id, conductor_id, desde, hasta, cantidad_viajes, bruto, comision, neto, estado, idempotency_key, creado_en, actualizado_en
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pendiente', %s, NOW(), NOW())
                """,
                (
                    liquidacion_id,
                    datos.conductor_id,
                    datos.desde,
                    datos.hasta,
                    datos.cantidad_viajes,
                    datos.bruto,
                    datos.comision,
                    datos.neto,
                    datos.idempotency_key,
                ),
            )
            conexion.commit()

            cursor.execute("SELECT * FROM liquidaciones WHERE id = %s LIMIT 1", (liquidacion_id,))
            liquidacion = cursor.fetchone()
            return {"mensaje": "Liquidación creada", "liquidacion": liquidacion, "idempotency_key": datos.idempotency_key}
    finally:
        conexion.close()


@app.get("/liquidaciones/{conductor_id}", tags=["Liquidaciones"])
def listar_liquidaciones_conductor(conductor_id: str):
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM liquidaciones WHERE conductor_id = %s ORDER BY creado_en DESC",
                (conductor_id,),
            )
            return cursor.fetchall()
    finally:
        conexion.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
