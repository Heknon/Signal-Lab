import time

from opentelemetry import trace
from opentelemetry.trace import SpanKind

tracer = trace.get_tracer("prices")


def fake_http_get(url: str) -> int:
    time.sleep(0.04)
    return 200


url = "https://api.prices.example/v1/quotes?sku=TEL-001"

# TODO: use SpanKind.CLIENT and the HTTP semantic conventions
with tracer.start_as_current_span("fetch quote") as span:
    span.set_attribute("method", "GET")
    span.set_attribute("url", url)
    status = fake_http_get(url)
    span.set_attribute("status", status)
