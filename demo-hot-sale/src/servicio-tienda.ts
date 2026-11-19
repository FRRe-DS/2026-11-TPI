// servicio-tienda.ts
// Backend de la tienda online. Puerto 3000.
// PROTEGIDO=false npx tsx servicio-tienda.ts  -> versión sin políticas
import express from 'express';
import rateLimit from 'express-rate-limit';
import { bulkhead, BulkheadRejectedError, CircuitState } from 'cockatiel';
import { politicaEnvios, breaker } from './resiliencia';
import { colaFacturas } from './cola-facturas';

const PROTEGIDO = process.env.PROTEGIDO !== 'false';
const app = express();
app.use(express.json());
const metricas = { rechazos429: 0, rechazosBulkhead: 0, rechazosCola: 0 };

// ---------- Rate limiting ----------
// Global: 300 cotizaciones de envío por segundo para toda la tienda.
const limiteGlobal = rateLimit({
  windowMs: 1000, limit: 300, keyGenerator: () => 'global',
  handler: (req, res) => {
    metricas.rechazos429++;
    res.setHeader('Retry-After', '1');
    res.status(429).json({ error: 'Demasiadas solicitudes' });
  },
});
// Por usuario: 10 cotizaciones por minuto (identificado por el header x-usuario).
const limitePorUsuario = rateLimit({
  windowMs: 60_000, limit: 10, standardHeaders: 'draft-7', legacyHeaders: false,
  skip: req => !req.header('x-usuario'),
  keyGenerator: req => String(req.header('x-usuario')),
  handler: (req, res) => {
    metricas.rechazos429++;
    res.setHeader('Retry-After', '60');
    res.status(429).json({ error: 'Llegaste al límite de cotizaciones por minuto' });
  },
});
const sinFiltro: express.RequestHandler = (req, res, next) => next();

// ---------- Bulkhead ----------
// Sin protección: un único pool compartido de 50 lugares (simula el pool de
// conexiones a la base) y cola sin límite. Con protección: un compartimento
// por función y colas acotadas.
const poolCompartido = bulkhead(50, 1_000_000);
const compEnvios = PROTEGIDO ? bulkhead(20, 10) : poolCompartido;
const compCheckout = PROTEGIDO ? bulkhead(30, 30) : poolCompartido;

async function cotizarEnvio(cp: string) {
  const llamar = async (signal?: AbortSignal) => {
    const r = await fetch(`http://localhost:4000/tarifa?cp=${cp}`, { signal });
    if (!r.ok) throw new Error(`proveedor respondió ${r.status}`);
    return r.json();
  };
  return PROTEGIDO ? politicaEnvios.execute(({ signal }) => llamar(signal)) : llamar();
}

app.get('/envios/cotizar',
  PROTEGIDO ? limiteGlobal : sinFiltro,
  PROTEGIDO ? limitePorUsuario : sinFiltro,
  async (req, res) => {
    try {
      const { costo, estimado } = await compEnvios.execute(() =>
        cotizarEnvio(String(req.query.cp ?? '3400')));
      res.json({ costoEnvio: costo, estimado: Boolean(estimado) });
    } catch (err) {
      if (err instanceof BulkheadRejectedError) {
        metricas.rechazosBulkhead++;
        res.setHeader('Retry-After', '3');
        return res.status(503).json({ error: 'Alta demanda, reintentá en unos segundos' });
      }
      res.status(502).json({ error: 'No se pudo cotizar el envío' });
    }
  });

// Checkout: cobra la compra. No depende del proveedor de envíos y
// debe seguir funcionando aunque las cotizaciones estén en problemas.
app.post('/checkout', async (req, res) => {
  try {
    const compra = await compCheckout.execute(async () => {
      await new Promise(r => setTimeout(r, 50)); // simula la pasarela de pago
      return { estado: 'aprobada', total: req.body.total };
    });
    res.status(201).json(compra);
  } catch (err) {
    if (err instanceof BulkheadRejectedError) {
      metricas.rechazosBulkhead++;
      return res.status(503).json({ error: 'Checkout saturado' });
    }
    res.status(500).json({ error: 'Error en el pago' });
  }
});

// Backpressure: si la cola de facturación está llena, se le avisa al productor.
app.post('/facturas/eventos', (req, res) => {
  if (!colaFacturas.encolar(req.body)) {
    metricas.rechazosCola++;
    res.setHeader('Retry-After', '2');
    return res.status(503).json({ error: 'Cola de facturación llena' });
  }
  res.status(202).json({ encolado: true, ocupacion: colaFacturas.ocupacion() });
});

// Evidencias para la demo.
app.get('/metricas', (req, res) => res.json({
  protegido: PROTEGIDO, breaker: CircuitState[breaker.state],
  colaFacturas: colaFacturas.largo(), ...metricas,
}));

app.listen(3000, () => console.log(`Tienda en :3000 (protegido=${PROTEGIDO})`));
