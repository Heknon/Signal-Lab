"""Signal Shop: one codebase, five roles (``SHOP_SERVICE``).

Run with ``opentelemetry-instrument uvicorn app:app`` so FastAPI, httpx and
logging are instrumented automatically; business telemetry is added by hand
below, the way you would in a real service.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import time
import uuid
from collections import deque

import httpx
from fastapi import FastAPI, HTTPException
from opentelemetry import metrics, trace
from opentelemetry.trace import Status, StatusCode
from pydantic import BaseModel

SERVICE = os.getenv("SHOP_SERVICE", "storefront")
URLS = {
    "storefront": os.getenv("SHOP_STOREFRONT_URL", "http://storefront:8080"),
    "checkout": os.getenv("SHOP_CHECKOUT_URL", "http://checkout:8080"),
    "inventory": os.getenv("SHOP_INVENTORY_URL", "http://inventory:8080"),
    "payments": os.getenv("SHOP_PAYMENTS_URL", "http://payments:8080"),
}

log = logging.getLogger(f"shop.{SERVICE}")
logging.basicConfig(level=logging.INFO)
tracer = trace.get_tracer("signal-shop", "1.0.0")
meter = metrics.get_meter("signal-shop", "1.0.0")

PRODUCTS = [
    {"sku": "TEL-001", "name": "Trace Telescope", "price": 129.0},
    {"sku": "MTR-002", "name": "Metric Mug", "price": 14.5},
    {"sku": "LOG-003", "name": "Log Notebook", "price": 9.0},
    {"sku": "SPN-004", "name": "Span Socks", "price": 7.25},
    {"sku": "COL-005", "name": "Collector Cap", "price": 22.0},
]
STOCK = {p["sku"]: random.randint(40, 120) for p in PRODUCTS}

app = FastAPI(title=f"signal-shop {SERVICE}")
client = httpx.AsyncClient(timeout=10)

# FastAPI is instrumented explicitly (and disabled in auto-instrumentation via
# OTEL_PYTHON_DISABLED_INSTRUMENTATIONS=fastapi) so we can drop the noisy
# per-message ASGI "http send/receive" spans.
try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(app, exclude_spans=["send", "receive"], excluded_urls="_stats,_chaos,_load")
except ImportError:  # pragma: no cover
    pass


# ------------------------------------------------------------------ chaos & stats
class Chaos(BaseModel):
    latency_ms: int | None = None
    error_rate: float | None = None


chaos = {"latency_ms": 0, "error_rate": 0.0}
stats = {"requests": 0, "errors": 0, "started": time.time()}
latencies: deque[float] = deque(maxlen=500)


async def apply_chaos() -> None:
    if chaos["latency_ms"]:
        jitter = random.uniform(0.7, 1.3)
        with tracer.start_as_current_span("chaos.delay") as span:
            span.set_attribute("chaos.latency_ms", chaos["latency_ms"])
            await asyncio.sleep(chaos["latency_ms"] * jitter / 1000)
    if chaos["error_rate"] and random.random() < chaos["error_rate"]:
        raise HTTPException(503, f"{SERVICE} is having a bad day (injected fault)")


@app.middleware("http")
async def track(request, call_next):
    if request.url.path.startswith("/_"):
        return await call_next(request)
    t0 = time.perf_counter()
    stats["requests"] += 1
    try:
        response = await call_next(request)
    except Exception:
        stats["errors"] += 1
        raise
    if response.status_code >= 500:
        stats["errors"] += 1
    latencies.append((time.perf_counter() - t0) * 1000)
    return response


@app.get("/_stats")
async def get_stats() -> dict:
    lat = sorted(latencies)

    def pct(p: float) -> float | None:
        return round(lat[min(len(lat) - 1, int(p * len(lat)))], 1) if lat else None

    out = {"service": SERVICE, "chaos": chaos, "requests": stats["requests"], "errors": stats["errors"], "p50_ms": pct(0.5), "p95_ms": pct(0.95)}
    if SERVICE == "loadgen":
        out["rps"] = load["rps"]
    return out


@app.post("/_chaos")
async def set_chaos(c: Chaos) -> dict:
    if c.latency_ms is not None:
        chaos["latency_ms"] = max(0, min(c.latency_ms, 10_000))
    if c.error_rate is not None:
        chaos["error_rate"] = max(0.0, min(c.error_rate, 1.0))
    log.warning("chaos updated: %s", chaos)
    return chaos


# ------------------------------------------------------------------ storefront
checkouts = meter.create_counter("shop.checkouts", unit="{checkout}", description="Checkout attempts by outcome")


class CartItem(BaseModel):
    sku: str
    qty: int = 1


class CheckoutRequest(BaseModel):
    user_id: str = "anonymous"
    items: list[CartItem] = []
    tier: str = "standard"


if SERVICE == "storefront":

    @app.get("/api/products")
    async def products() -> list[dict]:
        await apply_chaos()
        r = await client.get(f"{URLS['inventory']}/stock")
        stock = r.json()
        return [p | {"in_stock": stock.get(p["sku"], 0)} for p in PRODUCTS]

    @app.post("/api/checkout")
    async def start_checkout(req: CheckoutRequest) -> dict:
        await apply_chaos()
        span = trace.get_current_span()
        span.set_attribute("app.user.tier", req.tier)
        span.set_attribute("app.cart.items", sum(i.qty for i in req.items))
        try:
            r = await client.post(f"{URLS['checkout']}/checkout", json=req.model_dump())
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            checkouts.add(1, {"outcome": "failed", "app.user.tier": req.tier})
            log.error("checkout failed for user %s: HTTP %s", req.user_id, e.response.status_code)
            raise HTTPException(502, "checkout failed")
        checkouts.add(1, {"outcome": "ok", "app.user.tier": req.tier})
        return r.json()


# ------------------------------------------------------------------ checkout
order_value = meter.create_histogram("shop.order.value", unit="USD", description="Value of placed orders", explicit_bucket_boundaries_advisory=[5, 10, 25, 50, 100, 250, 500])

if SERVICE == "checkout":

    @app.post("/checkout")
    async def checkout(req: CheckoutRequest) -> dict:
        await apply_chaos()
        order_id = uuid.uuid4().hex[:10]
        span = trace.get_current_span()
        span.set_attribute("app.order.id", order_id)
        with tracer.start_as_current_span("price-order") as price_span:
            prices = {p["sku"]: p["price"] for p in PRODUCTS}
            total = round(sum(prices.get(i.sku, 0) * i.qty for i in req.items), 2)
            if req.tier == "gold":
                total = round(total * 0.9, 2)
                price_span.add_event("discount.applied", {"app.discount.pct": 10})
            price_span.set_attribute("app.order.total", total)
            await asyncio.sleep(random.uniform(0.002, 0.01))
        r = await client.post(f"{URLS['inventory']}/reserve", json={"items": [i.model_dump() for i in req.items]})
        if r.status_code != 200:
            span.set_status(Status(StatusCode.ERROR, "reservation failed"))
            log.error("order %s: stock reservation failed", order_id)
            raise HTTPException(502, "reservation failed")
        r = await client.post(f"{URLS['payments']}/charge", json={"order_id": order_id, "amount": total, "user_id": req.user_id})
        if r.status_code != 200:
            log.error("order %s: payment failed", order_id)
            raise HTTPException(502, "payment failed")
        order_value.record(total, {"app.user.tier": req.tier})
        log.info("order %s placed: %d item(s), total %.2f USD", order_id, len(req.items), total)
        return {"order_id": order_id, "total": total}


# ------------------------------------------------------------------ inventory
reserved = meter.create_up_down_counter("inventory.reserved", unit="{item}", description="Items currently reserved")


def _observe_stock(_options):
    for sku, qty in STOCK.items():
        yield metrics.Observation(qty, {"app.product.sku": sku})


if SERVICE == "inventory":
    meter.create_observable_gauge("inventory.stock", callbacks=[_observe_stock], unit="{item}", description="Units in stock")

    async def db(statement: str, op: str) -> None:
        with tracer.start_as_current_span(f"{op} inventory", kind=trace.SpanKind.CLIENT) as span:
            span.set_attribute("db.system.name", "postgresql")
            span.set_attribute("db.namespace", "shop")
            span.set_attribute("db.operation.name", op)
            span.set_attribute("db.query.text", statement)
            span.set_attribute("server.address", "inventory-db")
            await asyncio.sleep(random.uniform(0.003, 0.015))

    @app.get("/stock")
    async def stock() -> dict:
        await apply_chaos()
        await db("SELECT sku, qty FROM stock", "SELECT")
        return STOCK

    @app.post("/reserve")
    async def reserve(body: dict) -> dict:
        await apply_chaos()
        items = body.get("items", [])
        await db("UPDATE stock SET qty = qty - $1 WHERE sku = $2", "UPDATE")
        for i in items:
            sku, qty = i.get("sku"), int(i.get("qty", 1))
            if sku in STOCK:
                STOCK[sku] = STOCK[sku] - qty if STOCK[sku] > qty else random.randint(40, 120)  # restock
            reserved.add(qty)
        return {"reserved": len(items)}


# ------------------------------------------------------------------ payments
class CardDeclined(Exception):
    pass


if SERVICE == "payments":

    @app.post("/charge")
    async def charge(body: dict) -> dict:
        await apply_chaos()
        span = trace.get_current_span()
        span.set_attribute("app.payment.provider", "stripe-sim")
        span.set_attribute("app.payment.amount", body.get("amount", 0))
        with tracer.start_as_current_span("provider.authorize", kind=trace.SpanKind.CLIENT) as s:
            s.set_attribute("server.address", "api.payments.example")
            await asyncio.sleep(random.uniform(0.02, 0.06))
            if random.random() < 0.02:
                err = CardDeclined("card declined by issuer")
                s.record_exception(err)
                s.set_status(Status(StatusCode.ERROR, str(err)))
                log.warning("payment declined for order %s", body.get("order_id"))
                raise HTTPException(402, "card declined")
        return {"status": "captured"}


# ------------------------------------------------------------------ load generator
load = {"rps": float(os.getenv("SHOP_LOADGEN_RPS", "2"))}

if SERVICE == "loadgen":

    @app.post("/_load")
    async def set_load(body: dict) -> dict:
        load["rps"] = max(0.0, min(float(body.get("rps", 0)), 50.0))
        return load

    async def one_session() -> None:
        try:
            await client.get(f"{URLS['storefront']}/api/products")
            items = [{"sku": random.choice(PRODUCTS)["sku"], "qty": random.choice([1, 1, 1, 2, 3])} for _ in range(random.randint(1, 3))]
            await client.post(
                f"{URLS['storefront']}/api/checkout",
                json={"user_id": f"user-{random.randint(1, 400)}", "items": items, "tier": random.choices(["standard", "gold"], [4, 1])[0]},
            )
        except httpx.HTTPError:
            pass

    async def generate() -> None:
        await asyncio.sleep(3)
        while True:
            rps = load["rps"]
            if rps <= 0:
                await asyncio.sleep(0.5)
                continue
            asyncio.create_task(one_session())
            await asyncio.sleep(random.expovariate(rps))

    @app.on_event("startup")
    async def _start() -> None:
        asyncio.create_task(generate())
