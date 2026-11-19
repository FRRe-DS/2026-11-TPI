// 15 cotizaciones seguidas del mismo usuario: desde la 11 debería responder 429.
for (let i = 1; i <= 15; i++) {
  const r = await fetch('http://localhost:3000/envios/cotizar?cp=3400', { headers: { 'x-usuario': 'demo' } });
  console.log(`Cotización ${String(i).padStart(2)}: HTTP ${r.status}`);
}
export {};
