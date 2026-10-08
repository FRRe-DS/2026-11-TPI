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
*(Instrucciones pendientes hasta la definición del gestor de paquetes de Python: pip/poetry).*

---

## 🔒 Contratos de Seguridad (Scopes)
Para los demás grupos que necesiten consumir nuestra API, los endpoints requerirán tokens JWT emitidos por Keycloak con los siguientes permisos según el dominio:
*   `tarifas:read` / `tarifas:write`
*   `pagos:read` / `pagos:write`
*   `liquidaciones:read` / `liquidaciones:write`