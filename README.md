# 🚕 Módulo 7: Tarifas, Pagos y Liquidaciones

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![Keycloak](https://img.shields.io/badge/Keycloak-24.0-0097CE?style=for-the-badge&logo=Keycloak&logoColor=white)
![Supabase](https://img.shields.io/badge/Supabase-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)

Bienvenido al repositorio del **Grupo 11**. Somos los encargados de desarrollar el Módulo 7 para el Sistema Integrado de Viajes y Transporte (TPI 2026).

---

## 📖 ¿Qué hacemos en este módulo?

Nuestro microservicio es el corazón financiero de la plataforma. Nos encargamos de que los números cuadren para todas las partes involucradas:

*   **🪙 Tarifas:** Calculamos el precio estimado y final de los viajes basándonos en distancia, tiempo, demanda y reglas de negocio dinámicas.
*   **💳 Pagos:** Gestionamos las transacciones y cobros a los pasajeros, integrándonos con pasarelas de pago externas.
*   **💰 Liquidaciones:** Administramos los saldos y las transferencias correspondientes a los choferes y dueños de los vehículos tras cada ciclo de facturación.

Nos integramos estrechamente con los módulos de Reservas (M9), Viajes (M6), Clientes (M2) y Solicitudes (M5) a través de tokens JWT firmados y validados por nuestra infraestructura de seguridad.

---

## 👥 Integrantes del Equipo

*   👤 **Godoy Marianela Yasmin**
*   👤 **Martínez Carlos Exequiel**
*   👤 **Ocampo Santiago Mariano**
*   👤 **Pare Collante Agustina**
*   👤 **Quiroz Marina de los Milagros**
*   👤 **Sanchez Romina**
*   👤 **Salas Juliana**
*   👤 **Sarachaga Lautaro Leonel**
*   👤 **Toledo Francisco Santiago** 
---

## 🛠️ Guía de Inicio Rápido (Para el equipo)

Si acabas de clonar este repositorio, sigue estos pasos para levantar el entorno de desarrollo local:

### 1. Variables de Entorno
Copia el archivo de plantilla y renómbralo para configurarlo en tu máquina:
```bash
cp .env.example .env
```
*(Solicita las credenciales de Supabase y el Client Secret al administrador de infraestructura del equipo).*

### 2. Levantar la Infraestructura Base
El proyecto utiliza Docker para orquestar la seguridad local mediante Keycloak. Ejecuta:
```bash
docker compose up -d
```
> **Nota:** Keycloak se inicializará automáticamente con el Realm del proyecto y todos los Client Scopes (`tarifas:read`, `pagos:write`, etc.) gracias al volumen de autoconfiguración.

### 3. Ejecutar la API
Con Docker, el paso anterior ya levanta la API en `http://localhost:8000`. Para correrla localmente:
```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
La documentación interactiva queda en `http://localhost:8000/docs`. Con `AUTH_DISABLED=true` en el `.env` se puede probar sin token.

### 4. Probar con un token real
El realm incluye el client confidencial `m7-tarifas` (service account con los 6 scopes del módulo). Su secret está en `realm-config/ds-2026-realm.json` (`clients` → `m7-tarifas` → `secret`) y solo sirve para el Keycloak local.
```bash
curl -s -d grant_type=client_credentials -d client_id=m7-tarifas -d client_secret=<secret> \
  http://localhost:8080/realms/ds-2026-realm/protocol/openid-connect/token
# Usar el access_token devuelto:
curl -H "Authorization: Bearer <access_token>" http://localhost:8000/api/v1/tarifas/reglas
```

> **Nota:** por ahora los datos se guardan en memoria (`app/services/store.py`) y se pierden al reiniciar, hasta conectar Supabase.

---

## 🔌 Endpoints (`/api/v1`)

| Método | Ruta | Scope | Descripción |
|---|---|---|---|
| POST | `/tarifas/estimaciones` | `tarifas:read` | Precio estimado de un viaje |
| POST | `/tarifas/viajes/{viaje_id}/tarifa-final` | `tarifas:write` | Calcula y registra el precio final al terminar el viaje |
| GET | `/tarifas/viajes/{viaje_id}/tarifa-final` | `tarifas:read` | Consulta la tarifa final |
| GET | `/tarifas/reglas` | `tarifas:read` | Lista reglas de tarifa |
| GET | `/tarifas/reglas/{regla_id}` | `tarifas:read` | Detalle de una regla |
| POST | `/tarifas/reglas` | `tarifas:write` | Crea una regla (reemplaza la activa del mismo vehículo) |
| PATCH | `/tarifas/reglas/{regla_id}` | `tarifas:write` | Modifica una regla |
| POST | `/pagos` | `pagos:write` | Registra un pago (acepta `Idempotency-Key`) |
| GET | `/pagos` | `pagos:read` | Lista pagos (filtros: viaje, cliente, beneficiario, estado) |
| GET | `/pagos/{pago_id}` | `pagos:read` | Detalle de un pago |
| POST | `/pagos/{pago_id}/reembolsos` | `pagos:write` | Reembolso total o parcial |
| GET | `/pagos/{pago_id}/reembolsos` | `pagos:read` | Reembolsos de un pago |
| POST | `/pagos/webhooks/pasarela` | header `X-Webhook-Secret` | Confirmación de la pasarela externa |
| POST | `/liquidaciones` | `liquidaciones:write` | Genera la liquidación de un beneficiario para un período |
| GET | `/liquidaciones` | `liquidaciones:read` | Lista liquidaciones |
| GET | `/liquidaciones/{liquidacion_id}` | `liquidaciones:read` | Detalle de una liquidación |
| GET | `/liquidaciones/saldos/{beneficiario_id}` | `liquidaciones:read` | Saldo de un chofer/dueño |
| POST | `/liquidaciones/{liquidacion_id}/transferencia` | `liquidaciones:write` | Confirma la transferencia |
| POST | `/liquidaciones/{liquidacion_id}/anulacion` | `liquidaciones:write` | Anula y libera los pagos |

---

## 🔒 Contratos de Seguridad (Scopes)
Para los demás grupos que necesiten consumir nuestra API, los endpoints requerirán tokens JWT emitidos por Keycloak con los siguientes permisos según el dominio:
*   `tarifas:read` / `tarifas:write`
*   `pagos:read` / `pagos:write`
*   `liquidaciones:read` / `liquidaciones:write`