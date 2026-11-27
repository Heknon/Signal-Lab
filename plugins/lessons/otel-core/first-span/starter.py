from opentelemetry import trace

tracer = trace.get_tracer("hello")


def greet(name: str) -> None:
    # TODO: name this span "say-hello" and add a greeting.name attribute
    with tracer.start_as_current_span("my-span") as span:
        print(f"hello, {name}")


greet("Ada")
