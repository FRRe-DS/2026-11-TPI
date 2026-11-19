// Momento clave de la demo: 120 cotizaciones simultáneas y, mientras tanto, un pago.
// Muestra cuánto tarda el checkout. Sin protección tarda segundos; con bulkhead, milisegundos.
const cotizaciones = Array.from({ length: 120 }, () =>
  fetch('http://localhost:3000/envios/cotizar?cp=3400').then(r => r.status).catch(() => 0));

await new Promise(r => setTimeout(r, 500));

const inicio = performance.now();
const pago = await fetch('http://localhost:3000/checkout', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ total: 85000 }),
});
const segundos = ((performance.now() - inicio) / 1000).toFixed(2);
console.log(`\nCheckout: HTTP ${pago.status} en ${segundos} s\n`);

const codigos = await Promise.all(cotizaciones);
const resumen: Record<string, number> = {};
for (const c of codigos) resumen[c] = (resumen[c] ?? 0) + 1;
console.log('Respuestas de las 120 cotizaciones (código: cantidad):', resumen);
export {};
