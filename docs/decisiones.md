# Decisiones y supuestos de M7

Registro de las decisiones técnicas del Grupo 11 y de los supuestos que todavía
hay que acordar con el consorcio y con el **Grupo 6** (que implementa el mismo
módulo). Cada supuesto indica dónde se configura o qué habría que cambiar si el
acuerdo es distinto.

## Decisiones técnicas

| # | Decisión | Motivo |
|---|---|---|
| D1 | **PostgreSQL 16** en un contenedor propio, con **SQLAlchemy 2** y migraciones **Alembic**. Supabase deja de ser necesario. | RNF-05 (cada módulo dueño de sus datos) y RNF-18 (todo corre local con `docker compose up`). En la nube alcanza con apuntar `DATABASE_URL` a un Postgres administrado (Supabase sirve) sin tocar código. |
| D2 | Montos en `NUMERIC(12,2)` y `Decimal` en Python; en JSON se responden como string. | Evitar errores de redondeo de `float`. El string conserva los dos decimales exactos. |
| D3 | Redondeo `ROUND_HALF_UP` a centavos al final de cada cálculo (tarifa y comisión). | Es el redondeo comercial esperado; se aplica una sola vez para no acumular error. |
| D4 | **Doble cobro (RNF-08):** índice único parcial `(viaje_id, tipo_operacion)` para los pagos que no estén `rechazado` ni `anulado`. Ante la violación se responde **`409 /errores/pago-duplicado`** con `pago_existente_id`. | Elegimos 409 y no "devolver el existente" porque un segundo cobro **sin** la misma `Idempotency-Key` puede traer otro monto u otro medio de pago: devolver el anterior ocultaría el error. La repetición legítima se hace con la misma clave, que sí devuelve el original. El índice es parcial para que un cobro rechazado se pueda reintentar con otra tarjeta. |
| D5 | **Idempotencia (RF-7.6):** tabla `claves_idempotencia` con clave primaria `(operacion, clave)` y SHA-256 del cuerpo canónico. Misma clave y mismo cuerpo: `200` con el recurso original; otro cuerpo: `422`. La clave se inserta en la misma transacción que el recurso. | La restricción de base resuelve también las solicitudes concurrentes. Para reembolsos la clave se busca **después** de bloquear la fila del pago, así dos reintentos simultáneos no llaman dos veces a la pasarela. El hash del reembolso incluye el `pago_id`. |
| D6 | `Idempotency-Key` **opcional** en cobro y reembolso. | El enunciado pide que la repetición no duplique, y la restricción por viaje ya lo garantiza para los cobros. M2 la exige obligatoria: **a acordar** si conviene unificar. |
| D7 | **Autorización y captura separadas (RF-7.3)**: `POST /pagos` autoriza (al asignarse el viaje) y `POST /pagos/{id}/captura` cobra (al finalizar). El cobro se reserva en la base **antes** de llamar a la pasarela y la llamada se hace fuera de la transacción. | Así el índice único impide dos autorizaciones en la pasarela para el mismo viaje y nunca se mantiene una transacción abierta esperando a un tercero. |
| D8 | Pasarela detrás de la interfaz `PasarelaPagos` (`app/services/pasarela.py`), con `PasarelaSimulada` por defecto. Toda llamada pasa por `con_timeout` (`PASARELA_TIMEOUT_S`, 3 s). | Cambiar a una pasarela real es implementar la interfaz. Si no responde: autorización → `pendiente_confirmacion`; captura → `captura_pendiente`; ambos se resuelven por webhook (RNF-13). En anulación y reembolso no hay estado intermedio: se responde `503` sin registrar nada y se puede reintentar. |
| D9 | Tarjetas de prueba en la pasarela simulada: `4000000000000002` (rechazada) y `4000000000000119` (no responde). | Permiten demostrar los caminos de error en la demo sin tocar código. |
| D10 | Efectivo: queda `autorizado` al crear el cobro y `capturado` al capturar, sin pasarela. | "Efectivo se aprueba directo como hoy". Se mantienen los mismos estados para que la liquidación trate igual a todos los medios. |
| D11 | **Historial financiero inmutable (RF-7.7):** tabla `movimientos_financieros` con un trigger que rechaza `UPDATE` y `DELETE`. Cada cambio de estado de un pago o una liquidación inserta un movimiento en la misma transacción, con el `sub` del token como actor. | La inmutabilidad la garantiza la base, no solo el código. `TRUNCATE` sigue permitido (lo usan los tests). |
| D12 | **Errores problem+json** con el mismo esquema y criterio que M2: genéricos con `about:blank` (incluido el 404) y de dominio con `type: /errores/...`. Validación de formato → **`400`** con la extensión `errores` (campo y mensaje). | Coherencia con el contrato ya aprobado por el consorcio. FastAPI responde 422 por defecto; lo cambiamos a 400 para seguir a M2 y dejamos 422 para reglas de negocio. |
| D13 | Roles `cliente`, `conductor`, `operador` y además **`servicio`** para las cuentas de servicio de otros módulos; se comparan sin distinguir mayúsculas. | M2 usa `SERVICIO` para los módulos y los escribe en mayúsculas; aceptar ambas formas evita romper la integración. Sin un rol de servicio, M5/M6/M9 no podrían capturar ni registrar tarifas finales. |
| D14 | Reglas de propiedad: un cliente opera solo sobre su `cliente_id`; un conductor ve solo lo que lo tiene como `beneficiario_id`; pedir datos ajenos es `403` (no una lista vacía). Solo el operador administra reglas de tarifa y confirma o anula liquidaciones. | Lo pide el enunciado (RF-1.3) y es el mismo criterio que M2. |
| D15 | Audiencia del JWT: se exige `aud: m7-tarifas`. En el realm, los 6 scopes de M7 tienen un *audience mapper*, así que cualquier token que pida un scope de M7 trae la audiencia. | Quita el TODO de `security.py` sin obligar a cada módulo a configurar mappers propios. |
| D16 | El secreto de `m7-tarifas` sale del realm: el archivo usa `${M7_CLIENT_SECRET}` y Keycloak lo resuelve al importar. | RNF-06. La importación de realms de Keycloak (también en la 24) admite placeholders de variables de entorno. **No pudimos verificarlo localmente** porque no había Docker; si en algún entorno no se resolviera, ver "Regenerar el secreto" en el README. |
| D17 | El período de una liquidación se toma por **fecha de captura** (UTC), no por fecha de creación del pago. | Se liquida lo efectivamente cobrado; un viaje autorizado el día 31 y capturado el 1 entra en el mes siguiente. |
| D18 | Estimaciones guardadas con vencimiento (`ESTIMACION_VIGENCIA_MIN`, 15 min). Un cobro con `estimacion_id` y sin `monto` exige que esté vigente; con `monto` explícito la estimación solo queda como referencia. | M9 puede referenciar la estimación por id (RF-9.4) sin que M7 cobre precios viejos. |
| D19 | Clientes HTTP de M4, M6 y M9 con 2 s por intento y **1 reintento** solo para errores de red y 5xx; un 404 es `422 /errores/recurso-externo-inexistente` y nunca se reintenta. Si la URL no está configurada, la integración se considera deshabilitada. | Mismo criterio que M2 (2 s + 1 reintento). Solo se usan GET, que son seguros de reintentar. |
| D20 | Log estructurado en JSON por solicitud con `request_id`, método, ruta, estado y duración; nunca la query string. | RNF-14 y RNF-19 (los filtros pueden tener identificadores de personas). |
| D21 | Los tests de integración corren contra un PostgreSQL real (`db-test` del compose o el servicio de GitHub Actions) y no contra SQLite. | El índice parcial, `FOR UPDATE` y el trigger son propios de PostgreSQL; con SQLite los tests de concurrencia no probarían nada. |

## Supuestos pendientes de acordar

### Con el consorcio

| # | Supuesto | Valor actual | Dónde se cambia |
|---|---|---|---|
| S1 | Reglas de cargo de cancelación (RF-7.4): sin cargo antes de la asignación; sin cargo dentro del período de gracia; cargo fijo pasado ese período; cargo mayor si el conductor llegó al punto de retiro. En curso o finalizado no se cancela. | Gracia 5 min, cargo 500 ARS, cargo en punto 1000 ARS | `CANCELACION_*` en `.env` |
| S2 | Un viaje `asignado` sin `asignado_en` no puede evaluarse: `422 /errores/falta-asignado-en` (en vez de asumir que pasó el período de gracia). | `422` | `app/services/cancelaciones.py` |
| S3 | El cargo se cobra con el mismo medio de pago de la autorización del viaje. Si no había autorización, el cargo queda registrado sin `pago_cargo_id` para cobrarse por otra vía. Con efectivo el cargo se registra como capturado. | — | `cancelaciones.registrar` |
| S4 | Comisión de la plataforma sobre el neto cobrado (capturado menos reembolsado). | 20 % | `COMISION_PLATAFORMA` |
| S5 | Vigencia de una estimación. | 15 min | `ESTIMACION_VIGENCIA_MIN` |
| S6 | Moneda única ARS. | ARS | Columna `moneda` ya preparada |
| S7 | La captura no puede superar lo autorizado. Si la tarifa final excede la estimación, quien autoriza debe hacerlo con margen o se captura hasta lo autorizado y la diferencia queda pendiente. | `422` si excede | `pagos.monto_a_capturar` |
| S8 | Un reembolso después de liquidar el pago no ajusta la liquidación ya generada. | Sin ajuste | Pendiente (TP2) |
| S9 | Formato de los identificadores: el `sub` de Keycloak (UUID) es el `cliente_id` y el `beneficiario_id`. | UUID | `Usuario.id` |
| S10 | Nombres de campos en `snake_case`; M2 usa `camelCase`. Paginación: M7 devuelve listas completas, M2 usa `page`/`size`. | snake_case, sin paginar | Convención a unificar en todo el consorcio |
| S11 | Catálogo de eventos de [eventos.md](eventos.md) (nombres, exchange y sobre común). | Propuesta | — |

### Con M4, M6 y M9 (contratos no publicados todavía)

| Módulo | Lo que M7 asume | Archivo |
|---|---|---|
| M4 | `GET /api/v1/rutas/estimacion?origen_lat&origen_lng&destino_lat&destino_lng&tipo_vehiculo` → `{distancia_km, duracion_min}` | `app/services/integraciones.py` |
| M6 | `GET /api/v1/viajes/{id}` → `{id, estado, asignado_en}`, con estados `solicitado`, `asignado`, `conductor_en_punto`, `en_curso`, `finalizado`, `cancelado` | `app/services/integraciones.py`, `app/schemas/cancelaciones.py` |
| M9 | `GET /api/v1/reservas/{id}` → `{id, cliente_id, estado}` | `app/services/integraciones.py` |

Cuando publiquen sus contratos solo hay que ajustar esos clientes: el resto de
M7 depende de las interfaces `UbicacionM4`, `ViajesM6` y `ReservasM9`.

### Con el Grupo 6 (mismo módulo)

Para que cualquiera de las dos implementaciones de M7 sea intercambiable
(RNF-02) hay que acordar un único contrato. Puntos a revisar juntos:

1. Rutas y nombres de recursos (`/pagos`, `/metodos-pago`, `/cancelaciones`, `/movimientos`, `/liquidaciones`).
2. Estados del pago y sus transiciones (`EstadoPago` en el contrato).
3. Semántica del 409 por doble cobro (D4) y de `Idempotency-Key` opcional u obligatoria (D6).
4. Roles y scopes (D13, D15).
5. Tipos de error `/errores/...` listados en `Conflicto` y `NoProcesable` del contrato.
6. Payloads del catálogo de eventos.

## Pendiente para próximas entregas

- Publicar los eventos en RabbitMQ con patrón *outbox* sobre `movimientos_financieros` (RNF-10, TP2).
- Tarea de reconciliación que consulte a la pasarela los pagos que siguen en `pendiente_confirmacion` o `captura_pendiente` si el webhook nunca llega.
- Paginación de listados.
- Redis para cachear reglas de tarifa activas si hiciera falta (RNF-11).
- HTTPS y despliegue en la nube (RNF-12, RNF-18).
