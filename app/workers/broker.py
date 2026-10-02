from faststream.rabbit import RabbitBroker, RabbitExchange, RabbitQueue

from app.core.config import settings

broker = RabbitBroker(settings.rabbitmq_url)

# Explicit topology: normal payment events and a dead-letter exchange/queue.
PAYMENTS_EXCHANGE = RabbitExchange("payments", durable=True)
DLX = RabbitExchange("payments.dlx", durable=True)

PAYMENTS_QUEUE = RabbitQueue(
    "payments.new",
    durable=True,
    routing_key="payments.new",
    arguments={
        "x-dead-letter-exchange": "payments.dlx",
        "x-dead-letter-routing-key": "payments.dlq",
    },
)
DLQ = RabbitQueue("payments.dlq", durable=True, routing_key="payments.dlq")

DLQ_PUBLISHER = broker.publisher(
    queue=DLQ,
    exchange=DLX,
    routing_key="payments.dlq",
)
