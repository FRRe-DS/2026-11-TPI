# Catálogo de eventos de M7

Eventos que M7 **publicaría** cuando se incorpore RabbitMQ (RNF-10, TP2). Todavía
no se publican: este catálogo fija nombres y payloads para acordarlos con el
consorcio y con M8 (notificaciones y comprobantes), M6 (viajes) y M9 (reservas).

Hoy cada uno de estos hechos ya queda registrado en `movimientos_financieros`
(columna `tipo` entre paréntesis), así que publicar el evento será agregar un
productor sobre lo que ya existe (patrón *outbox* sugerido, ver
[decisiones.md](decisiones.md)).

## Convenciones

- **Exchange:** `m7.eventos` (tipo `topic`). **Routing key:** el nombre del evento.
- **Formato:** JSON UTF-8, con este sobre común:

```json
{
  "id": "0b8f7a52-3c1d-4e5f-9a6b-7c8d9e0f1a2b",
  "tipo": "pago.capturado",
  "version": 1,
  "ocurrido_en": "2026-10-22T19:45:48.210976Z",
  "origen": "m7-tarifas",
  "request_id": "a1b2c3d4e5f6",
  "datos": { }
}
```

- `id` es único por evento: los consumidores lo usan para descartar duplicados
  (entrega *at-least-once*, RNF-09).
- Montos como string con dos decimales, en ARS. Fechas en ISO 8601 UTC.
- Nunca se incluyen datos sensibles: ni número de tarjeta, ni token de la
  pasarela, ni datos personales más allá de los identificadores (RNF-19).
- Cambios incompatibles de payload incrementan `version`.

## Eventos

### `pago.autorizado`

El monto quedó reservado en el medio de pago. Se publica tanto por respuesta
directa de la pasarela como por webhook. Movimiento: `autorizacion`.

Consumidores esperados: M5 (confirmar asignación), M8 (aviso al cliente).

```json
{
  "pago_id": "2b9f1c3a-7d4e-4f5a-8b6c-9d0e1f2a3b4c",
  "viaje_id": "8d2b6c1e-1f3a-4c5d-9e7f-0a1b2c3d4e5f",
  "reserva_id": null,
  "cliente_id": "3f0c2a5e-8f7b-4a51-9d55-0b1c2d3e4f50",
  "beneficiario_id": "6a7b8c9d-0e1f-4a2b-8c3d-4e5f6a7b8c9d",
  "tipo_operacion": "cobro_viaje",
  "metodo": "tarjeta",
  "monto": "6600.00",
  "moneda": "ARS"
}
```

### `pago.capturado`

Se cobró el viaje (o el cargo de cancelación). Movimiento: `captura`.

Consumidores esperados: M8 (comprobante PDF, RF-8.4), M6 (cierre financiero del viaje).

```json
{
  "pago_id": "2b9f1c3a-7d4e-4f5a-8b6c-9d0e1f2a3b4c",
  "viaje_id": "8d2b6c1e-1f3a-4c5d-9e7f-0a1b2c3d4e5f",
  "cliente_id": "3f0c2a5e-8f7b-4a51-9d55-0b1c2d3e4f50",
  "beneficiario_id": "6a7b8c9d-0e1f-4a2b-8c3d-4e5f6a7b8c9d",
  "tipo_operacion": "cobro_viaje",
  "monto_autorizado": "6600.00",
  "monto_capturado": "6030.00",
  "moneda": "ARS",
  "capturado_en": "2026-10-22T20:10:00Z"
}
```

### `pago.rechazado`

La pasarela rechazó la autorización o la captura. Movimiento: `rechazo`.

Consumidores esperados: M5 (pedir otro medio de pago o liberar al conductor), M8 (aviso al cliente).

```json
{
  "pago_id": "2b9f1c3a-7d4e-4f5a-8b6c-9d0e1f2a3b4c",
  "viaje_id": "8d2b6c1e-1f3a-4c5d-9e7f-0a1b2c3d4e5f",
  "cliente_id": "3f0c2a5e-8f7b-4a51-9d55-0b1c2d3e4f50",
  "etapa": "autorizacion",
  "monto": "6600.00",
  "moneda": "ARS",
  "motivo": "Fondos insuficientes"
}
```

`etapa`: `autorizacion` o `captura`.

### `cargo_cancelacion.registrado`

Se canceló un viaje y se calculó su cargo (puede ser 0). Movimiento: `cargo_cancelacion`.

Consumidores esperados: M6 (historial del viaje), M8 (aviso y comprobante si hay cargo), M9 (si el viaje venía de una reserva).

```json
{
  "cargo_id": "5d6e7f80-9a1b-4c2d-8e3f-405162738495",
  "viaje_id": "8d2b6c1e-1f3a-4c5d-9e7f-0a1b2c3d4e5f",
  "cliente_id": "3f0c2a5e-8f7b-4a51-9d55-0b1c2d3e4f50",
  "estado_viaje": "asignado",
  "regla_aplicada": "asignado_fuera_de_gracia",
  "monto": "500.00",
  "moneda": "ARS",
  "pago_cargo_id": "7f8e9d0c-1b2a-4394-8576-a5b4c3d2e1f0",
  "pago_anulado_id": "2b9f1c3a-7d4e-4f5a-8b6c-9d0e1f2a3b4c"
}
```

### `reembolso.registrado`

Se devolvió total o parcialmente un pago. Movimiento: `reembolso`.

Consumidores esperados: M8 (aviso y nota de crédito), M9 (reserva cancelada con reintegro).

```json
{
  "reembolso_id": "c1d2e3f4-a5b6-4c7d-8e9f-0a1b2c3d4e5f",
  "pago_id": "2b9f1c3a-7d4e-4f5a-8b6c-9d0e1f2a3b4c",
  "viaje_id": "8d2b6c1e-1f3a-4c5d-9e7f-0a1b2c3d4e5f",
  "cliente_id": "3f0c2a5e-8f7b-4a51-9d55-0b1c2d3e4f50",
  "monto": "300.00",
  "monto_reembolsado_total": "300.00",
  "moneda": "ARS",
  "estado_pago": "reembolsado_parcial",
  "motivo": "Demora del conductor"
}
```

### `liquidacion.generada`

Se liquidó a un conductor un período. Movimiento: `liquidacion_generada`.

Consumidores esperados: M3 (estado del conductor), M8 (aviso al conductor).

```json
{
  "liquidacion_id": "e5f6a7b8-c9d0-4e1f-8a2b-3c4d5e6f7a8b",
  "beneficiario_id": "6a7b8c9d-0e1f-4a2b-8c3d-4e5f6a7b8c9d",
  "periodo_desde": "2026-10-01",
  "periodo_hasta": "2026-10-31",
  "cantidad_pagos": 42,
  "monto_bruto": "251300.00",
  "comision_porcentaje": "0.2000",
  "comision_plataforma": "50260.00",
  "monto_neto": "201040.00",
  "moneda": "ARS"
}
```

### `liquidacion.transferida`

El operador confirmó la transferencia al conductor. Movimiento: `liquidacion_transferida`.

Consumidores esperados: M8 (aviso y comprobante al conductor).

```json
{
  "liquidacion_id": "e5f6a7b8-c9d0-4e1f-8a2b-3c4d5e6f7a8b",
  "beneficiario_id": "6a7b8c9d-0e1f-4a2b-8c3d-4e5f6a7b8c9d",
  "monto_neto": "201040.00",
  "moneda": "ARS",
  "referencia_transferencia": "CBU-0001",
  "transferida_en": "2026-11-02T13:00:00Z"
}
```

## Eventos que M7 consumiría

Los listamos para acordarlos con los productores; hoy esas interacciones son
llamadas HTTP síncronas a la API de M7.

| Evento (productor) | Acción en M7 | Endpoint actual equivalente |
|---|---|---|
| `viaje.asignado` (M5/M6) | Autorizar el cobro | `POST /api/v1/pagos` |
| `viaje.finalizado` (M6) | Tarifa final y captura | `POST /api/v1/tarifas/viajes/{id}/tarifa-final` y `POST /api/v1/pagos/{id}/captura` |
| `viaje.cancelado` (M6) | Cargo de cancelación | `POST /api/v1/cancelaciones` |
| `reserva.cancelada` (M9) | Reembolso según condiciones | `POST /api/v1/pagos/{id}/reembolsos` |
