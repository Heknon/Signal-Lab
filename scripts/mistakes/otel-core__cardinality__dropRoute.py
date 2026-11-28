import random

from opentelemetry import metrics

meter = metrics.get_meter("gateway")
requests_total = meter.create_counter("api.requests", unit="{request}")

TIERS = ["free", "pro", "enterprise"]
random.seed(1)
users = {f"user-{i}": random.choice(TIERS) for i in range(500)}

for _ in range(2000):
    user, tier = random.choice(list(users.items()))
    route = random.choice(["/api/search", "/api/checkout"])
    requests_total.add(1, {"app.user.tier": tier})

print("sent 2000 requests")
