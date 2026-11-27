from opentelemetry import metrics

meter = metrics.get_meter("orders")

# TODO: create an "orders.placed" counter with unit "{order}"

incoming = ["card", "card", "paypal", "card", "voucher", "paypal"]
for method in incoming:
    print("order paid with", method)
    # TODO: count it, tagged with app.payment.method
