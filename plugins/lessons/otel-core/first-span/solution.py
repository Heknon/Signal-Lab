from opentelemetry import trace

tracer = trace.get_tracer("hello")


def greet(name: str) -> None:
    with tracer.start_as_current_span("say-hello") as span:
        span.set_attribute("greeting.name", name)
        print(f"hello, {name}")


greet("Ada")
