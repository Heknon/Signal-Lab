import time

from opentelemetry import trace

tracer = trace.get_tracer("cart")


def checkout(user_id: str, items: list[str]) -> None:
    with tracer.start_as_current_span("checkout") as span:
        span.set_attribute("app.user.id", user_id)
        span.set_attribute("app.cart.items", str(len(items)))
        time.sleep(0.02)  # validating the cart...
        span.add_event("cart.validated", {"app.cart.items": len(items)})
        time.sleep(0.05)  # charging the card...


checkout("u-42", ["mug", "socks", "cap"])
