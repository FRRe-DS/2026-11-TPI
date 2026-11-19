// Pide una cotización de envío y muestra la respuesta.
const r = await fetch('http://localhost:3000/envios/cotizar?cp=3400');
console.log(`HTTP ${r.status}`, await r.json());
export {};
