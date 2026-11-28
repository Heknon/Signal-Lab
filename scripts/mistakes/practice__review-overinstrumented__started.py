import logging
import random
import time

from opentelemetry import metrics, trace

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("checkout")
tracer = trace.get_tracer("checkout")
meter = metrics.get_meter("checkout")

# One counter answers "how many orders, and how many were declined?".
orders = meter.create_counter("orders", unit="{order}", description="Checkout attempts by outcome")

# A one-off event is a log line, not a time series.
started = meter.create_counter("service.started", unit="{start}")
started.add(1)


class CardDeclined(Exception):
    pass


def charge(card_number: str, amount: float) -> None:
    """The payment provider: declines cards ending in 0002."""
    with tracer.start_as_current_span("charge", kind=trace.SpanKind.CLIENT) as span:
        span.set_attribute("server.address", "api.payments.example")
        time.sleep(rng.uniform(0.01, 0.03))
        if card_number.endswith("0002"):
            raise CardDeclined("card declined by issuer")


def checkout(order: dict) -> bool:
    with tracer.start_as_current_span("checkout") as span:
        span.set_attribute("app.user.id", order["user"])

        # Pricing is in-memory arithmetic: a span per item would cost more than the work.
        total = sum(item["price"] * item["qty"] for item in order["items"])
        span.set_attribute("app.cart.items", sum(item["qty"] for item in order["items"]))

        try:
            charge(order["card"], total)
        except CardDeclined as e:
            # Recorded once, on the span, where it sits next to the rest of the request.
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            orders.add(1, {"outcome": "declined"})
            return False

        orders.add(1, {"outcome": "ok"})
        return True


# --- traffic: 12 orders, every fourth card is declined (leave this as is) ---
rng = random.Random(7)  # a private generator: telemetry code also uses `random`
CATALOG = [("TEL-001", 129.0), ("MTR-002", 14.5), ("LOG-003", 9.0), ("SPN-004", 7.25), ("COL-005", 22.0)]
for n in range(12):
    items = [{"sku": sku, "price": price, "qty": rng.choice([1, 1, 2])} for sku, price in rng.sample(CATALOG, rng.randint(2, 5))]
    card = "4111111111110002" if n % 4 == 3 else "4111111111111111"
    checkout({"user": f"user-{rng.randint(1, 5000)}", "card": card, "items": items})
print("processed 12 orders")
