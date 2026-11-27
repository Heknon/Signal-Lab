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
import sys
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
    """Every fault the lab can inject. Unset fields are left as they are."""

    reset: bool = False
    latency_ms: int | None = None  # every request is slower
    error_rate: float | None = None  # share of requests failing with 503
    slow_sku: str | None = None  # inventory: only reservations of this SKU are slow
    slow_sku_ms: int | None = None
    retries: int | None = None  # checkout: retries for failed payment calls (no backoff)
    pool_size: int | None = None  # inventory: DB connection pool size
    gold_error_rate: float | None = None  # checkout: failures for gold-tier users only
    empty_cart_rate: float | None = None  # storefront: silently drops cart items
    leak_mb_per_min: float | None = None  # memory leak until an OOM-style restart
    label_user_id: bool | None = None  # storefront: adds user ids to a metric (cardinality bomb)
    version: str | None = None  # "deploy": restart with this service.version


DEFAULTS = {
    "latency_ms": 0, "error_rate": 0.0, "slow_sku": None, "slow_sku_ms": 0, "retries": 0, "pool_size": 10,
    "gold_error_rate": 0.0, "empty_cart_rate": 0.0, "leak_mb_per_min": 0.0, "label_user_id": False,
}
BASE_VERSION = os.getenv("SHOP_BASE_VERSION") or next(
    (kv.split("=", 1)[1] for kv in os.getenv("OTEL_RESOURCE_ATTRIBUTES", "").split(",") if kv.startswith("service.version=")), "1.0.0"
)
chaos: dict = dict(DEFAULTS) | {"version": next((kv.split("=", 1)[1] for kv in os.getenv("OTEL_RESOURCE_ATTRIBUTES", "").split(",") if kv.startswith("service.version=")), BASE_VERSION)}


def chaos_active() -> bool:
    return any(chaos[k] != v for k, v in DEFAULTS.items()) or chaos["version"] != BASE_VERSION
stats = {"requests": 0, "errors": 0, "started": time.time()}
latencies: deque[float] = deque(maxlen=500)


async def apply_chaos() -> None:
    if chaos["latency_ms"]:
        jitter = random.uniform(0.7, 1.3)
        with tracer.start_as_current_span("chaos.delay") as span:
            span.set_attribute("chaos.latency_ms", chaos["latency_ms"])
            await asyncio.sleep(chaos["latency_ms"] * jitter / 1000)
    if chaos["error_rate"] and random.random() < chaos["error_rate"]:
        err = RuntimeError(f"{SERVICE} is having a bad day (injected fault)")
        span = trace.get_current_span()
        span.record_exception(err)
        span.set_status(Status(StatusCode.ERROR, str(err)))
        log.error("injected fault", extra={"app.chaos.error_rate": chaos["error_rate"]})
        raise HTTPException(503, str(err))


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

    out = {"service": SERVICE, "chaos": chaos | {"active": chaos_active()}, "requests": stats["requests"], "errors": stats["errors"], "p50_ms": pct(0.5), "p95_ms": pct(0.95), "memory_mb": round(_rss_bytes() / 1e6, 1)}
    if SERVICE == "loadgen":
        out["rps"] = load["rps"]
    return out


@app.post("/_chaos")
async def set_chaos(c: Chaos) -> dict:
    target_version = c.version
    if c.reset:
        chaos.update(DEFAULTS)
        leaked.clear()
        target_version = BASE_VERSION
    for key, value in c.model_dump(exclude_none=True, exclude={"reset", "version"}).items():
        if key in ("latency_ms", "slow_sku_ms"):
            value = max(0, min(int(value), 10_000))
        elif key in ("error_rate", "gold_error_rate", "empty_cart_rate"):
            value = max(0.0, min(float(value), 1.0))
        elif key == "retries":
            value = max(0, min(int(value), 5))
        elif key == "pool_size":
            value = max(1, min(int(value), 100))
        elif key == "leak_mb_per_min":
            value = max(0.0, min(float(value), 500.0))
        chaos[key] = value
    log.warning("chaos updated", extra={"app.chaos.active": chaos_active()})
    if target_version and target_version != chaos["version"]:
        chaos["version"] = target_version
        asyncio.get_running_loop().call_later(0.3, _restart, {"version": target_version})
    return chaos | {"active": chaos_active()}


def _restart(state: dict) -> None:
    """Re-exec this service, as a deploy or an OOM-kill would: new process, new
    service.instance.id, counters back at zero. Faults survive via SHOP_STATE."""
    import json

    attrs = [kv for kv in os.getenv("OTEL_RESOURCE_ATTRIBUTES", "").split(",") if kv and not kv.startswith("service.version=")]
    attrs.append(f"service.version={state.get('version', chaos['version'])}")
    os.environ["OTEL_RESOURCE_ATTRIBUTES"] = ",".join(attrs)
    os.environ["SHOP_BASE_VERSION"] = BASE_VERSION
    os.environ["SHOP_STATE"] = json.dumps({k: chaos[k] for k in DEFAULTS})
    log.warning("restarting", extra={"service.version": state.get("version")})
    logging.shutdown()
    os.execv(sys.executable, [sys.executable, "-m", "uvicorn", *sys.argv[1:]])


def _load_state() -> None:
    import json

    raw = os.environ.pop("SHOP_STATE", "")
    if raw:
        try:
            chaos.update({k: v for k, v in json.loads(raw).items() if k in DEFAULTS})
        except ValueError:
            pass


_load_state()


# ------------------------------------------------------------------ process metrics & memory leak
def _rss_bytes() -> int:
    try:
        with open("/proc/self/statm") as f:
            return int(f.read().split()[1]) * os.sysconf("SC_PAGE_SIZE")
    except (OSError, ValueError):
        import resource

        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024


def _observe_memory(_options):
    yield metrics.Observation(_rss_bytes(), {})


meter.create_observable_up_down_counter("process.memory.usage", callbacks=[_observe_memory], unit="By", description="Resident memory of this process")
leaked: list[bytearray] = []
OOM_LIMIT_MB = 300


async def _leak() -> None:
    while True:
        await asyncio.sleep(1)
        rate = chaos["leak_mb_per_min"]
        if not rate:
            continue
        leaked.append(bytearray(int(rate * 1024 * 1024 / 60)))
        if _rss_bytes() > OOM_LIMIT_MB * 1024 * 1024:
            log.error("out of memory: process killed", extra={"process.memory.limit_mb": OOM_LIMIT_MB})
            _restart({})


@app.on_event("startup")
async def _start_leak() -> None:
    asyncio.create_task(_leak())


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
        if chaos["empty_cart_rate"] and random.random() < chaos["empty_cart_rate"]:
            req.items = []  # the bug: a bad merge drops the cart, and nothing complains
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
        attrs = {"outcome": "ok", "app.user.tier": req.tier}
        if chaos["label_user_id"]:
            attrs["app.user.id"] = req.user_id  # the cardinality bomb
        checkouts.add(1, attrs)
        return r.json()


# ------------------------------------------------------------------ checkout
order_value = meter.create_histogram("shop.order.value", unit="USD", description="Value of placed orders", explicit_bucket_boundaries_advisory=[5, 10, 25, 50, 100, 250, 500])

if SERVICE == "checkout":

    @app.post("/checkout")
    async def checkout(req: CheckoutRequest) -> dict:
        await apply_chaos()
        if not req.items:
            return {"order_id": None, "total": 0}  # nothing to buy: succeed quietly
        order_id = uuid.uuid4().hex[:10]
        span = trace.get_current_span()
        span.set_attribute("app.order.id", order_id)
        span.set_attribute("app.user.tier", req.tier)
        if req.tier == "gold" and chaos["gold_error_rate"] and random.random() < chaos["gold_error_rate"]:
            err = KeyError("discount rule 'gold-2024' not found")
            span.record_exception(err)
            span.set_status(Status(StatusCode.ERROR, "pricing failed"))
            log.error("pricing failed", extra={"app.user.tier": req.tier, "app.order.id": order_id})
            raise HTTPException(500, "pricing failed")
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
        for attempt in range(1 + chaos["retries"]):
            r = await client.post(f"{URLS['payments']}/charge", json={"order_id": order_id, "amount": total, "user_id": req.user_id})
            if r.status_code == 200 or r.status_code == 402:
                break
            span.add_event("payment.retry", {"app.retry.attempt": attempt + 1})
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

    pool_state = {"used": 0, "pending": 0}

    def _observe_pool(_options):
        size = chaos["pool_size"]
        attrs = {"db.client.connection.pool.name": "inventory-db"}
        yield metrics.Observation(pool_state["used"], attrs | {"db.client.connection.state": "used"})
        yield metrics.Observation(max(0, size - pool_state["used"]), attrs | {"db.client.connection.state": "idle"})

    meter.create_observable_up_down_counter("db.client.connection.count", callbacks=[_observe_pool], unit="{connection}", description="Connections in the pool by state")
    meter.create_observable_up_down_counter(
        "db.client.connection.pending_requests", unit="{request}", description="Requests waiting for a connection",
        callbacks=[lambda _o: [metrics.Observation(pool_state["pending"], {"db.client.connection.pool.name": "inventory-db"})]],
    )
    wait_time = meter.create_histogram("db.client.connection.wait_time", unit="s", description="Time spent waiting for a connection",
                                       explicit_bucket_boundaries_advisory=[0.001, 0.005, 0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5])

    async def db(statement: str, op: str, extra_ms: float = 0) -> None:
        # A connection pool: when every connection is busy, requests queue.
        t0 = time.perf_counter()
        pool_state["pending"] += 1
        while pool_state["used"] >= chaos["pool_size"]:
            await asyncio.sleep(0.005)
        pool_state["pending"] -= 1
        pool_state["used"] += 1
        wait_time.record(time.perf_counter() - t0, {"db.client.connection.pool.name": "inventory-db"})
        try:
            await _query(statement, op, extra_ms)
        finally:
            pool_state["used"] -= 1

    async def _query(statement: str, op: str, extra_ms: float) -> None:
        with tracer.start_as_current_span(f"{op} inventory", kind=trace.SpanKind.CLIENT) as span:
            span.set_attribute("db.system.name", "postgresql")
            span.set_attribute("db.namespace", "shop")
            span.set_attribute("db.operation.name", op)
            span.set_attribute("db.query.text", statement)
            span.set_attribute("server.address", "inventory-db")
            await asyncio.sleep(random.uniform(0.025, 0.055) + extra_ms / 1000)

    @app.get("/stock")
    async def stock() -> dict:
        await apply_chaos()
        await db("SELECT sku, qty FROM stock", "SELECT")
        return STOCK

    @app.post("/reserve")
    async def reserve(body: dict) -> dict:
        await apply_chaos()
        items = body.get("items", [])
        slow = chaos["slow_sku"] and any(i.get("sku") == chaos["slow_sku"] for i in items)
        await db("UPDATE stock SET qty = qty - $1 WHERE sku = $2", "UPDATE", extra_ms=chaos["slow_sku_ms"] if slow else 0)
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

    inflight = {"n": 0}

    async def charge(body: dict) -> dict:
        inflight["n"] += 1
        try:
            return await _charge(body)
        finally:
            inflight["n"] -= 1

    app.post("/charge")(charge)

    async def _charge(body: dict) -> dict:
        # Limited capacity: each concurrent request beyond 4 adds latency.
        if inflight["n"] > 4:
            await asyncio.sleep((inflight["n"] - 4) * 0.03)
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
