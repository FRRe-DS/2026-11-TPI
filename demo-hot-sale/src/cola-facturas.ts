// cola-facturas.ts
// Cola acotada con un consumidor lento: el ejemplo de backpressure.
type Factura = { pedidoId: string; cliente: string; total: number };

const CAPACIDAD = 1000;   // nunca guardamos más que esto en memoria
const POR_SEGUNDO = 50;   // ritmo máximo que acepta el servicio de facturación electrónica
const cola: Factura[] = [];

export const colaFacturas = {
  // Devuelve false si la cola está llena: es la señal para que el productor frene.
  encolar(item: Factura): boolean {
    if (cola.length >= CAPACIDAD) return false;
    cola.push(item);
    return true;
  },
  ocupacion: () => cola.length / CAPACIDAD,
  largo: () => cola.length,
};

// Worker: emite facturas a ritmo fijo (5 cada 100 ms), llegue lo que llegue.
setInterval(() => {
  const lote = cola.splice(0, POR_SEGUNDO / 10);
  // acá se enviaría cada factura al servicio de facturación electrónica
}, 100);
