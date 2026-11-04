import asyncio
import json

import aio_pika
from aio_pika import ExchangeType

from app.core.config import settings
from app.core.database import asegurar_esquema_contrato
from app.messaging.handlers import procesar_viaje_finalizado


async def consume_viaje_finalizado() -> None:
    asegurar_esquema_contrato()
    while True:
        try:
            connection = await aio_pika.connect_robust(
                host=settings.RABBITMQ_HOST,
                port=settings.RABBITMQ_PORT,
                virtualhost=settings.RABBITMQ_VHOST,
                login=settings.RABBITMQ_USER,
                password=settings.RABBITMQ_PASSWORD,
            )
            break
        except (aio_pika.exceptions.AMQPException, OSError, ConnectionError) as exc:
            print(f"RabbitMQ aun no disponible: {exc}. Reintentando en 5 segundos...", flush=True)
            await asyncio.sleep(5)

    async with connection:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=10)

        exchange = await channel.declare_exchange(
            settings.RABBITMQ_EXCHANGE,
            ExchangeType.TOPIC,
            durable=True,
        )
        queue = await channel.declare_queue(
            "m7.viaje.finalizado",
            durable=True,
        )
        await queue.bind(exchange, "viaje.finalizado")

        async with queue.iterator() as messages:
            async for message in messages:
                async with message.process(requeue=True):
                    event = json.loads(message.body.decode("utf-8"))
                    if event.get("event_type") != "viaje.finalizado":
                        continue
                    await asyncio.to_thread(procesar_viaje_finalizado, event)


if __name__ == "__main__":
    asyncio.run(consume_viaje_finalizado())
