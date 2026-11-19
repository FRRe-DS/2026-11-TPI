// Cambia el comportamiento del operador logístico: normal, lento, falla o intermitente.
const modo = process.argv[2] ?? 'normal';
const r = await fetch('http://localhost:4000/admin/modo', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ modo }),
});
console.log('Operador logístico en modo:', (await r.json()).modo);
export {};
