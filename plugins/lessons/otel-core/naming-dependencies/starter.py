import time

from opentelemetry import trace
from opentelemetry.trace import SpanKind

tracer = trace.get_tracer("prices")


def fake_http_get(url: str) -> int:
    time.sleep(0.03)
    return 200


# TODO: name the service behind each host with peer.service.
#       Both prices hosts are one service, "price-api"; fx.example is "fx-rates".
def http_get(url: str, host: str) -> int:
    with tracer.start_as_current_span("GET", kind=SpanKind.CLIENT) as span:
        span.set_attribute("http.request.method", "GET")
        span.set_attribute("url.full", url)
        span.set_attribute("server.address", host)
        status = fake_http_get(url)
        span.set_attribute("http.response.status_code", status)
        return status


with tracer.start_as_current_span("refresh prices"):
    http_get("https://eu.prices.example/v1/quotes?sku=TEL-001", "eu.prices.example")
    http_get("https://us.prices.example/v1/quotes?sku=TEL-001", "us.prices.example")
    http_get("https://fx.example/v1/rates?base=EUR", "fx.example")
