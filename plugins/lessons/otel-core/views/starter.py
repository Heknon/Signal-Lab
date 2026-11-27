import random

from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.metrics.view import ExplicitBucketHistogramAggregation, View
from opentelemetry.sdk.resources import Resource

reader = PeriodicExportingMetricReader(OTLPMetricExporter(), export_interval_millis=1000)
# TODO: add views that keep only http.route on the counter and set the latency buckets
provider = MeterProvider(metric_readers=[reader], resource=Resource.create({"service.name": "api-gateway"}))
metrics.set_meter_provider(provider)


# ---- pretend this is a third-party library you can't change -------------
meter = metrics.get_meter("some.http.library")
requests_total = meter.create_counter("http.server.requests", unit="{request}")
latency = meter.create_histogram("http.server.latency", unit="s")

random.seed(5)
for _ in range(300):
    attrs = {
        "http.route": random.choice(["/search", "/cart", "/checkout"]),
        "user.id": f"user-{random.randint(1, 300)}",
        "http.user_agent": random.choice(["firefox", "chrome", "curl", "safari"]),
    }
    requests_total.add(1, attrs)
    latency.record(random.lognormvariate(-2.5, 0.7), {"http.route": attrs["http.route"]})
# -------------------------------------------------------------------------

provider.shutdown()
print("served 300 requests")
