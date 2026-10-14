import ast
from targeted_p43_named_queries import scoped_probe, NAMES, SHA


def test_p43_fixed_only_previously_malformed_queries_with_required_args():
    assert SHA == "cbbc33924cccddfd77ae0e4cc5784c36db3d22c5"
    assert set(NAMES) == {
        "orders_by_city", "orders_by_status", "customer_orders",
        "orders_by_date_range", "high_value_orders"
    }
    source = scoped_probe()
    ast.parse(source)
    for part in ("city=Sanaa", "status=Delivered", "customer_id=CUST-001",
                 "start_date=2026-01-01", "end_date=2026-12-31",
                 "min_total=200"):
        assert part in source
    assert "POST /ingest" not in source
