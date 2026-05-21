import urllib.request
import json
import uuid

API_KEY = "mk_secret_JtK77Q4_oWujlft2RzzSC9iTIeSRD74aV4FlI4aiCzWDnYGk"
HEADERS = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}
BASE_URL = "http://localhost:8000/v1"

def api_call(endpoint, method="GET", data=None):
    req = urllib.request.Request(
        f"{BASE_URL}{endpoint}",
        data=json.dumps(data).encode("utf-8") if data else None,
        headers=HEADERS,
        method=method
    )
    try:
        res = urllib.request.urlopen(req)
        return json.loads(res.read().decode())
    except urllib.error.HTTPError as e:
        print(f"Error {e.code}: {e.read().decode()}")
        raise

# 1. Create Categories
cat_lub = api_call("/categories", "POST", {"name": "Lubricantes"})
cat_fil = api_call("/categories", "POST", {"name": "Filtros"})

# 2. Create Products
prod_oil = api_call("/products", "POST", {
    "sku": "LUB-5W30-01",
    "name": "Aceite Sintético 5W-30 (Litro)",
    "category_id": cat_lub["id"],
    "base_uom": "Litro"
})

prod_filter = api_call("/products", "POST", {
    "sku": "FIL-ACE-01",
    "name": "Filtro de Aceite Universal",
    "category_id": cat_fil["id"],
    "base_uom": "Unidad"
})

# 3. Create Warehouse
wh = api_call("/warehouses", "POST", {
    "name": "Bodega Principal"
})

print("Productos y Bodega creados con éxito.")
