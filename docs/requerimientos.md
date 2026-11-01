# 📋 Requerimientos Funcionales y No Funcionales - Módulo 7 (Tarifas, Pagos y Liquidaciones)

Este documento detalla la cobertura de requerimientos del sistema implementados en este microservicio, su trazabilidad con los endpoints de la API (`/api/v1`) y los módulos con los que interactúa.

---

## 🪙 Requerimientos Funcionales (RF)

| ID | Requerimiento | Estado | Descripción Funcional | Endpoints / Componentes Asociados |
| :--- | :--- | :---: | :--- | :--- |
| **RF-7.1** | **Estimación y Cálculo de Tarifa** | ✅ Implementado | Estima el valor del viaje por distancia y tiempo o consultando a M4 (Ubicación). Guarda estimación con vigencia configurable (15 min) y calcula la tarifa final al concluir el viaje con reglas por tipo de vehículo. | `POST /api/v1/tarifas/estimaciones`<br>`GET /api/v1/tarifas/estimaciones/{id}`<br>`POST /api/v1/tarifas/viajes/{viaje_id}/tarifa-final`<br>`GET /api/v1/tarifas/viajes/{viaje_id}/tarifa-final`<br>`GET/POST/PATCH /api/v1/tarifas/reglas` |
| **RF-7.2** | **Registro de Métodos de Pago** | ✅ Implementado | Permite registrar tarjetas (validación de algoritmo de Luhn, enmascaramiento seguro `****1234` sin persistir CVV ni PAN completo) y medios de pago alternativos. Baja lógica del medio. | `POST /api/v1/metodos-pago`<br>`GET /api/v1/metodos-pago`<br>`GET /api/v1/metodos-pago/{id}`<br>`DELETE /api/v1/metodos-pago/{id}` |
| **RF-7.3** | **Autorización y Captura de Pagos** | ✅ Implementado | Proceso en dos fases: autoriza el cobro al asignarse el viaje (`POST /pagos`) y realiza la captura al finalizar (`POST /pagos/{id}/captura`). Soporta efectivo directo y resolución diferida por webhook. | `POST /api/v1/pagos`<br>`GET /api/v1/pagos`<br>`GET /api/v1/pagos/{id}`<br>`POST /api/v1/pagos/{id}/captura`<br>`POST /api/v1/pagos/{id}/anulacion`<br>`POST /api/v1/pagos/webhooks/pasarela` |
| **RF-7.4** | **Cargo de Cancelación** | ✅ Implementado | Evalúa y aplica cargos por cancelación según reglas de negocio: sin cargo dentro del período de gracia (5 min), cargo fijo si fue asignado y cargo mayor si el conductor ya llegó al punto. | `POST /api/v1/cancelaciones`<br>`GET /api/v1/cancelaciones/{viaje_id}` |
| **RF-7.5** | **Reembolsos / Reintegros** | ✅ Implementado | Registra reembolsos totales o parciales sobre cobros capturados. Controla que el monto reembolsado no supere el saldo capturado. | `POST /api/v1/pagos/{id}/reembolsos`<br>`GET /api/v1/pagos/{id}/reembolsos` |
| **RF-7.6** | **Idempotencia de Operaciones Financieras** | ✅ Implementado | Evita doble cobro o reintegros duplicados mediante header `Idempotency-Key` y control de hash del payload en la tabla `claves_idempotencia` en la misma transacción de BD. | Operaciones `POST /api/v1/pagos` y `POST /api/v1/pagos/{id}/reembolsos` |
| **RF-7.7** | **Historial Financiero Inmutable** | ✅ Implementado | Trazabilidad completa y auditable de todo cambio de estado financiero en la tabla `movimientos_financieros`, protegida por triggers a nivel de BD que prohíben `UPDATE` y `DELETE`. | `GET /api/v1/movimientos`<br>`Trigger PostgreSQL: trg_movimientos_financieros_inmutables` |
| **RF-7.8** | **Liquidaciones a Conductores** | ✅ Implementado | Agrupa pagos capturados de un período, calcula el subtotal, descuenta la comisión de plataforma (20%) y genera la liquidación para el beneficiario/conductor. Permite registrar transferencia y anular. | `POST /api/v1/liquidaciones`<br>`GET /api/v1/liquidaciones`<br>`GET /api/v1/liquidaciones/{id}`<br>`GET /api/v1/liquidaciones/saldos/{beneficiario_id}`<br>`POST /api/v1/liquidaciones/{id}/transferencia`<br>`POST /api/v1/liquidaciones/{id}/anulacion` |

---

## 🛡️ Requerimientos No Funcionales (RNF)

| ID | Requerimiento | Implementación en el Proyecto |
| :--- | :--- | :--- |
| **RNF-02** | **Interoperabilidad** | Contrato estandarizado OpenAPI 3.0 en `contratos/m7_tarifas/openapi.yml` verificado por tests automáticos (`test_contrato.py`). |
| **RNF-05** | **Base de datos propia del microservicio** | Instancia dedicada de PostgreSQL 16 con migraciones automáticas versionadas vía Alembic. |
| **RNF-06** | **Gestión segura de credenciales** | Secretos desacoplados en variables de entorno `.env` (nunca versionados en git); placeholder de Keycloak. |
| **RNF-08** | **Prevención de doble cobro** | Índice único parcial a nivel de base de datos `(viaje_id, tipo_operacion)` para pagos activos. |
| **RNF-12** | **Autenticación y Autorización basada en Roles** | Validación de JWT emitidos por Keycloak con verificación de firma RSA, audiencia `aud: m7-tarifas`, scopes y roles (`cliente`, `conductor`, `operador`, `servicio`). |
| **RNF-14 / RNF-19** | **Trazabilidad y Privacidad en Logs** | Middleware de correlación HTTP con `X-Request-Id` y logs en formato JSON estructurado sin incluir query params con posibles datos personales. |
| **RNF-18** | **Despliegue reproducible** | Orquestación completa mediante `docker-compose.yaml` (PostgreSQL, Keycloak y API FastAPI). |

---

## 🔗 Integraciones con otros Módulos

- **M1 (Identidad y Accesos - Keycloak):** Validación de tokens JWT y roles para control de acceso en cada endpoint.
- **M4 (Ubicación):** Estimación de distancia en kilómetros y duración en minutos para el cálculo de tarifas.
- **M6 (Viajes):** Consulta de estado de viajes y tiempos para validación de autorizaciones, capturas y cargos de cancelación.
- **M9 (Reservas):** Generación y vinculación de estimaciones de tarifa con reservas anticipadas.

