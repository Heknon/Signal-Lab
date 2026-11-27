import os

import requests
from opentelemetry import trace

tracer = trace.get_tracer("catalog")
SHOP_URL = os.environ["SHOP_URL"]

# TODO: wrap this in a "browse-catalog" span
products = requests.get(f"{SHOP_URL}/api/products", timeout=5).json()

for p in products:
    print(f"{p['name']:<18} {p['price']:>7.2f}  ({p['in_stock']} in stock)")
