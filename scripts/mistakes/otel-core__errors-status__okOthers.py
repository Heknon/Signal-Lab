import time

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

tracer = trace.get_tracer("payments")


class CardDeclined(Exception):
    pass


def charge(card: str, amount: float) -> None:
    time.sleep(0.03)
    if card.endswith("0002"):
        raise CardDeclined(f"card ending {card[-4:]} declined")


for card in ["4242-0001", "4242-0002", "4242-0003"]:
    with tracer.start_as_current_span("charge-card") as span:
        span.set_attribute("app.payment.amount", 19.99)
        try:
            charge(card, 19.99)
            print("charged", card)
            span.set_status(Status(StatusCode.OK))
        except CardDeclined as e:
            print("declined:", e)
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
