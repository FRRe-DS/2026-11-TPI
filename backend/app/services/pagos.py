"""Cobros de viaje: autorización al asignarse el viaje y captura al finalizar (RF-7.3).

Las llamadas a la pasarela se hacen fuera de la transacción que reserva el
cobro, con timeout: si no hay respuesta el pago queda en un estado explícito
(pendiente_confirmacion o captura_pendiente) que se resuelve por webhook.
"""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import conflicto, no_encontrado, no_procesable
from app.core.security import Usuario
from app.db import models
from app.schemas.movimientos import TipoMovimiento
from app.schemas.pagos import (
    CapturaRequest,
    EstadoPago,
    Pago,
    PagoCreate,
    Reembolso,
    ReembolsoCreate,
    TipoMetodoPago,
    TipoOperacion,
    WebhookPasarela,
)
from app.services import idempotencia, movimientos
from app.services.integraciones import DependenciaNoDisponible, ReservasM9
from app.services.pasarela import PasarelaNoDisponible, PasarelaPagos, con_timeout

E = EstadoPago
ESTADOS_COBRADOS = {E.capturado, E.reembolsado_parcial}

# Transiciones válidas del pago; el historial completo queda en movimientos_financieros
TRANSICIONES: dict[EstadoPago, set[EstadoPago]] = {
    E.pendiente_confirmacion: {E.autorizado, E.rechazado},
    E.autorizado: {E.captura_pendiente, E.capturado, E.anulado},
    E.captura_pendiente: {E.capturado, E.rechazado},
    E.capturado: {E.reembolsado_parcial, E.reembolsado},
    E.reembolsado_parcial: {E.reembolsado_parcial, E.reembolsado},
    E.rechazado: set(),
    E.anulado: set(),
    E.reembolsado: set(),
}


# --- Reglas puras -----------------------------------------------------------


def validar_transicion(actual: EstadoPago, nuevo: EstadoPago) -> None:
    if nuevo not in TRANSICIONES[actual]:
        raise conflicto(
            "transicion-invalida",
            "El estado del pago no admite la operación",
            f"No se puede pasar de '{actual.value}' a '{nuevo.value}'",
        )


def monto_a_capturar(autorizado: Decimal, solicitado: Decimal | None, tarifa_final: Decimal | None) -> Decimal:
    """Se captura lo pedido, si no la tarifa final del viaje, si no lo autorizado; nunca más que lo autorizado."""
    monto = solicitado or tarifa_final or autorizado
    if monto > autorizado:
        raise no_procesable(
            "monto-excede-autorizado",
            "El monto supera lo autorizado",
            f"Autorizado: {autorizado}, a capturar: {monto}",
        )
    return monto


def calcular_reembolso(
    capturado: Decimal, ya_reembolsado: Decimal, solicitado: Decimal | None
) -> tuple[Decimal, EstadoPago]:
    """Devuelve el monto a reembolsar y el estado en que queda el pago."""
    disponible = capturado - ya_reembolsado
    monto = solicitado if solicitado is not None else disponible
    if monto > disponible:
        raise no_procesable(
            "monto-excede-reembolsable", "El monto supera lo reembolsable", f"Disponible para reembolsar: {disponible}"
        )
    estado = E.reembolsado if ya_reembolsado + monto == capturado else E.reembolsado_parcial
    return monto, estado


# --- Acceso a datos ---------------------------------------------------------


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def buscar(db: Session, pago_id: UUID, bloquear: bool = False) -> models.Pago:
    consulta = select(models.Pago).where(models.Pago.id == pago_id)
    if bloquear:
        # populate_existing: con el bloqueo se releen los datos aunque el objeto ya esté en la sesión
        consulta = consulta.with_for_update().execution_options(populate_existing=True)
    pago = db.scalar(consulta)
    if pago is None:
        raise no_encontrado("Pago no encontrado")
    return pago


def _cambiar_estado(pago: models.Pago, nuevo: EstadoPago) -> None:
    validar_transicion(E(pago.estado), nuevo)
    pago.estado = nuevo.value
    pago.actualizado_en = _ahora()


def cobro_vigente(db: Session, viaje_id: UUID, tipo: TipoOperacion = TipoOperacion.cobro_viaje) -> models.Pago | None:
    return db.scalar(
        select(models.Pago).where(
            models.Pago.viaje_id == viaje_id,
            models.Pago.tipo_operacion == tipo.value,
            models.Pago.estado.not_in(models.ESTADOS_LIBERADOS),
        )
    )


def _metodo_del_cliente(db: Session, datos: PagoCreate) -> models.MetodoPago | None:
    if datos.metodo_pago_id is None:
        return None
    metodo = db.get(models.MetodoPago, datos.metodo_pago_id)
    if metodo is None or not metodo.activo or metodo.cliente_id != datos.cliente_id:
        raise no_procesable(
            "metodo-pago-invalido",
            "El medio de pago no está disponible",
            "No existe, fue dado de baja o pertenece a otro cliente",
        )
    return metodo


def _monto_solicitado(db: Session, datos: PagoCreate) -> Decimal:
    if datos.estimacion_id is None:
        return datos.monto
    estimacion = db.get(models.Estimacion, datos.estimacion_id)
    if estimacion is None:
        raise no_procesable("estimacion-inexistente", "La estimación no existe")
    if datos.monto is None and estimacion.vence_en <= _ahora():
        raise no_procesable("estimacion-vencida", "La estimación está vencida", f"Venció el {estimacion.vence_en}")
    return datos.monto or estimacion.total


def _validar_reserva(m9: ReservasM9 | None, datos: PagoCreate) -> None:
    """Si M9 está configurado, la reserva debe existir y ser del mismo cliente."""
    if datos.reserva_id is None or m9 is None:
        return
    reserva = m9.obtener_reserva(datos.reserva_id)
    if reserva.cliente_id != datos.cliente_id:
        raise no_procesable("reserva-de-otro-cliente", "La reserva pertenece a otro cliente")


# --- Autorización -----------------------------------------------------------


def _resolver_autorizacion(db: Session, pago_id: UUID, actor: str, token: str | None, pasarela: PasarelaPagos) -> None:
    pago = buscar(db, pago_id)
    try:
        resultado = con_timeout(pasarela.autorizar, pago.id, pago.monto, token)
    except PasarelaNoDisponible as exc:
        movimientos.registrar(
            db, TipoMovimiento.autorizacion_sin_respuesta, actor, pago.monto, pago=pago, detalle=str(exc)
        )
        db.commit()
        return
    pago = buscar(db, pago_id, bloquear=True)
    if pago.estado != E.pendiente_confirmacion:
        # Un webhook resolvió la autorización mientras se esperaba la respuesta
        db.rollback()
        return
    pago.referencia_externa = resultado.referencia
    _cambiar_estado(pago, E.autorizado if resultado.aprobado else E.rechazado)
    tipo = TipoMovimiento.autorizacion if resultado.aprobado else TipoMovimiento.rechazo
    movimientos.registrar(
        db, tipo, actor, pago.monto, pago=pago, referencia=resultado.referencia, detalle=resultado.motivo
    )
    db.commit()


def _nuevo_pago(datos: PagoCreate, tipo: TipoOperacion, metodo: models.MetodoPago | None, monto: Decimal):
    ahora = _ahora()
    efectivo = metodo is None or metodo.tipo == TipoMetodoPago.efectivo
    return models.Pago(
        id=uuid4(),
        viaje_id=datos.viaje_id,
        tipo_operacion=tipo.value,
        reserva_id=datos.reserva_id,
        estimacion_id=datos.estimacion_id,
        cliente_id=datos.cliente_id,
        beneficiario_id=datos.beneficiario_id,
        metodo_pago_id=metodo.id if metodo else None,
        metodo=metodo.tipo if metodo else TipoMetodoPago.efectivo.value,
        monto=monto,
        monto_capturado=Decimal("0"),
        monto_reembolsado=Decimal("0"),
        moneda="ARS",
        # El efectivo no pasa por la pasarela: queda autorizado directamente
        estado=(E.autorizado if efectivo else E.pendiente_confirmacion).value,
        creado_en=ahora,
        actualizado_en=ahora,
    )


def autorizar(
    db: Session,
    datos: PagoCreate,
    idempotency_key: str | None,
    usuario: Usuario,
    pasarela: PasarelaPagos,
    m9: ReservasM9 | None = None,
) -> tuple[Pago, bool]:
    """Crea el cobro del viaje y lo autoriza. Devuelve el pago y si fue creado ahora.

    - Misma Idempotency-Key y mismo cuerpo: devuelve el pago original (False).
    - Misma Idempotency-Key y otro cuerpo: 422.
    - Otro cobro vigente para el mismo viaje: 409 con el id del existente.
    """
    hash_actual = idempotencia.hash_cuerpo(datos.model_dump(mode="json"))
    if idempotency_key and (existente := idempotencia.buscar(db, "pago", idempotency_key, hash_actual)):
        return obtener(db, existente), False

    metodo = _metodo_del_cliente(db, datos)
    monto = _monto_solicitado(db, datos)
    _validar_reserva(m9, datos)

    pago = _nuevo_pago(datos, TipoOperacion.cobro_viaje, metodo, monto)
    db.add(pago)
    if idempotency_key:
        idempotencia.registrar(db, "pago", idempotency_key, hash_actual, pago.id)
    if pago.estado == E.autorizado:
        movimientos.registrar(db, TipoMovimiento.autorizacion, usuario.sub, monto, pago=pago, detalle="Efectivo")
    try:
        # Reserva el lugar del viaje antes de llamar a la pasarela (índice único parcial)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if idempotency_key and (existente := idempotencia.buscar(db, "pago", idempotency_key, hash_actual)):
            return obtener(db, existente), False
        vigente = cobro_vigente(db, datos.viaje_id)
        raise conflicto(
            "pago-duplicado",
            "El viaje ya tiene un cobro vigente",
            f"Pago existente: {vigente.id}" if vigente else None,
            pago_existente_id=str(vigente.id) if vigente else None,
        ) from exc

    if pago.estado == E.pendiente_confirmacion:
        _resolver_autorizacion(db, pago.id, usuario.sub, metodo.token_pasarela, pasarela)
    return obtener(db, pago.id), True


# --- Captura y anulación ----------------------------------------------------


def _capturar(db: Session, pago_id: UUID, monto_pedido: Decimal | None, actor: str, pasarela: PasarelaPagos) -> Pago:
    pago = buscar(db, pago_id, bloquear=True)
    validar_transicion(E(pago.estado), E.capturado)
    tarifa = db.get(models.TarifaFinal, pago.viaje_id) if pago.tipo_operacion == TipoOperacion.cobro_viaje else None
    monto = monto_a_capturar(pago.monto, monto_pedido, tarifa.total if tarifa else None)

    if pago.metodo == TipoMetodoPago.efectivo:
        _cambiar_estado(pago, E.capturado)
        pago.monto_capturado, pago.capturado_en = monto, _ahora()
        movimientos.registrar(db, TipoMovimiento.captura, actor, monto, pago=pago, detalle="Efectivo")
        db.commit()
        return Pago.model_validate(pago)

    # captura_pendiente impide una segunda captura mientras se espera a la pasarela
    _cambiar_estado(pago, E.captura_pendiente)
    pago.monto_capturado = monto
    referencia = pago.referencia_externa
    db.commit()
    try:
        resultado = con_timeout(pasarela.capturar, referencia, monto)
    except PasarelaNoDisponible as exc:
        movimientos.registrar(db, TipoMovimiento.captura_sin_respuesta, actor, monto, pago=pago, detalle=str(exc))
        db.commit()
        return obtener(db, pago_id)

    pago = buscar(db, pago_id, bloquear=True)
    if pago.estado != E.captura_pendiente:
        db.rollback()
        return Pago.model_validate(pago)
    if resultado.aprobado:
        _cambiar_estado(pago, E.capturado)
        pago.capturado_en = _ahora()
        tipo = TipoMovimiento.captura
    else:
        _cambiar_estado(pago, E.rechazado)
        pago.monto_capturado = Decimal("0")
        tipo = TipoMovimiento.rechazo
    movimientos.registrar(db, tipo, actor, monto, pago=pago, referencia=resultado.referencia, detalle=resultado.motivo)
    db.commit()
    return Pago.model_validate(pago)


def capturar(db: Session, pago_id: UUID, datos: CapturaRequest, usuario: Usuario, pasarela: PasarelaPagos) -> Pago:
    """Cobra el monto autorizado cuando M6 informa que el viaje finalizó."""
    return _capturar(db, pago_id, datos.monto, usuario.sub, pasarela)


def anular(db: Session, pago_id: UUID, actor: str, pasarela: PasarelaPagos, motivo: str | None = None) -> Pago:
    """Libera una autorización que no se va a capturar (por ejemplo, viaje cancelado)."""
    pago = buscar(db, pago_id, bloquear=True)
    validar_transicion(E(pago.estado), E.anulado)
    if pago.metodo != TipoMetodoPago.efectivo:
        try:
            con_timeout(pasarela.anular, pago.referencia_externa)
        except PasarelaNoDisponible as exc:
            db.rollback()
            raise DependenciaNoDisponible("La pasarela de pagos") from exc
    _cambiar_estado(pago, E.anulado)
    movimientos.registrar(
        db, TipoMovimiento.anulacion, actor, pago.monto, pago=pago, referencia=pago.referencia_externa, detalle=motivo
    )
    db.commit()
    return Pago.model_validate(pago)


def cobrar_cargo(
    db: Session, pago_viaje: models.Pago, monto: Decimal, actor: str, pasarela: PasarelaPagos
) -> models.Pago:
    """Cobra un cargo de cancelación con el mismo medio de pago del viaje."""
    metodo = db.get(models.MetodoPago, pago_viaje.metodo_pago_id) if pago_viaje.metodo_pago_id else None
    datos = PagoCreate(
        viaje_id=pago_viaje.viaje_id,
        reserva_id=pago_viaje.reserva_id,
        cliente_id=pago_viaje.cliente_id,
        beneficiario_id=pago_viaje.beneficiario_id,
        metodo_pago_id=pago_viaje.metodo_pago_id,
        monto=monto,
    )
    pago = _nuevo_pago(datos, TipoOperacion.cargo_cancelacion, metodo, monto)
    db.add(pago)
    if pago.estado == E.autorizado:
        movimientos.registrar(db, TipoMovimiento.autorizacion, actor, monto, pago=pago, detalle="Efectivo")
    db.commit()
    if pago.estado == E.pendiente_confirmacion:
        _resolver_autorizacion(db, pago.id, actor, metodo.token_pasarela if metodo else None, pasarela)
    if buscar(db, pago.id).estado == E.autorizado:
        _capturar(db, pago.id, monto, actor, pasarela)
    return buscar(db, pago.id)


# --- Reembolsos -------------------------------------------------------------


def reembolsar(
    db: Session,
    pago_id: UUID,
    datos: ReembolsoCreate,
    idempotency_key: str | None,
    usuario: Usuario,
    pasarela: PasarelaPagos,
) -> tuple[Reembolso, bool]:
    """Reembolso total o parcial. Con la misma Idempotency-Key no se devuelve dos veces (RF-7.6)."""
    hash_actual = idempotencia.hash_cuerpo({"pago_id": str(pago_id), **datos.model_dump(mode="json")})
    # El bloqueo del pago serializa los reembolsos: la clave se busca después de tomarlo
    pago = buscar(db, pago_id, bloquear=True)
    if idempotency_key and (existente := idempotencia.buscar(db, "reembolso", idempotency_key, hash_actual)):
        db.rollback()
        return Reembolso.model_validate(db.get(models.Reembolso, existente)), False

    estado_actual = E(pago.estado)
    if estado_actual not in ESTADOS_COBRADOS:
        raise conflicto(
            "transicion-invalida",
            "El estado del pago no admite la operación",
            f"No se puede reembolsar un pago en estado '{estado_actual.value}'",
        )
    monto, nuevo_estado = calcular_reembolso(pago.monto_capturado, pago.monto_reembolsado, datos.monto)
    validar_transicion(estado_actual, nuevo_estado)

    referencia = None
    if pago.metodo != TipoMetodoPago.efectivo:
        try:
            resultado = con_timeout(pasarela.reembolsar, pago.referencia_externa, monto)
        except PasarelaNoDisponible as exc:
            db.rollback()
            raise DependenciaNoDisponible("La pasarela de pagos") from exc
        if not resultado.aprobado:
            db.rollback()
            raise no_procesable("reembolso-rechazado", "La pasarela rechazó el reembolso", resultado.motivo)
        referencia = resultado.referencia

    _cambiar_estado(pago, nuevo_estado)
    pago.monto_reembolsado += monto
    reembolso = models.Reembolso(
        id=uuid4(),
        pago_id=pago.id,
        monto=monto,
        motivo=datos.motivo,
        referencia_externa=referencia,
        creado_por=usuario.sub,
        creado_en=_ahora(),
    )
    db.add(reembolso)
    if idempotency_key:
        idempotencia.registrar(db, "reembolso", idempotency_key, hash_actual, reembolso.id)
    movimientos.registrar(
        db, TipoMovimiento.reembolso, usuario.sub, monto, pago=pago, referencia=referencia, detalle=datos.motivo
    )
    db.commit()
    return Reembolso.model_validate(reembolso), True


def listar_reembolsos(db: Session, pago_id: UUID) -> list[Reembolso]:
    buscar(db, pago_id)
    consulta = select(models.Reembolso).where(models.Reembolso.pago_id == pago_id).order_by(models.Reembolso.creado_en)
    return [Reembolso.model_validate(r) for r in db.scalars(consulta)]


# --- Webhook y consultas ----------------------------------------------------


def procesar_webhook(db: Session, evento: WebhookPasarela) -> Pago:
    """Resuelve una autorización o captura que había quedado sin respuesta."""
    pago = buscar(db, evento.pago_id, bloquear=True)
    aprobado = evento.estado.value == "aprobado"
    if pago.estado == E.pendiente_confirmacion:
        _cambiar_estado(pago, E.autorizado if aprobado else E.rechazado)
        pago.referencia_externa = evento.referencia_externa
        tipo = TipoMovimiento.autorizacion if aprobado else TipoMovimiento.rechazo
        monto = pago.monto
    elif pago.estado == E.captura_pendiente:
        monto = pago.monto_capturado
        _cambiar_estado(pago, E.capturado if aprobado else E.rechazado)
        if aprobado:
            pago.capturado_en = _ahora()
        else:
            pago.monto_capturado = Decimal("0")
        tipo = TipoMovimiento.captura if aprobado else TipoMovimiento.rechazo
    else:
        # Las pasarelas reintentan: un evento repetido no es un error
        db.rollback()
        return Pago.model_validate(pago)
    movimientos.registrar(db, tipo, "pasarela", monto, pago=pago, referencia=evento.referencia_externa)
    db.commit()
    return Pago.model_validate(pago)


def obtener(db: Session, pago_id: UUID) -> Pago:
    return Pago.model_validate(buscar(db, pago_id))


def listar(
    db: Session,
    viaje_id: UUID | None = None,
    cliente_id: UUID | None = None,
    beneficiario_id: UUID | None = None,
    estado: EstadoPago | None = None,
    tipo_operacion: TipoOperacion | None = None,
) -> list[Pago]:
    consulta = select(models.Pago).order_by(models.Pago.creado_en)
    for columna, valor in (
        (models.Pago.viaje_id, viaje_id),
        (models.Pago.cliente_id, cliente_id),
        (models.Pago.beneficiario_id, beneficiario_id),
        (models.Pago.estado, estado.value if estado else None),
        (models.Pago.tipo_operacion, tipo_operacion.value if tipo_operacion else None),
    ):
        if valor is not None:
            consulta = consulta.where(columna == valor)
    return [Pago.model_validate(p) for p in db.scalars(consulta)]
