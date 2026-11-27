import logging
import random
import time

from opentelemetry import metrics, trace

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("checkout")
tracer = trace.get_tracer("checkout")
meter = metrics.get_meter("checkout")

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
    total = sum(price * qty for price, qty in order["items"])
    if order["tier"] == "gold":
        total *= 1 - loyalty_discount(order["user"])
    try:
        pay(order["provider"], total)
    except PaymentFailed:
        return False
    return True


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
