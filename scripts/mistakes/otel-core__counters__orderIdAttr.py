from opentelemetry import metrics

meter = metrics.get_meter("orders")
orders = meter.create_counter("orders.placed", unit="{order}", description="Orders placed")

incoming = ["card", "card", "paypal", "card", "voucher", "paypal"]
for method in incoming:
    print("order paid with", method)
    orders.add(1, {"app.payment.method": method, "app.order.id": f"o-{id(method)}-{len(incoming)}-{incoming.index(method)}-{__import__('uuid').uuid4()}"})
