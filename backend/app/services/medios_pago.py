import re
import uuid
from typing import Any, Dict, List
from fastapi import HTTPException
import pymysql

from app.core.database import get_db
from app.schemas.medios_pago import MedioPagoRequest


def validar_medio_pago(datos: MedioPagoRequest) -> None:
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


def registrar_medio_pago(datos: MedioPagoRequest) -> Dict[str, Any]:
    validar_medio_pago(datos)

    with get_db() as conexion:
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
                    (
                        medio_id,
                        datos.cliente_id,
                        datos.tipo,
                        datos.alias.strip(),
                        datos.ultimos4,
                        datos.predeterminado,
                    ),
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


def listar_medios_pago(cliente_id: str) -> List[Dict[str, Any]]:
    with get_db() as conexion:
        with conexion.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM medios_pago WHERE cliente_id = %s ORDER BY predeterminado DESC, creado_en DESC",
                (cliente_id,),
            )
            return cursor.fetchall()
