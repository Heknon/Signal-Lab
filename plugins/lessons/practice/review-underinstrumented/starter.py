import random
import time

from opentelemetry import metrics, trace

tracer = trace.get_tracer("shipping")
meter = metrics.get_meter("shipping")


class LabelPrinterError(Exception):
    pass


# --- dependencies (simulated; leave these as they are) ---
def validate_address(address: str) -> None:
    time.sleep(rng.uniform(0.003, 0.008))          # address service


def carrier_quote(carrier: str, weight_kg: float) -> float:
    if carrier == "swiftship":
        time.sleep(rng.uniform(0.18, 0.26))         # api.swiftship.example is slow
    else:
        time.sleep(rng.uniform(0.01, 0.02))         # api.parcelpost.example
    return round(4.5 + weight_kg * 1.2, 2)


def print_label(order_id: str) -> None:
    time.sleep(rng.uniform(0.005, 0.01))           # label printer
    if order_id in ("o-1003", "o-1008"):
        raise LabelPrinterError("label printer out of paper")


# --- the handler ---
def ship_order(order: dict) -> dict:
    with tracer.start_as_current_span("ship order") as span:
        span.set_attribute("app.order.id", order["id"])
        try:
            validate_address(order["address"])
            price = carrier_quote(order["carrier"], order["weight_kg"])
            print_label(order["id"])
        except Exception:
            # Retried by a nightly job, so the customer sees "queued".
            return {"status": "queued"}
        return {"status": "shipped", "price": price}


rng = random.Random(11)  # a private generator: telemetry code also uses `random`
for n in range(10):
    order = {"id": f"o-{1000 + n}", "address": "1 Main St", "carrier": rng.choice(["parcelpost", "swiftship"]), "weight_kg": rng.uniform(0.2, 4)}
    print(order["id"], ship_order(order)["status"])
