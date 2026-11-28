import time

from opentelemetry import propagate, trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.trace import SpanKind

tracer = trace.get_tracer("prices")

# The price API is another service, so it gets its own TracerProvider: its
# resource says service.name=price-api. (In production it is another process,
# and opentelemetry-instrument sets this up from OTEL_SERVICE_NAME.)
api_provider = TracerProvider(resource=Resource.create({"service.name": "price-api"}))
api_provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter()))
api_tracer = api_provider.get_tracer("price-api")


def price_api(path: str, headers: dict) -> int:
    """The price API's request handler."""
    ctx = propagate.extract(headers)  # continue the caller's trace
    with api_tracer.start_as_current_span("GET /v1/quotes", context=ctx, kind=SpanKind.SERVER) as span:
        span.set_attribute("http.request.method", "GET")
        span.set_attribute("http.route", "/v1/quotes")
        time.sleep(0.02)  # look up the quote
        span.set_attribute("http.response.status_code", 200)
        return 200


def fake_network(url: str, headers: dict) -> int:
    """Deliver a request. The price API is ours; fx.example is a third party."""
    time.sleep(0.005)
    if ".prices.example/" in url:
        return price_api(url.split(".example", 1)[1], headers)
    time.sleep(0.03)
    return 200


def http_get(url: str, host: str, peer: str) -> int:
    with tracer.start_as_current_span("GET", kind=SpanKind.CLIENT) as span:
        span.set_attribute("http.request.method", "GET")
        span.set_attribute("url.full", url)
        span.set_attribute("server.address", host)
        span.set_attribute("peer.service", peer)
        headers: dict[str, str] = {}
        propagate.inject(headers)  # traceparent travels with the request
        status = fake_network(url, headers)
        span.set_attribute("http.response.status_code", status)
        return status


def publish(update: dict) -> None:
    with tracer.start_as_current_span("send price-updates", kind=SpanKind.PRODUCER) as span:
        span.set_attribute("messaging.system", "kafka")
        span.set_attribute("messaging.destination.name", "price-updates")
        span.set_attribute("messaging.operation.type", "send")
        span.set_attribute("messaging.operation.name", "send")
        time.sleep(0.005)


with tracer.start_as_current_span("refresh prices"):
    http_get("https://eu.prices.example/v1/quotes?sku=TEL-001", "eu.prices.example", "price-api")
    http_get("https://us.prices.example/v1/quotes?sku=TEL-001", "us.prices.example", "price-api")
    http_get("https://fx.example/v1/rates?base=EUR", "fx.example", "fx-rates")
    publish({"sku": "TEL-001", "price_eur": 19.90})
