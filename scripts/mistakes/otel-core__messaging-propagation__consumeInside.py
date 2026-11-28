import json
import time

from opentelemetry import context, propagate, trace
from opentelemetry.context import Context
from opentelemetry.trace import SpanKind

tracer = trace.get_tracer("pipeline")
queue: list[str] = []  # stands in for Kafka / RabbitMQ / SQS


def publish(orders: list[str]) -> None:
    with tracer.start_as_current_span("send orders", kind=SpanKind.PRODUCER) as span:
        span.set_attribute("messaging.system", "kafka")
        span.set_attribute("messaging.destination.name", "orders")
        span.set_attribute("messaging.operation.type", "send")
        for order_id in orders:
            message = {"headers": {}, "body": {"order_id": order_id}}
            queue.append(json.dumps(message))


def consume() -> None:
    # A consumer is usually another process, maybe minutes later: it starts with
    # nothing but the messages. Only what you put in the headers carries over.
    token = context.attach(Context())
    try:
        while queue:
            message = json.loads(queue.pop(0))
            with tracer.start_as_current_span("process orders", kind=SpanKind.CONSUMER) as span:
                span.set_attribute("messaging.system", "kafka")
                span.set_attribute("messaging.destination.name", "orders")
                span.set_attribute("messaging.operation.type", "process")
                span.set_attribute("app.order.id", message["body"]["order_id"])
                time.sleep(0.02)
    finally:
        context.detach(token)


with tracer.start_as_current_span("send orders", kind=SpanKind.PRODUCER):
    publish(["o-1", "o-2", "o-3"])
    consume()
