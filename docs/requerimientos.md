# 📋 Requerimientos Funcionales - M7: Tarifas, Pagos y Liquidaciones

| ID | Requerimiento | Estado | Descripción Funcional | Endpoints Asociados |
| :--- | :--- | :---: | :--- | :--- |
| **RF-7.1** | **Estimación de tarifa** | ✅ Implementado | El sistema deberá calcular una estimación basada en tipo de vehículo, distancia, tiempo y parámetros configurables. | `POST /tarifas/estimar`<br>`GET /tarifas/parametros` |
| **RF-7.2** | **Método de pago** | ✅ Implementado | El cliente deberá poder registrar o seleccionar un medio de pago permitido por el escenario (tarjeta, billetera virtual, efectivo). | `POST /pagos/medios`<br>`GET /pagos/medios/{cliente_id}` |
| **RF-7.3** | **Autorización y captura** | ✅ Implementado | El sistema deberá simular o integrar la autorización y captura del pago conforme al estado del viaje. | `POST /pagos/autorizar`<br>`POST /pagos/capturar` |
| **RF-7.4** | **Cargo de cancelación** | ✅ Implementado | El sistema deberá calcular y registrar un cargo de cancelación cuando las reglas lo indiquen. | `POST /pagos/cancelar` |
| **RF-7.5** | **Reintegro** | ✅ Implementado | El sistema deberá registrar un reintegro total o parcial ante una cancelación o ajuste válido posterior al cobro. | `POST /pagos/reintegrar` |
| **RF-7.6** | **Idempotencia de pago** | ✅ Implementado | La repetición de una misma orden de cobro o reintegro no deberá generar operaciones financieras duplicadas mediante `idempotency_key`. | En todas las operaciones de pago y liquidación |
| **RF-7.7** | **Historial financiero** | ✅ Implementado | El sistema deberá conservar la trazabilidad de autorizaciones, capturas, rechazos, cargos y reintegros. | `GET /pagos/{viaje_id}/historial`<br>`GET /pagos/{viaje_id}` |
| **RF-7.8** | **Liquidación al conductor** | ✅ Implementado | El sistema deberá calcular o simular el importe a liquidar al conductor y registrar su estado. | `POST /liquidaciones`<br>`GET /liquidaciones/{conductor_id}` |

---

### Integración con otros módulos

- **M2 (Clientes):** Provee el `cliente_id` para medios de pago y cobros.
- **M6 (Viajes):** Provee `viaje_id`, `conductor_id`, distancia y tiempos de viajes completados o cancelados.
- **M9 (Reservas):** Consume estimaciones de tarifas preliminares.
