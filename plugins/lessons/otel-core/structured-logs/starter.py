import logging
import random

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("orders")

random.seed(3)
orders = [(f"o-{1000 + i}", f"user-{random.randint(1, 50)}", round(random.uniform(8, 240), 2)) for i in range(5)]

for order_id, user, total in orders:
    if total > 200:
        # TODO: constant message, details as attributes
        log.warning(f"payment declined for order {order_id} ({total} USD)")
        continue
    # TODO: constant message, details as attributes
    log.info(f"order {order_id} placed for {total:.2f} USD by {user}")
