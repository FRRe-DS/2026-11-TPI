// proveedor-envios.ts
// Simula la API externa del operador logístico que cotiza envíos. Puerto 4000.
import express from 'express';

const app = express();
app.use(express.json());

type Modo = 'normal' | 'lento' | 'falla' | 'intermitente';
let modo: Modo = 'normal';
const esperar = (ms: number) => new Promise(r => setTimeout(r, ms));

// Durante la demo cambiamos el comportamiento en vivo.
app.post('/admin/modo', (req, res) => {
  modo = req.body.modo;
  console.log(`[proveedor] modo = ${modo}`);
  res.json({ modo });
});

app.get('/tarifa', async (req, res) => {
  if (modo === 'lento') await esperar(3000);
  if (modo === 'falla') return res.status(500).json({ error: 'proveedor caído' });
  if (modo === 'intermitente' && Math.random() < 0.5) {
    return res.status(503).json({ error: 'sobrecarga' });
  }
  await esperar(80); // latencia normal
  res.json({ cp: req.query.cp, costo: 4200 });
});

app.listen(4000, () => console.log('Proveedor de envíos en :4000'));
