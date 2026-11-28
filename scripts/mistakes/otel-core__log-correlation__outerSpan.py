import logging
import time

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("refunds")
tracer = trace.get_tracer("refunds")

with tracer.start_as_current_span("refund-run"):
  for order_id, ok in [("o-1", True), ("o-2", False)]:
    log.info("refund requested", extra={"app.order.id": order_id})
    with tracer.start_as_current_span("refund") as span:
        span.set_attribute("app.order.id", order_id)
        time.sleep(0.02)
    if not ok:
        log.error("refund rejected by bank", extra={"app.order.id": order_id})
