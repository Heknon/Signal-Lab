import time

from opentelemetry import trace
from opentelemetry.trace import SpanKind

tracer = trace.get_tracer("prices")


def fake_http_get(url: str) -> int:
    time.sleep(0.04)
    return 200


url = "https://api.prices.example/v1/quotes?sku=TEL-001"

with tracer.start_as_current_span("GET", kind=SpanKind.CLIENT) as span:
    span.set_attribute("http.request.method", "GET")
    span.set_attribute("url.full", url)
    span.set_attribute("server.address", url)
    status = fake_http_get(url)
    span.set_attribute("http.response.status_code", status)
