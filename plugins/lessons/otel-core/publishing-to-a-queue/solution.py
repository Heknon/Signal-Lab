import time

from opentelemetry import trace
from opentelemetry.trace import SpanKind

tracer = trace.get_tracer("prices")


def fake_http_get(url: str) -> int:
    time.sleep(0.03)
    return 200


def http_get(url: str, host: str, peer: str) -> int:
    with tracer.start_as_current_span("GET", kind=SpanKind.CLIENT) as span:
        span.set_attribute("http.request.method", "GET")
        span.set_attribute("url.full", url)
        span.set_attribute("server.address", host)
        span.set_attribute("peer.service", peer)
        status = fake_http_get(url)
        span.set_attribute("http.response.status_code", status)
        return status


def publish(update: dict) -> None:
    with tracer.start_as_current_span("send price-updates", kind=SpanKind.PRODUCER) as span:
        span.set_attribute("messaging.system", "kafka")
        span.set_attribute("messaging.destination.name", "price-updates")
        span.set_attribute("messaging.operation.type", "send")
        span.set_attribute("messaging.operation.name", "send")
        time.sleep(0.005)  # hand the message to the broker


with tracer.start_as_current_span("refresh prices"):
    http_get("https://eu.prices.example/v1/quotes?sku=TEL-001", "eu.prices.example", "price-api")
    http_get("https://us.prices.example/v1/quotes?sku=TEL-001", "us.prices.example", "price-api")
    http_get("https://fx.example/v1/rates?base=EUR", "fx.example", "fx-rates")
    publish({"sku": "TEL-001", "price_eur": 19.90})
