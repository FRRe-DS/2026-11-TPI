# 🚕 Módulo 7: Tarifas, Pagos y Liquidaciones

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![Keycloak](https://img.shields.io/badge/Keycloak-24.0-0097CE?style=for-the-badge&logo=Keycloak&logoColor=white)

Bienvenido al repositorio del **Grupo 11**. Somos los encargados de desarrollar el Módulo 7 para el Sistema Integrado de Viajes y Transporte (TPI 2026).

---

## 📖 ¿Qué hacemos en este módulo?

Nuestro microservicio es el corazón financiero de la plataforma. Nos encargamos de que los números cuadren para todas las partes involucradas:

*   **🪙 Tarifas (RF-7.1):** estimamos el precio de un viaje (por distancia y tiempo, o consultando la ruta a M4), guardamos la estimación con vencimiento y calculamos la tarifa final.
*   **💳 Pagos (RF-7.2 a RF-7.7):** registramos medios de pago sin guardar datos de tarjeta, autorizamos al asignarse el viaje y capturamos al finalizar, calculamos el cargo de cancelación, hacemos reembolsos y dejamos un historial financiero inmutable.
*   **💰 Liquidaciones (RF-7.8):** liquidamos a los conductores lo cobrado, descontamos la comisión de la plataforma y registramos la transferencia.

Nos integramos con Reservas (M9), Viajes (M6), Ubicación (M4) y Solicitudes (M5) mediante su API y tokens JWT de M1 (Keycloak).

📄 Documentación: [contrato OpenAPI](contratos/m7_tarifas/openapi.yml) · [catálogo de eventos](docs/eventos.md) · [decisiones y supuestos](docs/decisiones.md)

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

Requisitos: Docker con Docker Compose. Para correr la API o los tests fuera de Docker, Python 3.11.

### 1. Variables de entorno
```bash
cp .env.example .env
```
Completá como mínimo `KC_PASSWORD`, `POSTGRES_PASSWORD` y `M7_CLIENT_SECRET`. Para generar valores:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```
El `.env` nunca se sube al repositorio. La tabla completa de variables está más abajo.

### 2. Levantar todo
```bash
docker compose up -d --build
```
Levanta PostgreSQL, Keycloak (con el realm `ds-2026-realm` importado) y la API. La API **aplica las migraciones sola al arrancar** y queda en:

*   API: `http://localhost:8000` · salud: `http://localhost:8000/health`
*   Documentación interactiva: `http://localhost:8000/docs`
*   Consola de Keycloak: `http://localhost:8080` (usuario `admin`, contraseña `KC_PASSWORD`)

### 3. Migraciones
Las migraciones están en `backend/alembic/versions`. `0001` crea el esquema y `0002` carga las reglas de tarifa iniciales de auto y moto.
```bash
docker compose exec api alembic upgrade head        # aplicar (ya se hace al arrancar)
docker compose exec api alembic current             # ver la versión aplicada
cd backend && alembic revision -m "descripcion"     # crear una nueva (con DATABASE_URL apuntando a la base)
```

### 4. Correr la API fuera de Docker
```bash
docker compose up -d postgres keycloak
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload
```
Fuera de Docker, la API lee `backend/.env` (o las variables del entorno). Usá `DATABASE_URL=postgresql+psycopg://m7:<POSTGRES_PASSWORD>@localhost:5432/m7`. Con `AUTH_DISABLED=true` se puede probar sin token: el usuario actúa como operador.

---

## 🧪 Tests y calidad

Los tests de integración usan un PostgreSQL real y descartable (servicio `db-test`, puerto 5433). **Un solo comando** corre las pruebas unitarias y las de integración, y exige 80 % de cobertura sobre `app/`:
```bash
docker compose --profile test up -d db-test
cd backend
export TEST_DATABASE_URL=postgresql+psycopg://test:test@localhost:5433/m7_test   # PowerShell: $env:TEST_DATABASE_URL="..."
pytest
```
Sin `TEST_DATABASE_URL`, los tests de integración se saltean y la cobertura no llega al mínimo.

| Carpeta | Qué prueba |
|---|---|
| `tests/unit` | Lógica pura, sin base ni red: tarifa, cargo de cancelación, comisión, saldo, transiciones, reembolsos, idempotencia, schemas, JWT, pasarela, clientes HTTP (con transporte simulado) y que el contrato OpenAPI coincida con la API. |
| `tests/integracion` | API completa contra PostgreSQL con la pasarela simulada y stubs de M4, M6 y M9: flujo completo, cancelaciones, reembolsos, 401/403, problem+json, concurrencia (cobros, capturas, reembolsos y liquidaciones en paralelo) y restricciones de la base. |

Los tokens de prueba se firman con un par de claves RSA generado en el momento: no hace falta Keycloak.

Lint y formato:
```bash
ruff check .
ruff format .
```
GitHub Actions (`.github/workflows/ci.yml`) corre lint, formato y tests con un PostgreSQL de servicio en cada push y pull request, y después construye la imagen.

---

## 🔑 Cómo pedir un token para probar

Los tokens deben traer `aud: m7-tarifas` (lo agrega el realm a todo token con un scope de M7), el scope de la operación y un rol: `cliente`, `conductor`, `operador` o `servicio`.

**Como módulo (rol `servicio`)**, con el client confidencial `m7-tarifas`:
```bash
curl -s -d grant_type=client_credentials -d client_id=m7-tarifas -d client_secret=$M7_CLIENT_SECRET \
  http://localhost:8080/realms/ds-2026-realm/protocol/openid-connect/token
```

**Como cliente, conductor u operador:**
1. En la consola de Keycloak (realm `ds-2026-realm`), creá un usuario, asignale una contraseña sin marcarla como temporal y asignale el rol de realm que corresponda. El `sub` del usuario es su `cliente_id` o `beneficiario_id`.
2. Pedí el token con el client público `m7-pruebas`:
```bash
curl -s -d grant_type=password -d client_id=m7-pruebas -d username=<usuario> -d password=<contraseña> \
  http://localhost:8080/realms/ds-2026-realm/protocol/openid-connect/token
```

Usá el `access_token` devuelto:
```bash
curl -H "Authorization: Bearer <access_token>" http://localhost:8000/api/v1/tarifas/reglas
```

### Regenerar el secreto de `m7-tarifas`
El realm toma el secreto de `M7_CLIENT_SECRET` (placeholder `${M7_CLIENT_SECRET}` en `realm-config/ds-2026-realm.json`) y solo lo lee **la primera vez** que importa el realm. Para cambiarlo:
*   Con el realm ya importado: consola → *Clients* → `m7-tarifas` → *Credentials* → *Regenerate*, y copiá el valor a `M7_CLIENT_SECRET` en tu `.env`.
*   O bien recreá Keycloak (`docker compose up -d --force-recreate keycloak`) con el nuevo valor en el `.env`.

> El secreto que estaba antes en el archivo del realm quedó en el historial de git: no lo reutilicen en ningún entorno publicado.

---

## ⚙️ Variables de entorno

| Variable | Por defecto | Uso |
|---|---|---|
| `KC_PASSWORD` | — (obligatoria) | Contraseña del admin de Keycloak local |
| `M7_CLIENT_SECRET` | — (obligatoria) | Secreto del client `m7-tarifas` |
| `POSTGRES_DB` / `POSTGRES_USER` | `m7` / `m7` | Base de M7 |
| `POSTGRES_PASSWORD` | — (obligatoria) | Contraseña de la base de M7 |
| `DATABASE_URL` | armada por el compose | `postgresql+psycopg://usuario:clave@host:puerto/base` |
| `TEST_DATABASE_URL` | — | Base descartable para los tests de integración |
| `KEYCLOAK_ISSUER_URI` / `KEYCLOAK_JWKS_URI` | realm local | Validación del JWT |
| `KEYCLOAK_AUDIENCE` | `m7-tarifas` | Audiencia exigida en el token |
| `AUTH_DISABLED` | `false` | `true` omite el token (solo desarrollo) |
| `PASARELA_WEBHOOK_SECRET` | — | Secreto compartido del webhook (sin él, el webhook responde 401) |
| `PASARELA_TIMEOUT_S` | `3` | Espera máxima por llamada a la pasarela |
| `COMISION_PLATAFORMA` | `0.20` | Comisión que retiene la plataforma |
| `ESTIMACION_VIGENCIA_MIN` | `15` | Vigencia de una estimación |
| `CANCELACION_PERIODO_GRACIA_MIN` | `5` | Minutos sin cargo después de la asignación |
| `CANCELACION_CARGO_ASIGNADO` | `500` | Cargo pasado el período de gracia |
| `CANCELACION_CARGO_CONDUCTOR_EN_PUNTO` | `1000` | Cargo si el conductor ya llegó |
| `M4_UBICACION_URL` / `M6_VIAJES_URL` / `M9_RESERVAS_URL` | vacío | URL de cada módulo; vacío = integración deshabilitada |
| `INTEGRACIONES_TIMEOUT_S` / `INTEGRACIONES_REINTENTOS` | `2` / `1` | Espera por intento y reintentos hacia otros módulos |

---

## 🔌 Endpoints (`/api/v1`)

El detalle (cuerpos, errores y ejemplos) está en el [contrato OpenAPI](contratos/m7_tarifas/openapi.yml).

| Método | Ruta | Scope | Roles | Descripción |
|---|---|---|---|---|
| POST | `/tarifas/estimaciones` | `tarifas:read` | todos | Estima y guarda la estimación |
| GET | `/tarifas/estimaciones/{id}` | `tarifas:read` | todos | Consulta una estimación |
| POST | `/tarifas/viajes/{viaje_id}/tarifa-final` | `tarifas:write` | servicio, operador | Tarifa final al terminar el viaje |
| GET | `/tarifas/viajes/{viaje_id}/tarifa-final` | `tarifas:read` | todos | Consulta la tarifa final |
| GET | `/tarifas/reglas`, `/tarifas/reglas/{id}` | `tarifas:read` | todos | Reglas de tarifa |
| POST/PATCH | `/tarifas/reglas`, `/tarifas/reglas/{id}` | `tarifas:write` | operador | Crea o modifica reglas |
| POST | `/metodos-pago` | `pagos:write` | cliente, operador | Registra un medio de pago |
| GET | `/metodos-pago`, `/metodos-pago/{id}` | `pagos:read` | cliente (propios), operador, servicio | Consulta medios de pago |
| DELETE | `/metodos-pago/{id}` | `pagos:write` | cliente (propios), operador | Baja lógica |
| POST | `/pagos` | `pagos:write` | cliente (propio), servicio, operador | Crea y autoriza el cobro (`Idempotency-Key`) |
| GET | `/pagos`, `/pagos/{id}` | `pagos:read` | todos (cada uno lo suyo) | Consulta pagos |
| POST | `/pagos/{id}/captura` | `pagos:write` | servicio, operador | Captura al finalizar el viaje |
| POST | `/pagos/{id}/anulacion` | `pagos:write` | servicio, operador | Libera la autorización |
| POST | `/pagos/{id}/reembolsos` | `pagos:write` | servicio, operador | Reembolso total o parcial (`Idempotency-Key`) |
| GET | `/pagos/{id}/reembolsos` | `pagos:read` | todos (cada uno lo suyo) | Reembolsos de un pago |
| POST | `/pagos/webhooks/pasarela` | header `X-Webhook-Secret` | — | Resultado diferido de la pasarela |
| POST | `/cancelaciones` | `pagos:write` | cliente (propio), servicio, operador | Cargo de cancelación |
| GET | `/cancelaciones/{viaje_id}` | `pagos:read` | cliente (propio), operador, servicio | Consulta la cancelación |
| GET | `/movimientos` | `pagos:read` | todos (cada uno lo suyo) | Historial financiero inmutable |
| POST | `/liquidaciones` | `liquidaciones:write` | operador, servicio | Genera la liquidación de un período |
| GET | `/liquidaciones`, `/liquidaciones/{id}` | `liquidaciones:read` | conductor (propias), operador, servicio | Consulta liquidaciones |
| GET | `/liquidaciones/saldos/{beneficiario_id}` | `liquidaciones:read` | conductor (propio), operador, servicio | Saldo del conductor |
| POST | `/liquidaciones/{id}/transferencia` | `liquidaciones:write` | operador | Confirma la transferencia |
| POST | `/liquidaciones/{id}/anulacion` | `liquidaciones:write` | operador | Anula y libera los pagos |

Todas las respuestas de error son `application/problem+json` (RFC 9457) y toda respuesta devuelve `X-Request-Id`.

### Ciclo de un pago
```
                      ┌──────────────► rechazado
POST /pagos ──► pendiente_confirmacion ──► autorizado ──► captura_pendiente ──► capturado ──► reembolsado_parcial ──► reembolsado
   (efectivo ────────────────────────────►)    │                                    ▲   └──────────────────────────────────►
                                               ├──► anulado                         │
                                               └────────────────────────────────────┘ (respuesta inmediata)
```
`pendiente_confirmacion` y `captura_pendiente` aparecen solo si la pasarela no responde a tiempo y se resuelven por webhook.

### Pasarela simulada
Toda tarjeta válida (Luhn) se aprueba, salvo dos tarjetas de prueba: `4000000000000002`, que se rechaza, y `4000000000000119`, que no responde y deja el pago en `pendiente_confirmacion`.
