# 🚕 Módulo 7: Tarifas, Pagos y Liquidaciones

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![Keycloak](https://img.shields.io/badge/Keycloak-24.0-0097CE?style=for-the-badge&logo=Keycloak&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1?style=for-the-badge&logo=mysql&logoColor=white)

Bienvenido al repositorio del **Grupo 11**. Somos los encargados de desarrollar el Módulo 7 para el Sistema Integrado de Viajes y Transporte (TPI 2026).

---

## 📖 ¿Qué hacemos en este módulo?

Nuestro microservicio es el corazón financiero de la plataforma:

*   **🪙 Tarifas:** Calculamos el precio estimado y final de los viajes basándonos en distancia, tiempo, tipo de vehículo y parámetros de negocio configurables.
*   **💳 Pagos:** Gestionamos métodos de pago, autorizaciones, capturas, cargos de cancelación y reintegros con garantía de idempotencia.
*   **💰 Liquidaciones:** Administramos los saldos y transferencias correspondientes a los conductores tras cada ciclo de facturación.

Consulta la lista detallada en [docs/requerimientos.md](docs/requerimientos.md).

Nos integramos con los módulos de Clientes (M2), Solicitudes (M5), Viajes (M6) y Reservas (M9) a través de contratos HTTP y tokens JWT validados por Keycloak.

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

## 🛠️ Guía de Inicio Rápido

### 1. Variables de Entorno
Copia la plantilla y configura tus credenciales locales:
```bash
cp .env.example .env
```

### 2. Levantar la Infraestructura Base (Keycloak + MySQL)
```bash
docker compose up -d
```
> **Nota:** Keycloak se inicializará automáticamente con el Realm del proyecto en el puerto `8080`, y MySQL se levantará en el puerto `3306` ejecutando los scripts de inicialización de `init-db/`.

### 3. Entorno Virtual de Python y Dependencias

**En Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**En macOS / Linux (Bash / Zsh):**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Ejecutar la API en Desarrollo

Desde la raíz del proyecto:
```bash
uvicorn backend.app.main:app --reload --port 8000
```
O ingresando al directorio `backend/`:
```bash
cd backend
uvicorn main:app --reload --port 8000
```

La documentación interactiva estará disponible en:
- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- Redoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

### 5. Ejecutar Pruebas Automatizadas

```bash
pytest
```

---

## 🔒 Contratos de Seguridad (Scopes)
Los endpoints protegidos requieren tokens JWT emitidos por Keycloak con los siguientes permisos según el dominio:
*   `tarifas:read` / `tarifas:write`
*   `pagos:read` / `pagos:write`
*   `liquidaciones:read` / `liquidaciones:write`