import logging
import random
import time

from opentelemetry import metrics, trace
from opentelemetry.trace import Status, StatusCode

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("checkout")
tracer = trace.get_tracer("checkout")
meter = metrics.get_meter("checkout")

# Q1 + Q2: one counter, two low-cardinality attributes (2 outcomes x 3 providers = 6 series).
orders = meter.create_counter("orders", unit="{order}", description="Checkout attempts by outcome and payment provider")
# Q3: a histogram, split only by tier (2 series), so percentiles cover every request, unsampled.
duration = meter.create_histogram("checkout.duration", unit="s", description="Time to place an order")

# Operations will ask:
#   1. How many orders per minute, and what share fail?
#   2. Which payment provider fails most?
#   3. Is checkout slower for gold users?
#   4. What happened to order o-2009? (support has the order id, nothing else)


class PaymentFailed(Exception):
    def __init__(self, provider: str, code: str):
        super().__init__(f"{provider} rejected the payment: {code}")
        self.code = code


# --- dependencies (simulated; leave these as they are) ---
FAILURE_RATE = {"stripe-sim": 0.05, "adyen-sim": 0.1, "paypal-sim": 0.45}


def loyalty_discount(user_id: str) -> float:
    time.sleep(rng.uniform(0.06, 0.09))            # loyalty service, gold users only
    return 0.1


def pay(provider: str, amount: float) -> None:
    time.sleep(rng.uniform(0.01, 0.03))            # payment provider API
    if rng.random() < FAILURE_RATE[provider]:
        raise PaymentFailed(provider, rng.choice(["do_not_honor", "timeout", "insufficient_funds"]))


# --- the feature: instrument this ---
def place_order(order: dict) -> bool:
    start = time.perf_counter()
    provider, tier = order["provider"], order["tier"]
    # Q4: the span is the record of one order, so the high-cardinality ids go here.
    with tracer.start_as_current_span("checkout") as span:
        span.set_attribute("app.order.id", order["id"])
        span.set_attribute("app.user.id", order["user"])
        span.set_attribute("app.user.tier", tier)
        span.set_attribute("app.payment.provider", provider)
        total = sum(price * qty for price, qty in order["items"])
        if tier == "gold":
            total *= 1 - loyalty_discount(order["user"])
        try:
            with tracer.start_as_current_span("pay", kind=trace.SpanKind.CLIENT) as pay_span:
                pay_span.set_attribute("server.address", f"api.{provider}.example")
                pay(provider, total)
        except PaymentFailed as e:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            # Q4 when the trace was sampled away: one structured, correlated line per failure.
            log.warning("payment failed", extra={"app.order.id": order["id"], "app.payment.provider": provider, "app.payment.error_code": e.code})
            outcome = "failed"
        else:
            outcome = "ok"
        orders.add(1, {"outcome": outcome, "app.payment.provider": provider})
        duration.record((time.perf_counter() - start) * 1000, {"app.user.tier": tier})
        return outcome == "ok"


rng = random.Random(5)  # a private generator: telemetry code also uses `random`
for n in range(20):
    order = {
        "id": f"o-{2000 + n}",
        "user": f"user-{rng.randint(1, 900)}",
        "tier": rng.choice(["standard", "standard", "gold"]),
        "provider": rng.choice(list(FAILURE_RATE)),
        "items": [(rng.choice([7.25, 9.0, 14.5, 22.0, 129.0]), rng.randint(1, 3)) for _ in range(rng.randint(1, 4))],
    }
    print(order["id"], "placed" if place_order(order) else "failed")
