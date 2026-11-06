import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from src.warehouse import load_data, create_warehouse, build_products, build_pair_constraints

_cache = {}


def fixtures():
    """Real project inputs (read-only), built once."""
    if not _cache:
        data, _ = load_data(os.path.join(ROOT, "data"))
        products = build_products(data["forecasts"])
        _cache.update(data=data, products=products, slots=create_warehouse(),
                      pairs=build_pair_constraints(data["pairs"], [p["id"] for p in products]))
    return _cache


def prod(pid, cat="food", heavy=False, cap=10, demand=1.0):
    return {"id": pid, "demand": demand, "last_week_demand": demand, "heavy": heavy, "category": cat, "required_capacity": cap}
