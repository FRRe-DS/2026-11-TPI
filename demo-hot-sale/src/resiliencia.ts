// resiliencia.ts
// Políticas del Tema 1 alrededor de la llamada al proveedor de envíos (cockatiel).
import {
  circuitBreaker, retry, timeout, fallback, wrap,
  handleAll, handleWhen, ExponentialBackoff, SamplingBreaker,
  TimeoutStrategy, BrokenCircuitError, CircuitState,
} from 'cockatiel';

// 1) Timeout por intento: si el proveedor no responde en 800 ms, se corta.
//    Aggressive + AbortSignal cancela de verdad el fetch.
const porIntento = timeout(800, TimeoutStrategy.Aggressive);

// 2) Circuit Breaker: abre si falla el 50 % de las llamadas en una ventana
//    de 10 s (con al menos 5 llamadas por segundo). A los 15 s pasa a
//    semiabierto y deja pasar una llamada de prueba.
export const breaker = circuitBreaker(handleAll, {
  halfOpenAfter: 15_000,
  breaker: new SamplingBreaker({ threshold: 0.5, duration: 10_000, minimumRps: 5 }),
});

// 3) Reintentos: hasta 2 reintentos con backoff exponencial y jitter.
//    Con el circuito abierto NO se reintenta (sería insistir contra una pared).
const reintentos = retry(
  handleWhen(err => !(err instanceof BrokenCircuitError)),
  { maxAttempts: 2, backoff: new ExponentialBackoff({ initialDelay: 100, maxDelay: 400 }) },
);

// 4) Respaldo: si todo falla, tarifa plana de envío marcada como estimada.
const respaldo = fallback(handleAll, () => ({ costo: 5000, estimado: true }));

// Orden de afuera hacia adentro: respaldo > reintentos > breaker > timeout > llamada
export const politicaEnvios = wrap(respaldo, reintentos, breaker, porIntento);

breaker.onStateChange(estado => console.log(`[breaker] estado = ${CircuitState[estado]}`));
