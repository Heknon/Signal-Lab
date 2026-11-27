import time

from opentelemetry import trace

tracer = trace.get_tracer("cart")


def checkout(user_id: str, items: list[str]) -> None:
    with tracer.start_as_current_span("checkout") as span:
        # TODO: record who is checking out and how many items they have
        time.sleep(0.02)  # validating the cart...
        # TODO: record a "cart.validated" event here
        time.sleep(0.05)  # charging the card...


checkout("u-42", ["mug", "socks", "cap"])
