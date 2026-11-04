import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

import aio_pika
from aio_pika import DeliveryMode, ExchangeType, Message

from app.core.config import settings


async def publish_event(
    routing_key: str,
    event_type: str,
    data: Dict[str, Any],
    *,
    source: str = "m7",
    event_id: str | None = None,
) -> str:
    resolved_event_id = event_id or str(uuid.uuid4())
    event = {
        "event_id": resolved_event_id,
        "event_type": event_type,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "version": 1,
        "data": data,
    }

    connection = await aio_pika.connect_robust(
        host=settings.RABBITMQ_HOST,
        port=settings.RABBITMQ_PORT,
        virtualhost=settings.RABBITMQ_VHOST,
        login=settings.RABBITMQ_USER,
        password=settings.RABBITMQ_PASSWORD,
    )
    async with connection:
        channel = await connection.channel()
        exchange = await channel.declare_exchange(
            settings.RABBITMQ_EXCHANGE,
            ExchangeType.TOPIC,
            durable=True,
        )
        await exchange.publish(
            Message(
                json.dumps(event, default=str, ensure_ascii=False).encode("utf-8"),
                content_type="application/json",
                delivery_mode=DeliveryMode.PERSISTENT,
                message_id=resolved_event_id,
                correlation_id=resolved_event_id,
            ),
            routing_key=routing_key,
        )
    return resolved_event_id
