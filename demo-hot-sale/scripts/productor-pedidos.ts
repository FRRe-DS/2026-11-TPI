// productor-pedidos.ts
// Simula el servicio de pedidos: por cada compra confirmada pide emitir una factura.
// Respeta la señal de backpressure: ante un 503 espera lo que indica Retry-After.
async function pedirFactura(evento: object) {
  while (true) {
    const r = await fetch('http://localhost:3000/facturas/eventos', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(evento),
    });
    if (r.status !== 503) return;
    const espera = Number(r.headers.get('retry-after') ?? 1) * 1000;
    console.log(`[productor] cola llena, espero ${espera} ms`);
    await new Promise(ok => setTimeout(ok, espera));
  }
}

export {}; // hace que el archivo sea un módulo (permite await de primer nivel)

// Medianoche del Hot Sale: 3000 compras se confirman casi a la vez.
const eventos = Array.from({ length: 3000 }, (_, i) =>
  ({ pedidoId: `p${i}`, cliente: `cli${i % 500}`, total: 85000 }));
for (let i = 0; i < eventos.length; i += 100) {
  await Promise.all(eventos.slice(i, i + 100).map(pedirFactura));
}
console.log('[productor] todas las facturas fueron aceptadas');
