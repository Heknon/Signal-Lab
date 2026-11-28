from opentelemetry import baggage, context, propagate, trace

tracer = trace.get_tracer("tenants")


def apply_discount() -> None:
    with tracer.start_as_current_span("apply-discount") as span:
        span.set_attribute("app.tenant.id", "acme")


def handle_request() -> None:
    with tracer.start_as_current_span("handle-request"):
        apply_discount()
        headers: dict[str, str] = {}
        propagate.inject(headers)
        print("downstream headers:", headers)


for tenant in ["acme", "globex"]:  # two requests, from two tenants
    token = context.attach(baggage.set_baggage("app.tenant.id", tenant))
    try:
        handle_request()
    finally:
        context.detach(token)
