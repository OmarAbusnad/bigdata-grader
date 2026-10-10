from grader.normalization import (
    clean_payload, compare_clean_record, lenient_equal, records_equivalent, audit_entries, error_codes,
)

EXPECTED = {
    "order_id": "طلب-714670", "order_date": "2026-01-05T10:20:00", "status": "مؤكد",
    "customer_id": "عميل-714670", "customer_name": "أحمد محمد", "customer_phone": "771234567",
    "customer_email": "a@example.com", "city": "صنعاء", "district": "التحرير",
    "delivery_type": "سريع", "delivery_cost": 5000.0, "payment_method": "نقدًا عند التسليم",
    "payment_status": "بانتظار الدفع", "payment_amount": 125000.0, "currency": "YER",
    "total_amount": 125000.0,
    "items_json": '[{"sku":"SKU-1002","name":"فأرة لاسلكية","qty":2,"unit_price":60000.0,"total":120000.0}]',
}


def flat_doc(**over):
    d = dict(EXPECTED)
    d.update(over)
    return d


def test_p62_style_record_wrapper_is_read():
    # P62 stores the cleaned record under "record" (previously every field was "missing").
    doc = {"order_id": "طلب-714670", "quality_status": "corrected", "record": dict(EXPECTED),
           "corrections": [{"field": "x"}]}
    ok, notes = compare_clean_record(doc, EXPECTED)
    assert ok, notes
    assert audit_entries(doc)


def test_camel_case_and_grouped_subdocuments_are_read():
    doc = {"orderId": "طلب-714670", "orderDate": "2026-01-05T10:20:00", "status": "مؤكد",
           "customer": {"id": "عميل-714670", "name": "أحمد محمد", "phone": "771234567",
                        "email": "a@example.com"},
           "address": {"city": "صنعاء", "district": "التحرير"},
           "delivery": {"type": "سريع", "cost": 5000},
           "payment": {"method": "نقدًا عند التسليم", "status": "بانتظار الدفع", "amount": 125000},
           "currency": "YER", "totalAmount": 125000,
           "items": [{"sku": "SKU-1002", "name": "فأرة لاسلكية", "qty": 2, "unit_price": 60000, "total": 120000}]}
    ok, notes = compare_clean_record(doc, EXPECTED)
    assert ok, notes


def test_equivalent_formats_are_accepted():
    assert lenient_equal("customer_phone", "+967771234567", "771234567")
    assert lenient_equal("customer_phone", "+967 77 123 4567", "771234567")
    assert lenient_equal("customer_phone", "0771234567", "771234567")
    assert lenient_equal("order_date", "05-01-2026 10:20:00", "2026-01-05T10:20:00")
    assert lenient_equal("order_date", "2026-01-05", "2026-01-05T10:20:00")  # date-level
    assert lenient_equal("order_date", "2026-01-05 10:20:00", "2026-01-05T10:20:00")
    assert lenient_equal("total_amount", "125,000.00", 125000.0)
    assert lenient_equal("total_amount", "١٢٥٠٠٠", 125000.0)
    assert lenient_equal("total_amount", "125000 ريال", 125000.0)
    assert lenient_equal("currency", "ريال", "YER")
    assert lenient_equal("status", "confirmed", "مؤكد")
    assert lenient_equal("status", "  مؤكد  ", "مؤكد")
    assert lenient_equal("payment_method", "نقدا عند التسليم", "نقدًا عند التسليم")
    assert lenient_equal("payment_method", "cash on delivery", "نقدًا عند التسليم")
    assert lenient_equal("city", "Sanaa", "صنعاء")
    assert lenient_equal("customer_email", " A@Example.com ", "a@example.com")


def test_real_content_errors_still_fail():
    assert not lenient_equal("total_amount", 125001.5, 125000.0)
    assert not lenient_equal("status", "ملغي", "مؤكد")
    assert not lenient_equal("order_date", "2026-02-05", "2026-01-05T10:20:00")
    assert not lenient_equal("customer_phone", "771234568", "771234567")
    assert not lenient_equal("currency", "USD", "YER")


def test_one_cosmetic_field_does_not_fail_the_record_but_a_wrong_total_does():
    ok, _ = compare_clean_record(flat_doc(status="delivered_x", city="مدينة"), EXPECTED)
    assert ok  # 2 of 16 fields differ -> 87% >= 80%, no critical field wrong
    ok, notes = compare_clean_record(flat_doc(total_amount=1.0), EXPECTED)
    assert not ok and any("total_amount" in n for n in notes)


def test_many_wrong_fields_fail():
    bad = flat_doc(status="ملغي", city="عدن", customer_phone="700000000", delivery_type="عادي",
                   payment_status="تم الدفع", payment_method="بطاقة")
    ok, _ = compare_clean_record(bad, EXPECTED)
    assert not ok


def test_items_order_insensitive_and_extra_optional_fields_tolerated():
    a = [{"sku": "B", "qty": 1, "unit_price": 10, "total": 10}, {"sku": "A", "qty": 2, "unit_price": 5, "total": 10}]
    e = [{"sku": "A", "qty": 2, "unit_price": 5.0, "total": 10.0}, {"sku": "B", "qty": 1, "unit_price": 10.0, "total": 10.0}]
    assert lenient_equal("items", a, e)
    assert not lenient_equal("items", a[:1], e)


def test_records_equivalent_ignores_formatting_but_sees_changes():
    a = {"record": dict(EXPECTED)}
    b = {"order_id": "طلب-714670", "status": "confirmed", "total_amount": "125,000",
         "customer_phone": "+967771234567"}
    assert records_equivalent(a, a)
    assert not records_equivalent(a, {"record": flat_doc(status="ملغي")})
    assert clean_payload(b)["status"] == "confirmed"


def test_quarantine_codes_found_in_nested_wrapper():
    assert error_codes({"record": {"error_codes": ["MISSING_ORDER_ID"]}}) == ["MISSING_ORDER_ID"]
    assert error_codes({"reasons": ["EMPTY_ITEMS"]}) == ["EMPTY_ITEMS"]


def test_mongo_object_id_is_not_mistaken_for_the_order_id():
    doc = {"_id": object(), "record": dict(EXPECTED)}
    payload = clean_payload(doc)
    assert payload["order_id"] == "طلب-714670"
    ok, notes = compare_clean_record(doc, EXPECTED)
    assert ok, notes
