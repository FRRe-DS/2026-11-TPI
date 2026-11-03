from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL

from fastapi import APIRouter, Header, HTTPException, Response

from app.schemas.tarifas import (
    EstimacionNueva,
    ReglaTarifaCambios,
    ReglaTarifaNueva,
    TarifaFinalNueva,
)
from app.schemas.pagos import (
    AvisoPasarela,
    CargoCancelacionNuevo,
    PagoNuevo,
    ReembolsoNuevo,
)
from app.schemas.liquidaciones import LiquidacionNueva, TransferenciaNueva
from app.services.tarifas import obtener_todos_los_parametros

router = APIRouter(prefix="/api/v1", tags=["Contrato OpenAPI"])
tarifas_finales: Dict[str, Dict[str, Any]] = {}
reglas: Dict[str, Dict[str, Any]] = {}
pagos: Dict[str, Dict[str, Any]] = {}
movimientos: Dict[str, List[Dict[str, Any]]] = {}
reembolsos: Dict[str, List[Dict[str, Any]]] = {}
liquidaciones: Dict[str, Dict[str, Any]] = {}


def _redondear(valor: float) -> float:
    return float(Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


@router.post("/tarifas/estimaciones", tags=["Tarifas"], status_code=200)
def estimar_tarifa(datos: EstimacionNueva) -> Dict[str, Any]:
    parametro = next(
        (
            item
            for item in obtener_todos_los_parametros()
            if item["tipo_vehiculo"] == datos.tipo_vehiculo
        ),
        None,
    )
    if parametro is None:
        raise HTTPException(status_code=422, detail="No existe una regla activa para el tipo de vehiculo")

    tarifa_base = _redondear(float(parametro["base"]))
    cargo_distancia = _redondear(float(parametro["por_km"]) * datos.distancia_km)
    cargo_tiempo = _redondear(float(parametro["por_min"]) * datos.duracion_estimada_min)
    subtotal = _redondear((tarifa_base + cargo_distancia + cargo_tiempo) * datos.multiplicador_demanda)
    total = _redondear(max(subtotal, float(parametro["minima"])))

    return {
        "regla_id": str(parametro.get("id") or uuid5(NAMESPACE_URL, f"m7-regla-{datos.tipo_vehiculo}")),
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
    if viaje_key in tarifas_finales:
        raise HTTPException(status_code=409, detail="La tarifa final del viaje ya fue registrada")

    estimacion = estimar_tarifa(
        EstimacionNueva(
            tipo_vehiculo=datos.tipo_vehiculo,
            distancia_km=datos.distancia_real_km,
            duracion_estimada_min=datos.duracion_real_min,
            multiplicador_demanda=datos.multiplicador_demanda,
        )
    )
    tarifa = {
        "viaje_id": viaje_key,
        "regla_id": estimacion["regla_id"],
        "moneda": "ARS",
        "desglose": estimacion["desglose"],
        "calculada_en": datetime.now(timezone.utc).isoformat(),
    }
    tarifas_finales[viaje_key] = tarifa
    return tarifa


@router.get("/tarifas/viajes/{viaje_id}/tarifa-final", tags=["Tarifas"])
def obtener_tarifa_final(viaje_id: UUID) -> Dict[str, Any]:
    tarifa = tarifas_finales.get(str(viaje_id))
    if tarifa is None:
        raise HTTPException(status_code=404, detail="El viaje no tiene tarifa final")
    return tarifa


def _pagina(items: List[Dict[str, Any]], page: int, size: int) -> Dict[str, Any]:
    inicio = page * size
    contenido = items[inicio:inicio + size]
    total_paginas = (len(items) + size - 1) // size
    return {
        "pagina": page,
        "tamano": size,
        "total_elementos": len(items),
        "total_paginas": total_paginas,
        "items": contenido,
    }


@router.get("/tarifas/reglas", tags=["Tarifas"])
def listar_reglas(
    tipo_vehiculo: Optional[str] = None,
    solo_activas: bool = False,
    page: int = 0,
    size: int = 20,
) -> Dict[str, Any]:
    items = list(reglas.values())
    if tipo_vehiculo:
        items = [item for item in items if item["tipo_vehiculo"] == tipo_vehiculo]
    if solo_activas:
        items = [item for item in items if item["activa"]]
    return _pagina(items, page, size)


@router.post("/tarifas/reglas", tags=["Tarifas"], status_code=201)
def crear_regla(datos: ReglaTarifaNueva, response: Response) -> Dict[str, Any]:
    regla_id = str(uuid4())
    if datos.activa:
        for regla in reglas.values():
            if regla["tipo_vehiculo"] == datos.tipo_vehiculo:
                regla["activa"] = False
    regla = {"id": regla_id, **datos.model_dump()}
    reglas[regla_id] = regla
    response.headers["Location"] = f"/api/v1/tarifas/reglas/{regla_id}"
    return regla


@router.get("/tarifas/reglas/{regla_id}", tags=["Tarifas"])
def obtener_regla(regla_id: UUID) -> Dict[str, Any]:
    regla = reglas.get(str(regla_id))
    if regla is None:
        raise HTTPException(status_code=404, detail="Regla no encontrada")
    return regla


@router.patch("/tarifas/reglas/{regla_id}", tags=["Tarifas"])
def modificar_regla(regla_id: UUID, datos: ReglaTarifaCambios) -> Dict[str, Any]:
    regla = reglas.get(str(regla_id))
    if regla is None:
        raise HTTPException(status_code=404, detail="Regla no encontrada")
    cambios = datos.model_dump(exclude_unset=True)
    if cambios.get("activa") is True:
        for otra in reglas.values():
            if otra["tipo_vehiculo"] == regla["tipo_vehiculo"] and otra["id"] != regla["id"]:
                otra["activa"] = False
    regla.update(cambios)
    return regla


@router.delete("/tarifas/reglas/{regla_id}", tags=["Tarifas"], status_code=204)
def eliminar_regla(regla_id: UUID):
    if str(regla_id) not in reglas:
        raise HTTPException(status_code=404, detail="Regla no encontrada")
    del reglas[str(regla_id)]
    return Response(status_code=204)


def _movimiento(pago_id: str, tipo: str, monto: float, actor: str = "sistema", detalle: Optional[str] = None):
    movimiento = {
        "id": str(uuid4()),
        "pago_id": pago_id,
        "tipo": tipo,
        "monto": _redondear(monto),
        "fecha": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "detalle": detalle,
    }
    movimientos.setdefault(pago_id, []).append(movimiento)
    return movimiento


def _pago(datos: Dict[str, Any]) -> Dict[str, Any]:
    ahora = datetime.now(timezone.utc).isoformat()
    pago_id = datos["id"]
    pago = {
        "id": pago_id,
        "concepto": datos.get("concepto", "viaje"),
        "viaje_id": str(datos["viaje_id"]) if datos.get("viaje_id") else None,
        "reserva_id": str(datos["reserva_id"]) if datos.get("reserva_id") else None,
        "cliente_id": str(datos["cliente_id"]),
        "beneficiario_id": str(datos["beneficiario_id"]) if datos.get("beneficiario_id") else None,
        "monto": _redondear(datos["monto"]),
        "monto_reembolsado": _redondear(datos.get("monto_reembolsado", 0)),
        "moneda": "ARS",
        "metodo": datos["metodo"],
        "estado": datos["estado"],
        "referencia_externa": datos.get("referencia_externa"),
        "creado_en": datos.get("creado_en", ahora),
        "actualizado_en": ahora,
    }
    return {clave: valor for clave, valor in pago.items() if valor is not None}


@router.post("/pagos", tags=["Pagos"], status_code=201)
def crear_pago(datos: PagoNuevo, response: Response, idempotency_key: str = Header(..., alias="Idempotency-Key")) -> Dict[str, Any]:
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Idempotency-Key es obligatorio")
    viaje = str(datos.viaje_id)
    tarifa = tarifas_finales.get(viaje)
    if tarifa is None or _redondear(tarifa["desglose"]["total"]) != _redondear(datos.monto):
        raise HTTPException(status_code=422, detail="El monto no coincide con la tarifa final")
    pago_id = str(uuid4())
    estado = "aprobado" if datos.metodo == "efectivo" else "pendiente"
    referencia = None if datos.metodo == "efectivo" else f"pasarela-{pago_id}"
    pagos[pago_id] = _pago({
        "id": pago_id,
        "viaje_id": datos.viaje_id,
        "reserva_id": datos.reserva_id,
        "cliente_id": datos.cliente_id,
        "beneficiario_id": datos.beneficiario_id,
        "monto": datos.monto,
        "metodo": datos.metodo,
        "estado": estado,
        "referencia_externa": referencia,
    })
    _movimiento(pago_id, "registro", datos.monto)
    if estado == "aprobado":
        _movimiento(pago_id, "aprobacion", datos.monto)
    response.headers["Location"] = f"/api/v1/pagos/{pago_id}"
    return pagos[pago_id]


@router.get("/pagos", tags=["Pagos"])
def listar_pagos(
    viaje_id: Optional[UUID] = None,
    cliente_id: Optional[UUID] = None,
    beneficiario_id: Optional[UUID] = None,
    estado: Optional[str] = None,
    page: int = 0,
    size: int = 20,
) -> Dict[str, Any]:
    items = list(pagos.values())
    if viaje_id:
        items = [item for item in items if item.get("viaje_id") == str(viaje_id)]
    if cliente_id:
        items = [item for item in items if item["cliente_id"] == str(cliente_id)]
    if beneficiario_id:
        items = [item for item in items if item.get("beneficiario_id") == str(beneficiario_id)]
    if estado:
        items = [item for item in items if item["estado"] == estado]
    return _pagina(items, page, size)


@router.get("/pagos/{pago_id}", tags=["Pagos"])
def obtener_pago(pago_id: UUID) -> Dict[str, Any]:
    pago = pagos.get(str(pago_id))
    if pago is None:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    return pago


@router.get("/pagos/{pago_id}/movimientos", tags=["Historial"])
def listar_movimientos(pago_id: UUID, page: int = 0, size: int = 20) -> Dict[str, Any]:
    if str(pago_id) not in pagos:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    return _pagina(movimientos.get(str(pago_id), []), page, size)


@router.post("/pagos/{pago_id}/reembolsos", tags=["Reembolsos"])
def crear_reembolso(
    pago_id: UUID,
    datos: ReembolsoNuevo,
    response: Response,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
) -> Dict[str, Any]:
    pago = pagos.get(str(pago_id))
    if pago is None:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    if pago["estado"] not in ["aprobado", "reembolsado_parcial"]:
        raise HTTPException(status_code=409, detail="El pago no admite reembolsos")
    disponible = pago["monto"] - pago["monto_reembolsado"]
    monto = disponible if datos.monto is None else datos.monto
    if monto > disponible:
        raise HTTPException(status_code=422, detail="El monto supera el disponible para reembolsar")
    pago["monto_reembolsado"] = _redondear(pago["monto_reembolsado"] + monto)
    pago["estado"] = "reembolsado" if pago["monto_reembolsado"] == pago["monto"] else "reembolsado_parcial"
    reembolso = {
        "id": str(uuid4()),
        "pago_id": str(pago_id),
        "monto": _redondear(monto),
        "motivo": datos.motivo,
        "creado_en": datetime.now(timezone.utc).isoformat(),
    }
    reembolsos.setdefault(str(pago_id), []).append(reembolso)
    _movimiento(str(pago_id), "reembolso", monto, detalle=datos.motivo)
    response.headers["Location"] = f"/api/v1/pagos/{pago_id}/reembolsos/{reembolso['id']}"
    return reembolso


@router.get("/pagos/{pago_id}/reembolsos", tags=["Reembolsos"])
def listar_reembolsos(pago_id: UUID, page: int = 0, size: int = 20) -> Dict[str, Any]:
    if str(pago_id) not in pagos:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    return _pagina(reembolsos.get(str(pago_id), []), page, size)


@router.post("/pagos/webhooks/pasarela", tags=["Pagos"])
def webhook_pasarela(datos: AvisoPasarela) -> Dict[str, Any]:
    pago = pagos.get(str(datos.pago_id))
    if pago is None:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    pago["estado"] = datos.estado
    pago["referencia_externa"] = datos.referencia_externa
    _movimiento(str(datos.pago_id), "aprobacion" if datos.estado == "aprobado" else "rechazo", pago["monto"], "pasarela")
    return pago


@router.post("/cargos-cancelacion", tags=["Cancelaciones"])
def crear_cargo_cancelacion(
    datos: CargoCancelacionNuevo,
    response: Response,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
) -> Dict[str, Any]:
    regla = next(
        (item for item in reglas.values() if item["tipo_vehiculo"] == datos.tipo_vehiculo and item["activa"]),
        None,
    )
    monto = float(regla["cargo_cancelacion"]) if regla else 0
    if monto <= 0:
        raise HTTPException(status_code=422, detail="No hay cargo de cancelacion activo")
    pago_id = str(uuid4())
    ahora = datetime.now(timezone.utc).isoformat()
    pagos[pago_id] = _pago({
        "id": pago_id,
        "concepto": "cargo_cancelacion",
        "viaje_id": datos.viaje_id,
        "reserva_id": datos.reserva_id,
        "cliente_id": datos.cliente_id,
        "monto": monto,
        "metodo": datos.metodo,
        "estado": "pendiente",
        "referencia_externa": f"pasarela-{pago_id}",
        "creado_en": ahora,
    })
    _movimiento(pago_id, "registro", monto)
    response.headers["Location"] = f"/api/v1/pagos/{pago_id}"
    return pagos[pago_id]


@router.post("/liquidaciones", tags=["Liquidaciones"], status_code=201)
def crear_liquidacion(datos: LiquidacionNueva, response: Response) -> Dict[str, Any]:
    if datos.periodo_hasta < datos.periodo_desde:
        raise HTTPException(status_code=422, detail="periodo_hasta debe ser posterior a periodo_desde")
    incluidos = [
        pago for pago in pagos.values()
        if pago.get("beneficiario_id") == str(datos.beneficiario_id)
        and pago["estado"] in ["aprobado", "reembolsado_parcial"]
    ]
    if not incluidos:
        raise HTTPException(status_code=422, detail="No hay pagos para liquidar")
    bruto = sum(pago["monto"] - pago["monto_reembolsado"] for pago in incluidos)
    efectivo = sum(pago["monto"] - pago["monto_reembolsado"] for pago in incluidos if pago["metodo"] == "efectivo")
    comision = _redondear(bruto * 0.20)
    neto = _redondear(bruto - comision - efectivo)
    liquidacion_id = str(uuid4())
    liquidacion = {
        "id": liquidacion_id,
        "beneficiario_id": str(datos.beneficiario_id),
        "periodo_desde": datos.periodo_desde.isoformat(),
        "periodo_hasta": datos.periodo_hasta.isoformat(),
        "pago_ids": [pago["id"] for pago in incluidos],
        "monto_bruto": _redondear(bruto),
        "comision_plataforma": comision,
        "cobrado_en_efectivo": _redondear(efectivo),
        "monto_neto": neto,
        "moneda": "ARS",
        "estado": "pendiente",
        "creada_en": datetime.now(timezone.utc).isoformat(),
        "actualizada_en": datetime.now(timezone.utc).isoformat(),
    }
    liquidaciones[liquidacion_id] = liquidacion
    response.headers["Location"] = f"/api/v1/liquidaciones/{liquidacion_id}"
    return liquidacion


@router.get("/liquidaciones", tags=["Liquidaciones"])
def listar_liquidaciones(beneficiario_id: Optional[UUID] = None, estado: Optional[str] = None, page: int = 0, size: int = 20):
    items = list(liquidaciones.values())
    if beneficiario_id:
        items = [item for item in items if item["beneficiario_id"] == str(beneficiario_id)]
    if estado:
        items = [item for item in items if item["estado"] == estado]
    return _pagina(items, page, size)


@router.get("/liquidaciones/saldos/{beneficiario_id}", tags=["Liquidaciones"])
def obtener_saldo(beneficiario_id: UUID):
    pendientes = [p for p in pagos.values() if p.get("beneficiario_id") == str(beneficiario_id) and p["estado"] in ["aprobado", "reembolsado_parcial"]]
    pendientes_liquidar = sum(p["monto"] - p["monto_reembolsado"] for p in pendientes)
    liquidaciones_beneficiario = [l for l in liquidaciones.values() if l["beneficiario_id"] == str(beneficiario_id)]
    pendiente_transferir = sum(l["monto_neto"] for l in liquidaciones_beneficiario if l["estado"] == "pendiente")
    transferido = sum(l["monto_neto"] for l in liquidaciones_beneficiario if l["estado"] == "transferida")
    return {
        "beneficiario_id": str(beneficiario_id),
        "saldo_pendiente_liquidar": _redondear(pendientes_liquidar),
        "liquidado_pendiente_transferir": _redondear(pendiente_transferir),
        "total_transferido": _redondear(transferido),
        "moneda": "ARS",
    }


@router.get("/liquidaciones/{liquidacion_id}", tags=["Liquidaciones"])
def obtener_liquidacion(liquidacion_id: UUID):
    liquidacion = liquidaciones.get(str(liquidacion_id))
    if liquidacion is None:
        raise HTTPException(status_code=404, detail="Liquidacion no encontrada")
    return liquidacion


@router.post("/liquidaciones/{liquidacion_id}/transferencia", tags=["Liquidaciones"])
def registrar_transferencia(liquidacion_id: UUID, datos: TransferenciaNueva):
    liquidacion = liquidaciones.get(str(liquidacion_id))
    if liquidacion is None:
        raise HTTPException(status_code=404, detail="Liquidacion no encontrada")
    if liquidacion["estado"] != "pendiente":
        raise HTTPException(status_code=409, detail="Solo se transfiere una liquidacion pendiente")
    liquidacion["estado"] = "transferida"
    liquidacion["referencia_transferencia"] = datos.referencia_transferencia
    liquidacion["actualizada_en"] = datetime.now(timezone.utc).isoformat()
    return liquidacion


@router.post("/liquidaciones/{liquidacion_id}/anulacion", tags=["Liquidaciones"])
def anular_liquidacion(liquidacion_id: UUID):
    liquidacion = liquidaciones.get(str(liquidacion_id))
    if liquidacion is None:
        raise HTTPException(status_code=404, detail="Liquidacion no encontrada")
    if liquidacion["estado"] != "pendiente":
        raise HTTPException(status_code=409, detail="Solo se puede anular una liquidacion pendiente")
    liquidacion["estado"] = "anulada"
    liquidacion["actualizada_en"] = datetime.now(timezone.utc).isoformat()
    return liquidacion
