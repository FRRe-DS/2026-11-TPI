import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Header, HTTPException, Response
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

from app.core.database import get_db
from app.schemas.liquidaciones import LiquidacionNueva, TransferenciaNueva
from app.schemas.pagos import (
    AvisoPasarela,
    CargoCancelacionNuevo,
    PagoNuevo,
    ReembolsoNuevo,
)
from app.schemas.tarifas import (
    EstimacionNueva,
    ReglaTarifaCambios,
    ReglaTarifaNueva,
    TarifaFinalNueva,
)


router = APIRouter(prefix="/api/v1")


def _redondear(valor: Any) -> float:
    return float(Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso(valor: Any) -> Optional[str]:
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor.isoformat()
    return str(valor)


def _json_valor(valor: Any) -> Any:
    if isinstance(valor, (str, int, float, bool)) or valor is None:
        return valor
    if isinstance(valor, Decimal):
        return _redondear(valor)
    if isinstance(valor, datetime):
        return _iso(valor)
    if isinstance(valor, (bytes, bytearray)):
        return json.loads(valor.decode("utf-8"))
    if isinstance(valor, dict):
        return {clave: _json_valor(contenido) for clave, contenido in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [_json_valor(contenido) for contenido in valor]
    return str(valor)


def _row_json(row: Dict[str, Any]) -> Dict[str, Any]:
    return _json_valor(row)


def _hash_cuerpo(datos: BaseModel) -> str:
    cuerpo = datos.model_dump_json()
    return hashlib.sha256(cuerpo.encode("utf-8")).hexdigest()


def _idempotencia(
    clave: str,
    ruta: str,
    datos: BaseModel,
    response: Response,
) -> Optional[Dict[str, Any]]:
    cuerpo_hash = _hash_cuerpo(datos)
    with get_db() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT ruta, cuerpo_hash, respuesta FROM operaciones_idempotentes WHERE clave=%s",
                (clave,),
            )
            existente = cursor.fetchone()
    if existente is None:
        return None
    if existente["ruta"] != ruta or existente["cuerpo_hash"] != cuerpo_hash:
        raise HTTPException(status_code=422, detail="Idempotency-Key ya fue usada con otro cuerpo")
    response.status_code = 200
    respuesta = existente["respuesta"]
    if isinstance(respuesta, bytes):
        respuesta = respuesta.decode("utf-8")
    return json.loads(respuesta) if isinstance(respuesta, str) else respuesta


def _guardar_idempotencia(
    clave: str,
    ruta: str,
    datos: BaseModel,
    respuesta: Dict[str, Any],
) -> None:
    with get_db() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO operaciones_idempotentes (clave, ruta, cuerpo_hash, estado_http, respuesta)
                VALUES (%s, %s, %s, 200, CAST(%s AS JSON))
                """,
                (clave, ruta, _hash_cuerpo(datos), json.dumps(jsonable_encoder(respuesta))),
            )
        conexion.commit()


def _regla_activa(tipo_vehiculo: str, cursor: Any) -> Optional[Dict[str, Any]]:
    cursor.execute(
        """
        SELECT * FROM reglas_tarifa
        WHERE tipo_vehiculo=%s AND activa=TRUE
        ORDER BY actualizado_en DESC LIMIT 1
        """,
        (tipo_vehiculo,),
    )
    return cursor.fetchone()


def _pagina(items: List[Dict[str, Any]], page: int, size: int) -> Dict[str, Any]:
    if page < 0:
        raise HTTPException(status_code=422, detail="page debe ser mayor o igual a cero")
    if size < 1 or size > 100:
        raise HTTPException(status_code=422, detail="size debe estar entre 1 y 100")
    inicio = page * size
    return {
        "page": page,
        "size": size,
        "total_elementos": len(items),
        "total_paginas": (len(items) + size - 1) // size,
        "items": items[inicio:inicio + size],
    }


@router.post("/tarifas/estimaciones", tags=["Tarifas"])
def estimar_tarifa(datos: EstimacionNueva) -> Dict[str, Any]:
    with get_db() as conexion:
        with conexion.cursor() as cursor:
            regla = _regla_activa(datos.tipo_vehiculo, cursor)
    if regla is None:
        raise HTTPException(status_code=422, detail="No existe una regla activa para el tipo de vehiculo")

    tarifa_base = _redondear(regla["tarifa_base"])
    cargo_distancia = _redondear(float(regla["precio_por_km"]) * datos.distancia_km)
    cargo_tiempo = _redondear(float(regla["precio_por_minuto"]) * datos.duracion_estimada_min)
    subtotal = _redondear((tarifa_base + cargo_distancia + cargo_tiempo) * datos.multiplicador_demanda)
    total = _redondear(max(subtotal, float(regla["tarifa_minima"])))
    return {
        "regla_id": str(regla["id"]),
        "moneda": "ARS",
        "desglose": {
            "tarifa_base": tarifa_base,
            "cargo_distancia": cargo_distancia,
            "cargo_tiempo": cargo_tiempo,
            "multiplicador_demanda": datos.multiplicador_demanda,
            "total": total,
        },
    }


@router.post("/tarifas/viajes/{viaje_id}/tarifa-final", tags=["Tarifas"], status_code=201)
def registrar_tarifa_final(viaje_id: UUID, datos: TarifaFinalNueva) -> Dict[str, Any]:
    viaje_key = str(viaje_id)
    estimacion = estimar_tarifa(EstimacionNueva(
        tipo_vehiculo=datos.tipo_vehiculo,
        distancia_km=datos.distancia_real_km,
        duracion_estimada_min=datos.duracion_real_min,
        multiplicador_demanda=datos.multiplicador_demanda,
    ))
    tarifa = {
        "viaje_id": viaje_key,
        "regla_id": estimacion["regla_id"],
        "moneda": "ARS",
        "desglose": estimacion["desglose"],
        "calculada_en": _ahora(),
    }
    with get_db() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT viaje_id FROM tarifas_finales WHERE viaje_id=%s", (viaje_key,))
            if cursor.fetchone():
                raise HTTPException(status_code=409, detail="La tarifa final del viaje ya fue registrada")
            cursor.execute(
                """
                INSERT INTO tarifas_finales (viaje_id, regla_id, moneda, desglose, calculada_en)
                VALUES (%s, %s, %s, CAST(%s AS JSON), NOW())
                """,
                (viaje_key, estimacion["regla_id"], "ARS", json.dumps(estimacion["desglose"])),
            )
        conexion.commit()
    return tarifa


@router.get("/tarifas/viajes/{viaje_id}/tarifa-final", tags=["Tarifas"])
def obtener_tarifa_final(viaje_id: UUID) -> Dict[str, Any]:
    with get_db() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT * FROM tarifas_finales WHERE viaje_id=%s", (str(viaje_id),))
            fila = cursor.fetchone()
    if not fila:
        raise HTTPException(status_code=404, detail="El viaje no tiene tarifa final")
    fila = _row_json(fila)
    fila["desglose"] = json.loads(fila["desglose"]) if isinstance(fila["desglose"], str) else fila["desglose"]
    fila["calculada_en"] = _iso(fila["calculada_en"])
    return fila


@router.get("/tarifas/reglas", tags=["Tarifas"])
def listar_reglas(tipo_vehiculo: Optional[str] = None, solo_activas: bool = False, page: int = 0, size: int = 20):
    consulta = "SELECT * FROM reglas_tarifa WHERE 1=1"
    parametros: List[Any] = []
    if tipo_vehiculo:
        consulta += " AND tipo_vehiculo=%s"
        parametros.append(tipo_vehiculo)
    if solo_activas:
        consulta += " AND activa=TRUE"
    consulta += " ORDER BY actualizado_en DESC"
    with get_db() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(consulta, parametros)
            items = [_row_json(fila) for fila in cursor.fetchall()]
    return _pagina(items, page, size)


@router.post("/tarifas/reglas", tags=["Tarifas"], status_code=201)
def crear_regla(datos: ReglaTarifaNueva, response: Response) -> Dict[str, Any]:
    regla_id = str(uuid4())
    with get_db() as conexion:
        with conexion.cursor() as cursor:
            if datos.activa:
                cursor.execute("UPDATE reglas_tarifa SET activa=FALSE WHERE tipo_vehiculo=%s", (datos.tipo_vehiculo,))
            cursor.execute(
                """
                INSERT INTO reglas_tarifa
                (id, tipo_vehiculo, tarifa_base, precio_por_km, precio_por_minuto, tarifa_minima,
                 cargo_cancelacion, activa)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (regla_id, datos.tipo_vehiculo, datos.tarifa_base, datos.precio_por_km,
                 datos.precio_por_minuto, datos.tarifa_minima, datos.cargo_cancelacion, datos.activa),
            )
        conexion.commit()
    regla = {"id": regla_id, **datos.model_dump()}
    response.headers["Location"] = f"/api/v1/tarifas/reglas/{regla_id}"
    return regla


@router.get("/tarifas/reglas/{regla_id}", tags=["Tarifas"])
def obtener_regla(regla_id: UUID) -> Dict[str, Any]:
    with get_db() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT * FROM reglas_tarifa WHERE id=%s", (str(regla_id),))
            regla = cursor.fetchone()
    if not regla:
        raise HTTPException(status_code=404, detail="Regla no encontrada")
    return _row_json(regla)


@router.patch("/tarifas/reglas/{regla_id}", tags=["Tarifas"])
def modificar_regla(regla_id: UUID, datos: ReglaTarifaCambios) -> Dict[str, Any]:
    regla_key = str(regla_id)
    cambios = datos.model_dump(exclude_unset=True)
    with get_db() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT tipo_vehiculo FROM reglas_tarifa WHERE id=%s", (regla_key,))
            actual = cursor.fetchone()
            if not actual:
                raise HTTPException(status_code=404, detail="Regla no encontrada")
            if cambios.get("activa") is True:
                cursor.execute("UPDATE reglas_tarifa SET activa=FALSE WHERE tipo_vehiculo=%s", (actual["tipo_vehiculo"],))
            nombres = {
                "tarifa_base": "tarifa_base", "precio_por_km": "precio_por_km",
                "precio_por_minuto": "precio_por_minuto", "tarifa_minima": "tarifa_minima",
                "cargo_cancelacion": "cargo_cancelacion", "activa": "activa",
            }
            asignaciones = ", ".join(f"{nombres[clave]}=%s" for clave in cambios)
            cursor.execute(
                f"UPDATE reglas_tarifa SET {asignaciones} WHERE id=%s",
                (*cambios.values(), regla_key),
            )
            cursor.execute("SELECT * FROM reglas_tarifa WHERE id=%s", (regla_key,))
            actualizada = cursor.fetchone()
        conexion.commit()
    return _row_json(actualizada)


@router.delete("/tarifas/reglas/{regla_id}", tags=["Tarifas"], status_code=204)
def eliminar_regla(regla_id: UUID):
    with get_db() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT id FROM reglas_tarifa WHERE id=%s", (str(regla_id),))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Regla no encontrada")
            cursor.execute("DELETE FROM reglas_tarifa WHERE id=%s", (str(regla_id),))
        conexion.commit()
    return Response(status_code=204)


def _guardar_movimiento(
    pago_id: str,
    tipo: str,
    monto: float,
    actor: str = "sistema",
    detalle: Optional[str] = None,
    conexion: Any = None,
) -> Dict[str, Any]:
    movimiento_id = str(uuid4())
    propio = conexion is None
    db = get_db() if propio else None
    db = db.__enter__() if db else conexion
    try:
        with db.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO movimientos_contrato (id, pago_id, tipo, monto, actor, detalle)
                VALUES (%s,%s,%s,%s,%s,%s)
                """,
                (movimiento_id, pago_id, tipo, _redondear(monto), actor, detalle),
            )
        if propio:
            db.commit()
    finally:
        if propio:
            db.close()
    return {
        "id": movimiento_id,
        "pago_id": pago_id,
        "tipo": tipo,
        "monto": _redondear(monto),
        "fecha": _ahora(),
        "actor": actor,
        "detalle": detalle,
    }


def _obtener_pago(pago_id: str) -> Optional[Dict[str, Any]]:
    with get_db() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT * FROM pagos_contrato WHERE id=%s", (pago_id,))
            fila = cursor.fetchone()
    return _row_json(fila) if fila else None


def _pago_response(fila: Dict[str, Any]) -> Dict[str, Any]:
    fila = _row_json(fila)
    for campo in ("viaje_id", "reserva_id", "beneficiario_id", "referencia_externa"):
        if fila.get(campo) in ("", None):
            fila.pop(campo, None)
    fila["monto"] = _redondear(fila["monto"])
    fila["monto_reembolsado"] = _redondear(fila["monto_reembolsado"])
    fila["creado_en"] = _iso(fila["creado_en"])
    fila["actualizado_en"] = _iso(fila["actualizado_en"])
    return fila


@router.post("/pagos", tags=["Pagos"], status_code=201)
def crear_pago(
    datos: PagoNuevo,
    response: Response,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
) -> Dict[str, Any]:
    if len(idempotency_key) > 255:
        raise HTTPException(status_code=422, detail="Idempotency-Key es demasiado larga")
    repetida = _idempotencia(idempotency_key, "/api/v1/pagos", datos, response)
    if repetida is not None:
        return repetida
    viaje_key = str(datos.viaje_id)
    with get_db() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT desglose FROM tarifas_finales WHERE viaje_id=%s", (viaje_key,))
            tarifa = cursor.fetchone()
    if not tarifa:
        raise HTTPException(status_code=422, detail="El viaje no tiene tarifa final registrada")
    desglose = tarifa["desglose"]
    if isinstance(desglose, bytes):
        desglose = json.loads(desglose.decode("utf-8"))
    elif isinstance(desglose, str):
        desglose = json.loads(desglose)
    if _redondear(desglose["total"]) != _redondear(datos.monto):
        raise HTTPException(status_code=422, detail="El monto no coincide con la tarifa final")

    pago_id = str(uuid4())
    estado = "aprobado" if datos.metodo == "efectivo" else "pendiente"
    referencia = None if datos.metodo == "efectivo" else f"pasarela-{pago_id}"
    with get_db() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO pagos_contrato
                (id, concepto, viaje_id, reserva_id, cliente_id, beneficiario_id, monto,
                 monto_reembolsado, moneda, metodo, estado, referencia_externa)
                VALUES (%s,'viaje',%s,%s,%s,%s,%s,0,'ARS',%s,%s,%s)
                """,
                (pago_id, viaje_key, str(datos.reserva_id) if datos.reserva_id else None,
                 str(datos.cliente_id), str(datos.beneficiario_id), _redondear(datos.monto),
                 datos.metodo, estado, referencia),
            )
            _guardar_movimiento(pago_id, "registro", datos.monto, conexion=conexion)
            if estado == "aprobado":
                _guardar_movimiento(pago_id, "aprobacion", datos.monto, conexion=conexion)
        conexion.commit()
    pago = _obtener_pago(pago_id)
    pago = _pago_response(pago)
    _guardar_idempotencia(idempotency_key, "/api/v1/pagos", datos, pago)
    response.headers["Location"] = f"/api/v1/pagos/{pago_id}"
    return pago


@router.get("/pagos", tags=["Pagos"])
def listar_pagos(
    viaje_id: Optional[UUID] = None,
    cliente_id: Optional[UUID] = None,
    beneficiario_id: Optional[UUID] = None,
    estado: Optional[str] = None,
    page: int = 0,
    size: int = 20,
) -> Dict[str, Any]:
    consulta = "SELECT * FROM pagos_contrato WHERE 1=1"
    parametros: List[Any] = []
    for campo, valor in (("viaje_id", viaje_id), ("cliente_id", cliente_id),
                         ("beneficiario_id", beneficiario_id), ("estado", estado)):
        if valor is not None:
            consulta += f" AND {campo}=%s"
            parametros.append(str(valor) if isinstance(valor, UUID) else valor)
    consulta += " ORDER BY creado_en DESC"
    with get_db() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(consulta, parametros)
            items = [_pago_response(fila) for fila in cursor.fetchall()]
    return _pagina(items, page, size)


@router.get("/pagos/{pago_id}", tags=["Pagos"])
def obtener_pago(pago_id: UUID) -> Dict[str, Any]:
    pago = _obtener_pago(str(pago_id))
    if pago is None:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    return _pago_response(pago)


@router.get("/pagos/{pago_id}/movimientos", tags=["Historial"])
def listar_movimientos(pago_id: UUID, page: int = 0, size: int = 20) -> Dict[str, Any]:
    pago_key = str(pago_id)
    if _obtener_pago(pago_key) is None:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    with get_db() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM movimientos_contrato WHERE pago_id=%s ORDER BY fecha ASC",
                (pago_key,),
            )
            items = [_row_json(fila) for fila in cursor.fetchall()]
    return _pagina(items, page, size)


@router.post("/pagos/{pago_id}/reembolsos", tags=["Reembolsos"])
def crear_reembolso(
    pago_id: UUID,
    datos: ReembolsoNuevo,
    response: Response,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
) -> Dict[str, Any]:
    ruta = f"/api/v1/pagos/{pago_id}/reembolsos"
    repetida = _idempotencia(idempotency_key, ruta, datos, response)
    if repetida is not None:
        return repetida
    pago_key = str(pago_id)
    pago = _obtener_pago(pago_key)
    if pago is None:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    if pago["estado"] not in ("aprobado", "reembolsado_parcial"):
        raise HTTPException(status_code=409, detail="El pago no admite reembolsos")
    disponible = _redondear(float(pago["monto"]) - float(pago["monto_reembolsado"]))
    monto = disponible if datos.monto is None else _redondear(datos.monto)
    if monto > disponible:
        raise HTTPException(status_code=422, detail="El monto supera el disponible para reembolsar")
    reembolso_id = str(uuid4())
    nuevo_reembolsado = _redondear(float(pago["monto_reembolsado"]) + monto)
    estado = "reembolsado" if nuevo_reembolsado == _redondear(pago["monto"]) else "reembolsado_parcial"
    with get_db() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(
                "INSERT INTO reembolsos_contrato (id,pago_id,monto,motivo) VALUES (%s,%s,%s,%s)",
                (reembolso_id, pago_key, monto, datos.motivo),
            )
            cursor.execute(
                "UPDATE pagos_contrato SET monto_reembolsado=%s, estado=%s WHERE id=%s",
                (nuevo_reembolsado, estado, pago_key),
            )
            _guardar_movimiento(pago_key, "reembolso", monto, detalle=datos.motivo, conexion=conexion)
        conexion.commit()
    reembolso = {
        "id": reembolso_id,
        "pago_id": pago_key,
        "monto": monto,
        "motivo": datos.motivo,
        "creado_en": _ahora(),
    }
    _guardar_idempotencia(idempotency_key, ruta, datos, reembolso)
    response.headers["Location"] = f"{ruta}/{reembolso_id}"
    return reembolso


@router.get("/pagos/{pago_id}/reembolsos", tags=["Reembolsos"])
def listar_reembolsos(pago_id: UUID, page: int = 0, size: int = 20) -> Dict[str, Any]:
    pago_key = str(pago_id)
    if _obtener_pago(pago_key) is None:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    with get_db() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM reembolsos_contrato WHERE pago_id=%s ORDER BY creado_en ASC",
                (pago_key,),
            )
            items = [_row_json(fila) for fila in cursor.fetchall()]
    return _pagina(items, page, size)


@router.post("/pagos/webhooks/pasarela", tags=["Pagos"])
def webhook_pasarela(datos: AvisoPasarela) -> Dict[str, Any]:
    pago_key = str(datos.pago_id)
    pago = _obtener_pago(pago_key)
    if pago is None:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    if pago["estado"] != "pendiente":
        raise HTTPException(status_code=409, detail="El pago ya fue procesado por la pasarela")
    with get_db() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(
                "UPDATE pagos_contrato SET estado=%s, referencia_externa=%s WHERE id=%s",
                (datos.estado, datos.referencia_externa, pago_key),
            )
            _guardar_movimiento(
                pago_key,
                "aprobacion" if datos.estado == "aprobado" else "rechazo",
                pago["monto"],
                actor="pasarela",
                conexion=conexion,
            )
        conexion.commit()
    return _pago_response(_obtener_pago(pago_key))


@router.post("/cargos-cancelacion", tags=["Cancelaciones"])
def crear_cargo_cancelacion(
    datos: CargoCancelacionNuevo,
    response: Response,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
) -> Dict[str, Any]:
    repetida = _idempotencia(idempotency_key, "/api/v1/cargos-cancelacion", datos, response)
    if repetida is not None:
        return repetida
    with get_db() as conexion:
        with conexion.cursor() as cursor:
            regla = _regla_activa(datos.tipo_vehiculo, cursor)
    if not regla or _redondear(regla["cargo_cancelacion"]) <= 0:
        raise HTTPException(status_code=422, detail="No hay cargo de cancelacion activo")
    monto = _redondear(regla["cargo_cancelacion"])
    pago_id = str(uuid4())
    with get_db() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO pagos_contrato
                (id, concepto, viaje_id, reserva_id, cliente_id, beneficiario_id, monto,
                 monto_reembolsado, moneda, metodo, estado, referencia_externa)
                VALUES (%s,'cargo_cancelacion',%s,%s,%s,NULL,%s,0,'ARS',%s,'pendiente',%s)
                """,
                (pago_id, str(datos.viaje_id) if datos.viaje_id else None,
                 str(datos.reserva_id) if datos.reserva_id else None,
                 str(datos.cliente_id), monto, datos.metodo, f"pasarela-{pago_id}"),
            )
            _guardar_movimiento(pago_id, "cargo_cancelacion", monto, conexion=conexion)
        conexion.commit()
    pago = _pago_response(_obtener_pago(pago_id))
    _guardar_idempotencia(idempotency_key, "/api/v1/cargos-cancelacion", datos, pago)
    response.headers["Location"] = f"/api/v1/pagos/{pago_id}"
    return pago


@router.post("/liquidaciones", tags=["Liquidaciones"], status_code=201)
def crear_liquidacion(datos: LiquidacionNueva, response: Response) -> Dict[str, Any]:
    if datos.periodo_hasta < datos.periodo_desde:
        raise HTTPException(status_code=422, detail="periodo_hasta debe ser posterior a periodo_desde")
    beneficiario = str(datos.beneficiario_id)
    with get_db() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT p.* FROM pagos_contrato p
                WHERE p.beneficiario_id=%s
                  AND DATE(p.creado_en) BETWEEN %s AND %s
                  AND p.estado IN ('aprobado', 'reembolsado_parcial')
                  AND NOT EXISTS (
                    SELECT 1 FROM liquidaciones_contrato l
                    WHERE l.estado <> 'anulada'
                      AND JSON_CONTAINS(COALESCE(l.pago_ids, JSON_ARRAY()), JSON_QUOTE(p.id))
                  )
                ORDER BY p.creado_en ASC
                """,
                (beneficiario, datos.periodo_desde, datos.periodo_hasta),
            )
            incluidos = [_pago_response(fila) for fila in cursor.fetchall()]
    if not incluidos:
        raise HTTPException(status_code=422, detail="No hay pagos para liquidar")

    bruto = sum(float(pago["monto"]) - float(pago["monto_reembolsado"]) for pago in incluidos)
    efectivo = sum(
        float(pago["monto"]) - float(pago["monto_reembolsado"])
        for pago in incluidos if pago["metodo"] == "efectivo"
    )
    comision = _redondear(bruto * 0.20)
    liquidacion_id = str(uuid4())
    liquidacion = {
        "id": liquidacion_id,
        "beneficiario_id": beneficiario,
        "periodo_desde": datos.periodo_desde.isoformat(),
        "periodo_hasta": datos.periodo_hasta.isoformat(),
        "pago_ids": [pago["id"] for pago in incluidos],
        "monto_bruto": _redondear(bruto),
        "comision_plataforma": comision,
        "cobrado_en_efectivo": _redondear(efectivo),
        "monto_neto": _redondear(bruto - comision - efectivo),
        "moneda": "ARS",
        "estado": "pendiente",
        "creada_en": _ahora(),
        "actualizada_en": _ahora(),
    }
    with get_db() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO liquidaciones_contrato
                (id, beneficiario_id, periodo_desde, periodo_hasta, pago_ids, monto_bruto,
                 comision_plataforma, cobrado_en_efectivo, monto_neto, moneda, estado)
                VALUES (%s,%s,%s,%s,CAST(%s AS JSON),%s,%s,%s,%s,'ARS','pendiente')
                """,
                (liquidacion_id, beneficiario, datos.periodo_desde, datos.periodo_hasta,
                 json.dumps(liquidacion["pago_ids"]), liquidacion["monto_bruto"],
                 liquidacion["comision_plataforma"], liquidacion["cobrado_en_efectivo"],
                 liquidacion["monto_neto"]),
            )
        conexion.commit()
    response.headers["Location"] = f"/api/v1/liquidaciones/{liquidacion_id}"
    return liquidacion


@router.get("/liquidaciones", tags=["Liquidaciones"])
def listar_liquidaciones(
    beneficiario_id: Optional[UUID] = None,
    estado: Optional[str] = None,
    page: int = 0,
    size: int = 20,
) -> Dict[str, Any]:
    consulta = "SELECT * FROM liquidaciones_contrato WHERE 1=1"
    parametros: List[Any] = []
    if beneficiario_id is not None:
        consulta += " AND beneficiario_id=%s"
        parametros.append(str(beneficiario_id))
    if estado is not None:
        consulta += " AND estado=%s"
        parametros.append(estado)
    consulta += " ORDER BY creada_en DESC"
    with get_db() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(consulta, parametros)
            items = [_liquidacion_response(fila) for fila in cursor.fetchall()]
    return _pagina(items, page, size)


def _liquidacion_response(fila: Dict[str, Any]) -> Dict[str, Any]:
    resultado = _row_json(fila)
    pago_ids = resultado["pago_ids"]
    if isinstance(pago_ids, bytes):
        pago_ids = json.loads(pago_ids.decode("utf-8"))
    elif isinstance(pago_ids, str):
        pago_ids = json.loads(pago_ids)
    resultado["pago_ids"] = pago_ids
    for campo in ("monto_bruto", "comision_plataforma", "cobrado_en_efectivo", "monto_neto"):
        resultado[campo] = _redondear(resultado[campo])
    resultado["periodo_desde"] = str(resultado["periodo_desde"])
    resultado["periodo_hasta"] = str(resultado["periodo_hasta"])
    resultado["creada_en"] = _iso(resultado["creada_en"])
    resultado["actualizada_en"] = _iso(resultado["actualizada_en"])
    if resultado.get("referencia_transferencia") in ("", None):
        resultado.pop("referencia_transferencia", None)
    return resultado


@router.get("/liquidaciones/saldos/{beneficiario_id}", tags=["Liquidaciones"])
def obtener_saldo(beneficiario_id: UUID) -> Dict[str, Any]:
    beneficiario = str(beneficiario_id)
    with get_db() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(
                """
                SELECT COALESCE(SUM(monto - monto_reembolsado), 0) AS saldo
                FROM pagos_contrato
                WHERE beneficiario_id=%s
                  AND estado IN ('aprobado', 'reembolsado_parcial')
                  AND NOT EXISTS (
                    SELECT 1 FROM liquidaciones_contrato l
                    WHERE l.estado <> 'anulada'
                      AND JSON_CONTAINS(COALESCE(l.pago_ids, JSON_ARRAY()), JSON_QUOTE(pagos_contrato.id))
                  )
                """,
                (beneficiario,),
            )
            pendiente = cursor.fetchone()["saldo"]
            cursor.execute(
                "SELECT monto_neto, estado FROM liquidaciones_contrato WHERE beneficiario_id=%s",
                (beneficiario,),
            )
            liquidaciones = cursor.fetchall()
    pendiente_transferir = sum(
        float(fila["monto_neto"]) for fila in liquidaciones if fila["estado"] == "pendiente"
    )
    total_transferido = sum(
        float(fila["monto_neto"]) for fila in liquidaciones if fila["estado"] == "transferida"
    )
    return {
        "beneficiario_id": beneficiario,
        "saldo_pendiente_liquidar": _redondear(pendiente),
        "liquidado_pendiente_transferir": _redondear(pendiente_transferir),
        "total_transferido": _redondear(total_transferido),
        "moneda": "ARS",
    }


@router.get("/liquidaciones/{liquidacion_id}", tags=["Liquidaciones"])
def obtener_liquidacion(liquidacion_id: UUID) -> Dict[str, Any]:
    with get_db() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT * FROM liquidaciones_contrato WHERE id=%s", (str(liquidacion_id),))
            fila = cursor.fetchone()
    if not fila:
        raise HTTPException(status_code=404, detail="Liquidacion no encontrada")
    return _liquidacion_response(fila)


@router.post("/liquidaciones/{liquidacion_id}/transferencia", tags=["Liquidaciones"])
def registrar_transferencia(liquidacion_id: UUID, datos: TransferenciaNueva) -> Dict[str, Any]:
    liquidacion_key = str(liquidacion_id)
    with get_db() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT estado FROM liquidaciones_contrato WHERE id=%s",
                (liquidacion_key,),
            )
            liquidacion = cursor.fetchone()
            if not liquidacion:
                raise HTTPException(status_code=404, detail="Liquidacion no encontrada")
            if liquidacion["estado"] != "pendiente":
                raise HTTPException(status_code=409, detail="Solo se transfiere una liquidacion pendiente")
            cursor.execute(
                """
                UPDATE liquidaciones_contrato
                SET estado='transferida', referencia_transferencia=%s
                WHERE id=%s
                """,
                (datos.referencia_transferencia, liquidacion_key),
            )
            cursor.execute("SELECT * FROM liquidaciones_contrato WHERE id=%s", (liquidacion_key,))
            actualizada = cursor.fetchone()
        conexion.commit()
    return _liquidacion_response(actualizada)


@router.post("/liquidaciones/{liquidacion_id}/anulacion", tags=["Liquidaciones"])
def anular_liquidacion(liquidacion_id: UUID) -> Dict[str, Any]:
    liquidacion_key = str(liquidacion_id)
    with get_db() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT estado FROM liquidaciones_contrato WHERE id=%s",
                (liquidacion_key,),
            )
            liquidacion = cursor.fetchone()
            if not liquidacion:
                raise HTTPException(status_code=404, detail="Liquidacion no encontrada")
            if liquidacion["estado"] != "pendiente":
                raise HTTPException(status_code=409, detail="Solo se puede anular una liquidacion pendiente")
            cursor.execute(
                "UPDATE liquidaciones_contrato SET estado='anulada' WHERE id=%s",
                (liquidacion_key,),
            )
            cursor.execute("SELECT * FROM liquidaciones_contrato WHERE id=%s", (liquidacion_key,))
            actualizada = cursor.fetchone()
        conexion.commit()
    return _liquidacion_response(actualizada)
