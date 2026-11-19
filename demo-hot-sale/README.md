# Demo Hot Sale: resiliencia y control de carga

Demo de la expo de Desarrollo de Software. Una tienda online en pleno Hot Sale depende de la API externa de un operador logístico para cotizar envíos. Cuando esa API se pone lenta, la tienda tiene que seguir cobrando.

Conceptos que muestra: timeout, reintentos, Circuit Breaker, bulkhead, rate limiting y backpressure.

## Requisitos

- Node.js 18 o más nuevo (`node -v` para ver la versión).
- Funciona igual en Windows, Mac y Linux. No hace falta curl.

## Instalación (una sola vez)

Abrir la carpeta en VS Code, abrir una terminal (Ctrl + ñ o Terminal > New Terminal) y correr:

```
npm install
```

## Qué hay en la carpeta

| Archivo | Qué es |
|---|---|
| `src/proveedor-envios.ts` | API simulada del operador logístico (puerto 4000). Se le puede cambiar el modo en vivo. |
| `src/resiliencia.ts` | Tema 1: timeout, reintentos, Circuit Breaker y fallback. |
| `src/servicio-tienda.ts` | Backend de la tienda (puerto 3000) con rate limiting y bulkhead. |
| `src/cola-facturas.ts` | Cola acotada de facturas: backpressure. |
| `scripts/` | Comandos cortos para la demo. |

## Las tres terminales

En VS Code se abren con el botón **+** del panel de terminal.

| Terminal | Comando | Para qué |
|---|---|---|
| 1 | `npm run proveedor` | Levanta el operador logístico. Queda corriendo. |
| 2 | `npm run tienda:sin-proteccion` o `npm run tienda` | Levanta la tienda. Queda corriendo. Acá aparece el log del breaker. |
| 3 | los comandos de la tabla de abajo | Desde acá se maneja la demo. |

Para cambiar la tienda de "sin protección" a "con protección": en la terminal 2, Ctrl + C y correr el otro comando.

## Comandos de la terminal 3

| Comando | Qué hace |
|---|---|
| `npm run modo:normal` | El operador responde en 80 ms. |
| `npm run modo:lento` | El operador tarda 3 segundos por respuesta. |
| `npm run modo:falla` | El operador devuelve siempre error 500. |
| `npm run modo:intermitente` | El operador falla la mitad de las veces. |
| `npm run cascada` | Manda 120 cotizaciones juntas y, mientras tanto, un pago. Muestra cuánto tardó el pago. |
| `npm run cotizar` | Pide una cotización y muestra la respuesta. Con el circuito abierto devuelve `estimado: true`. |
| `npm run metricas` | Estado del breaker, cola de facturas y cantidad de rechazos. |
| `npm run rate-limit` | 15 cotizaciones del mismo usuario. Desde la 11 responde 429. |
| `npm run facturas` | Manda 3000 pedidos de factura de golpe para mostrar backpressure. Tarda unos 30 segundos. |
| `npm run carga` | Prueba de carga con autocannon: 200 conexiones durante 10 segundos. |

## Resultados esperados

| Prueba | Sin protección | Con protección |
|---|---|---|
| `npm run cascada` con el operador lento | Pago en unos 6 s | Pago en menos de 0,1 s |
| Log de la terminal 2 | Nada | `[breaker] estado = Open` |
| `npm run cotizar` con el circuito abierto | Tarda 3 s | Inmediato, `costoEnvio: 5000, estimado: true` |
| `npm run rate-limit` | Todo 200 | 200 hasta la 10, después 429 |
| `npm run facturas` | No se usa | Unas 1000 esperas y ninguna factura perdida |

## Problemas comunes

- **`EADDRINUSE`**: el puerto ya está ocupado. Hay otra terminal con el proveedor o la tienda corriendo; cerrala con Ctrl + C.
- **`fetch failed`**: no están levantados el proveedor (terminal 1) o la tienda (terminal 2).
- **`rate-limit` da 429 desde la primera**: el límite es por minuto y ya lo usaste. Esperá un minuto o reiniciá la tienda.
- **El breaker no vuelve a cerrarse**: poné `npm run modo:normal`, esperá 15 segundos y corré `npm run cotizar`.
