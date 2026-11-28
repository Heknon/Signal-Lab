import logging
import random

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("orders")

random.seed(3)
orders = [(f"o-{1000 + i}", f"user-{random.randint(1, 50)}", round(random.uniform(8, 240), 2)) for i in range(5)]

for order_id, user, total in orders:
    if total > 200:
        log.warning("payment declined", extra={"app.order.id": order_id, "app.order.total": total})
        continue
    log.info("order placed", extra={"app.order.id": order_id, "app.order.total": f"{total:.2f}", "app.user.id": user})
