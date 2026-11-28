from opentelemetry import baggage, context, propagate, trace

tracer = trace.get_tracer("tenants")


def apply_discount() -> None:
    with tracer.start_as_current_span("apply-discount") as span:
        # TODO: read the tenant from baggage and record it as app.tenant.id
        pass


def handle_request() -> None:
    with tracer.start_as_current_span("handle-request"):
        apply_discount()
        headers: dict[str, str] = {}
        propagate.inject(headers)
        print("downstream headers:", headers)


for tenant in ["acme", "globex"]:  # two requests, from two tenants
    # TODO: put app.tenant.id=<tenant> into baggage for the duration of the request
    handle_request()
