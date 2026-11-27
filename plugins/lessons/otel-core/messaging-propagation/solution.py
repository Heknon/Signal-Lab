import json
import time

from opentelemetry import propagate, trace
from opentelemetry.trace import SpanKind

tracer = trace.get_tracer("pipeline")
queue: list[str] = []  # stands in for Kafka / RabbitMQ / SQS


def publish(orders: list[str]) -> None:
    with tracer.start_as_current_span("orders publish", kind=SpanKind.PRODUCER):
        for order_id in orders:
            message = {"headers": {}, "body": {"order_id": order_id}}
            propagate.inject(message["headers"])
            queue.append(json.dumps(message))


def consume() -> None:
    while queue:
        message = json.loads(queue.pop(0))
        ctx = propagate.extract(message["headers"])
        with tracer.start_as_current_span("orders process", context=ctx, kind=SpanKind.CONSUMER) as span:
            span.set_attribute("app.order.id", message["body"]["order_id"])
            time.sleep(0.02)


publish(["o-1", "o-2", "o-3"])
consume()
