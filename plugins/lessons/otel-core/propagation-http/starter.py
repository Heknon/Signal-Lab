import json
import os
import urllib.request

from opentelemetry import propagate, trace
from opentelemetry.trace import SpanKind

tracer = trace.get_tracer("prices")
url = os.environ["SHOP_URL"] + "/api/products"

with tracer.start_as_current_span("GET", kind=SpanKind.CLIENT) as span:
    span.set_attribute("http.request.method", "GET")
    span.set_attribute("url.full", url)
    headers = {"accept": "application/json"}
    # TODO: put the current trace context into the headers
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=5) as r:
        span.set_attribute("http.response.status_code", r.status)
        products = json.load(r)

print("sent headers:", headers)
print(len(products), "products")
