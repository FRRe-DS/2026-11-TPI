// Muestra el estado del breaker, la cola de facturas y los rechazos.
const r = await fetch('http://localhost:3000/metricas');
console.log(await r.json());
export {};
