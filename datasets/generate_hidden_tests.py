"""
مولّد اختبارات المناقشة للمشروع النصفي - الإصدار 2
===================================================

ينشئ 4 ملفات اختبار مخفية:

1) test_01_small_batch_pipeline.csv
   لاختبار:
   - الاختيار التلقائي Python Batch
   - التحميل الكامل إلى orders_raw
   - ELT
   - Cleaning
   - orders_validated / orders_quarantine

2) test_02_large_spark.csv
   لاختبار:
   - الاختيار التلقائي PySpark
   - Parallel processing
   - Partitions / Spark UI
   - Cluster للمجموعات التي اختارت مسار Cluster
   الملف نظيف عمدًا لعزل اختبار Spark عن تعقيد جودة البيانات.

3) test_03_upsert_idempotency.csv
   لاختبار إلزامي للجميع:
   - Stable Business Key
   - Unique Index
   - Upsert
   - Insert / Update / Unchanged
   - Idempotency عند إعادة الملف
   يعتمد على حالة Test 01؛ لذلك أعد Test 01 بعد Reset قبل تشغيل Test 03.

4) test_04_incremental_plan_b.csv
   للخطة B فقط أو التميز الفردي:
   - Incremental / Delta Data
   - Metadata / processed-file state / watermark أو آلية مكافئة
   - Upsert
   - Idempotency عند إعادة نفس ملف Delta

ملفات خاصة بالمحاضر:
- teacher_key.json
- teacher_manifest.csv
- teacher_readme.txt

مهم:
لا تشارك teacher_* مع الطلاب.

التشغيل:
    python generate_midterm_discussion_tests_v2.py

مثال:
    python generate_midterm_discussion_tests_v2.py --out-dir D:\\Razi\\Big_Data\\midterm_hidden_tests --seed 20260818

للاختبار الموحد أثناء المناقشة يُنصح أن يكون حد التحويل بين Batch وSpark
قابلًا للضبط، ويمكن ضبطه إلى 20 MB:
- Test 01 أصغر من الحد.
- Test 02 أكبر من الحد بوضوح.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from collections import defaultdict, deque
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


DEFAULT_SEED = 20260818
DEFAULT_TEST01_N = 20_000
DEFAULT_TEST02_N = 100_000
DEFAULT_TEST03_N = 2_000
DEFAULT_TEST04_N = 1_000

FIELDNAMES = [
    "order_id",
    "order_date",
    "status",
    "customer_id",
    "customer_name",
    "customer_phone",
    "customer_email",
    "city",
    "district",
    "delivery_type",
    "delivery_cost",
    "payment_method",
    "payment_status",
    "payment_amount",
    "currency",
    "total_amount",
    "items_json",
]

CITIES = ["صنعاء", "عدن", "تعز", "إب", "الحديدة", "ذمار", "المكلا"]
DISTRICTS = ["التحرير", "الحصبة", "حدة", "شعوب", "كريتر", "خور مكسر", "القاهرة"]
STATUSES = ["قيد الانتظار", "مؤكد", "قيد الشحن", "تم التسليم", "مرتجع", "ملغي"]
PAYMENT_METHODS = ["نقدًا عند التسليم", "بطاقة", "محفظة إلكترونية"]
DELIVERY_TYPES = ["عادي", "سريع"]
NAMES = [
    "أحمد محمد", "محمد علي", "خالد سالم", "علي حسين",
    "يوسف طارق", "فاطمة أحمد", "أروى محمد", "سارة ياسر",
]
PRODUCTS = [
    ("SKU-1010", "هاتف سامسونج A54", 180_000, 260_000),
    ("SKU-1009", "شاحن سريع", 4_000, 12_000),
    ("SKU-1007", "قرص SSD محمول", 40_000, 180_000),
    ("SKU-1002", "فأرة لاسلكية", 6_000, 12_000),
    ("SKU-1005", "سماعات رأس", 12_000, 45_000),
    ("SKU-1008", "محول HDMI", 5_000, 15_000),
]

CORRECTABLE_CASES = [
    "order_id_missing_prefix",
    "order_id_extra_spaces",
    "arabic_digits_delivery_cost",
    "arabic_digits_payment_amount",
    "arabic_digits_total_amount",
    "price_with_thousands_commas",
    "price_with_currency_suffix",
    "email_double_at",
    "email_double_dot",
    "phone_with_country_code",
    "phone_with_spaces",
    "date_dd_mm_yyyy",
    "currency_arabic_name",
    "status_extra_spaces",
    "qty_as_string_in_items",
    "unit_price_as_string_in_items",
    "total_amount_mismatch_recomputable",
]

QUARANTINE_CASES = [
    "missing_order_id",
    "missing_customer_id",
    "invalid_phone_too_short",
    "email_missing_domain",
    "invalid_date_impossible",
    "unknown_order_status",
    "empty_items",
    "corrupted_items_json",
    "missing_item_sku",
    "negative_quantity",
    "unknown_currency",
    "multiple_conflicting_errors",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="midterm_discussion_tests_v2")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--test01-n", type=int, default=DEFAULT_TEST01_N)
    parser.add_argument("--test02-n", type=int, default=DEFAULT_TEST02_N)
    parser.add_argument("--test03-n", type=int, default=DEFAULT_TEST03_N)
    parser.add_argument("--test04-n", type=int, default=DEFAULT_TEST04_N)
    return parser.parse_args()


def to_arabic_digits(value: Any) -> str:
    return str(value).translate(str.maketrans("0123456789.", "٠١٢٣٤٥٦٧٨٩٫"))


def random_phone(rng: random.Random) -> str:
    return rng.choice(["77", "73", "70", "71"]) + "".join(
        str(rng.randint(0, 9)) for _ in range(7)
    )


def random_email(rng: random.Random, index: int) -> str:
    return f"customer{index}_{rng.randint(100, 999999)}@example.com"


def random_datetime(rng: random.Random, start: datetime) -> str:
    dt = start + timedelta(minutes=rng.randint(0, 180 * 24 * 60))
    return dt.isoformat(timespec="seconds")


def random_price(rng: random.Random, low: int, high: int) -> float:
    return float(rng.randrange(low, high + 1, 500))


def make_items(rng: random.Random) -> list[dict[str, Any]]:
    items = []
    for _ in range(rng.randint(1, 3)):
        sku, name, low, high = rng.choice(PRODUCTS)
        qty = rng.randint(1, 3)
        unit_price = random_price(rng, low, high)
        items.append({
            "sku": sku,
            "name": name,
            "qty": qty,
            "unit_price": unit_price,
            "total": float(qty * unit_price),
        })
    return items


def make_clean_row(
    rng: random.Random,
    seq: int,
    namespace: int,
    start: datetime | None = None,
) -> dict[str, Any]:
    start = start or datetime(2026, 1, 1, 8, 0, 0)
    items = make_items(rng)
    delivery_type = rng.choice(DELIVERY_TYPES)
    delivery_cost = 2_000.0 if delivery_type == "عادي" else 5_000.0
    total_amount = float(sum(i["total"] for i in items) + delivery_cost)
    payment_method = rng.choice(PAYMENT_METHODS)
    payment_status = (
        "بانتظار الدفع"
        if payment_method == "نقدًا عند التسليم"
        else rng.choice(["بانتظار الدفع", "تم الدفع"])
    )
    return {
        "order_id": f"طلب-{namespace + seq}",
        "order_date": random_datetime(rng, start),
        "status": rng.choice(STATUSES),
        "customer_id": f"عميل-{namespace + seq}",
        "customer_name": rng.choice(NAMES),
        "customer_phone": random_phone(rng),
        "customer_email": random_email(rng, namespace + seq),
        "city": rng.choice(CITIES),
        "district": rng.choice(DISTRICTS),
        "delivery_type": delivery_type,
        "delivery_cost": delivery_cost,
        "payment_method": payment_method,
        "payment_status": payment_status,
        "payment_amount": total_amount,
        "currency": "YER",
        "total_amount": total_amount,
        "items_json": json.dumps(items, ensure_ascii=False, separators=(",", ":")),
    }


def parse_items(row: dict[str, Any]) -> list[dict[str, Any]]:
    return json.loads(str(row["items_json"]))


def set_items(row: dict[str, Any], items: list[dict[str, Any]]) -> None:
    row["items_json"] = json.dumps(items, ensure_ascii=False, separators=(",", ":"))


def apply_correctable(row: dict[str, Any], case: str) -> str:
    if case == "order_id_missing_prefix":
        row["order_id"] = str(row["order_id"]).replace("طلب-", "", 1)
        return "إضافة البادئة طلب-."
    if case == "order_id_extra_spaces":
        row["order_id"] = f"  {row['order_id']}  "
        return "إزالة المسافات الخارجية."
    if case == "arabic_digits_delivery_cost":
        row["delivery_cost"] = to_arabic_digits(row["delivery_cost"])
        return "تحويل الأرقام العربية إلى لاتينية ثم Double."
    if case == "arabic_digits_payment_amount":
        row["payment_amount"] = to_arabic_digits(row["payment_amount"])
        return "تحويل الأرقام العربية إلى لاتينية ثم Double."
    if case == "arabic_digits_total_amount":
        row["total_amount"] = to_arabic_digits(row["total_amount"])
        return "تحويل الأرقام العربية إلى لاتينية ثم Double."
    if case == "price_with_thousands_commas":
        row["total_amount"] = f"{float(row['total_amount']):,.2f}"
        return "إزالة فواصل الآلاف ثم التحويل إلى Double."
    if case == "price_with_currency_suffix":
        row["payment_amount"] = f"{float(row['payment_amount']):.2f} YER"
        return "إزالة رمز/اسم العملة ثم التحويل إلى Double."
    if case == "email_double_at":
        row["customer_email"] = str(row["customer_email"]).replace("@", "@@", 1)
        return "ضغط @@ إلى @."
    if case == "email_double_dot":
        local, domain = str(row["customer_email"]).split("@", 1)
        row["customer_email"] = f"{local}@{domain.replace('.', '..', 1)}"
        return "ضغط .. إلى نقطة واحدة."
    if case == "phone_with_country_code":
        row["customer_phone"] = "+967 " + str(row["customer_phone"])
        return "توحيد الهاتف إلى الصيغة المعتمدة."
    if case == "phone_with_spaces":
        phone = str(row["customer_phone"])
        row["customer_phone"] = f"{phone[:2]} {phone[2:5]} {phone[5:]}"
        return "إزالة المسافات."
    if case == "date_dd_mm_yyyy":
        dt = datetime.fromisoformat(str(row["order_date"]))
        row["order_date"] = dt.strftime("%d-%m-%Y %H:%M:%S")
        return "تحويل التاريخ إلى ISO."
    if case == "currency_arabic_name":
        row["currency"] = "ريال يمني"
        return "توحيد العملة إلى YER."
    if case == "status_extra_spaces":
        row["status"] = f"   {row['status']}   "
        return "Trim للحالة."
    if case == "qty_as_string_in_items":
        items = parse_items(row)
        items[0]["qty"] = str(items[0]["qty"])
        set_items(row, items)
        return "تحويل qty من String إلى Integer."
    if case == "unit_price_as_string_in_items":
        items = parse_items(row)
        items[0]["unit_price"] = str(items[0]["unit_price"])
        set_items(row, items)
        return "تحويل unit_price من String إلى Double."
    if case == "total_amount_mismatch_recomputable":
        row["total_amount"] = float(row["total_amount"]) + 1_000.0
        return "إعادة حساب الإجمالي من items + delivery_cost."
    raise ValueError(case)


def apply_quarantine(row: dict[str, Any], case: str) -> str:
    if case == "missing_order_id":
        row["order_id"] = ""
        return "معرف الطلب مفقود."
    if case == "missing_customer_id":
        row["customer_id"] = ""
        return "معرف العميل مفقود."
    if case == "invalid_phone_too_short":
        row["customer_phone"] = "12345"
        return "الهاتف ناقص ولا يمكن استعادته."
    if case == "email_missing_domain":
        row["customer_email"] = "customer_without_domain"
        return "Domain مفقود."
    if case == "invalid_date_impossible":
        row["order_date"] = "2026-19-45 99:70:00"
        return "تاريخ مستحيل."
    if case == "unknown_order_status":
        row["status"] = "حالة غامضة غير معروفة"
        return "الحالة غير قابلة للاستنتاج."
    if case == "empty_items":
        row["items_json"] = "[]"
        return "الطلب بلا عناصر."
    if case == "corrupted_items_json":
        row["items_json"] = '[{"sku":"SKU-1009","qty":2'
        return "JSON تالف."
    if case == "missing_item_sku":
        items = parse_items(row)
        items[0].pop("sku", None)
        set_items(row, items)
        return "SKU مفقود."
    if case == "negative_quantity":
        items = parse_items(row)
        items[0]["qty"] = -abs(int(items[0]["qty"]))
        set_items(row, items)
        return "كمية سالبة ومعناها غير محسوم."
    if case == "unknown_currency":
        row["currency"] = "UNKNOWN"
        return "العملة غير معروفة."
    if case == "multiple_conflicting_errors":
        row["customer_id"] = ""
        row["customer_email"] = "@@"
        row["items_json"] = "not-json"
        row["total_amount"] = "???"
        return "عدة أخطاء جوهرية متعارضة."
    raise ValueError(case)


def distribute(total: int, cases: list[str]) -> list[str]:
    q, r = divmod(total, len(cases))
    result = []
    for i, case in enumerate(cases):
        result.extend([case] * (q + (1 if i < r else 0)))
    return result


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        w.writerows(rows)


def add_manifest(
    manifest: list[dict[str, Any]],
    dataset: str,
    row_no: int | None,
    raw: dict[str, Any],
    canonical: dict[str, Any],
    expected_class: str,
    expected_action: str,
    error_type: str = "",
    note: str = "",
) -> None:
    manifest.append({
        "dataset": dataset,
        "csv_row_number": row_no,
        "input_order_id": raw.get("order_id", ""),
        "expected_order_id": canonical.get("order_id", ""),
        "expected_class": expected_class,
        "expected_action": expected_action,
        "error_type": error_type,
        "teacher_note": note,
        "expected_clean_record_json": (
            ""
            if expected_action == "quarantine"
            else json.dumps(canonical, ensure_ascii=False, separators=(",", ":"))
        ),
    })


def main() -> int:
    args = parse_args()
    if min(args.test01_n, args.test02_n, args.test03_n, args.test04_n) < 100:
        raise ValueError("All test sizes must be >= 100.")

    out = Path(args.out_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    manifest: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Test 01: 60% clean, 25% correctable, 15% quarantine.
    # ------------------------------------------------------------------
    n1_clean = round(args.test01_n * 0.60)
    n1_correctable = round(args.test01_n * 0.25)
    n1_quarantine = args.test01_n - n1_clean - n1_correctable

    labels = (
        [("clean", "")] * n1_clean
        + [("correctable", c) for c in distribute(n1_correctable, CORRECTABLE_CASES)]
        + [("quarantine", c) for c in distribute(n1_quarantine, QUARANTINE_CASES)]
    )
    rng.shuffle(labels)

    test01_rows = []
    baseline_validated: dict[str, dict[str, Any]] = {}

    for i, (quality, case) in enumerate(labels, start=1):
        canonical = make_clean_row(rng, i, 700_000)
        raw = deepcopy(canonical)
        note = ""
        action = "insert_validated"

        if quality == "correctable":
            note = apply_correctable(raw, case)
        elif quality == "quarantine":
            note = apply_quarantine(raw, case)
            action = "quarantine"
        else:
            case = ""

        if action != "quarantine":
            baseline_validated[canonical["order_id"]] = deepcopy(canonical)

        test01_rows.append(raw)
        add_manifest(
            manifest, "TEST_01_BATCH_PIPELINE", i + 1,
            raw, canonical, quality, action, case, note
        )

    test01_path = out / "test_01_small_batch_pipeline.csv"
    write_csv(test01_path, test01_rows)

    # ------------------------------------------------------------------
    # Test 02: clean large file, unique namespace.
    # ------------------------------------------------------------------
    test02_path = out / "test_02_large_spark.csv"
    with test02_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        for i in range(1, args.test02_n + 1):
            w.writerow(make_clean_row(rng, i, 2_000_000))

    # ------------------------------------------------------------------
    # Test 03:
    # 30% new valid, 30% existing update, 25% unchanged, 15% quarantine.
    # New valid is split into clean/correctable.
    # ------------------------------------------------------------------
    n3_new = round(args.test03_n * 0.30)
    n3_update = round(args.test03_n * 0.30)
    n3_unchanged = round(args.test03_n * 0.25)
    n3_quarantine = args.test03_n - n3_new - n3_update - n3_unchanged

    n3_new_correctable = round(n3_new / 3)
    n3_new_clean = n3_new - n3_new_correctable

    ids = list(baseline_validated.keys())
    rng.shuffle(ids)
    need = n3_update + n3_unchanged
    if need > len(ids):
        raise ValueError("Test 01 baseline is too small for Test 03.")
    update_ids = ids[:n3_update]
    unchanged_ids = ids[n3_update:n3_update + n3_unchanged]

    test03_rows = []
    state_after_03 = deepcopy(baseline_validated)

    # New clean.
    for j in range(1, n3_new_clean + 1):
        canonical = make_clean_row(rng, j, 3_000_000)
        test03_rows.append(deepcopy(canonical))
        state_after_03[canonical["order_id"]] = deepcopy(canonical)
        add_manifest(
            manifest, "TEST_03_UPSERT_IDEMPOTENCY", None,
            canonical, canonical, "new_clean", "insert", "", "سجل جديد صالح."
        )

    # New correctable.
    c_cases = distribute(n3_new_correctable, CORRECTABLE_CASES)
    for j, case in enumerate(c_cases, start=1):
        canonical = make_clean_row(rng, 100_000 + j, 3_000_000)
        raw = deepcopy(canonical)
        note = apply_correctable(raw, case)
        test03_rows.append(raw)
        state_after_03[canonical["order_id"]] = deepcopy(canonical)
        add_manifest(
            manifest, "TEST_03_UPSERT_IDEMPOTENCY", None,
            raw, canonical, "new_correctable", "insert", case, note
        )

    # Existing updates.
    for oid in update_ids:
        canonical = deepcopy(state_after_03[oid])
        old_status = canonical["status"]
        canonical["status"] = rng.choice([s for s in STATUSES if s != old_status])
        canonical["payment_status"] = (
            "تم الدفع" if canonical["payment_status"] != "تم الدفع" else "بانتظار الدفع"
        )
        state_after_03[oid] = deepcopy(canonical)
        test03_rows.append(canonical)
        add_manifest(
            manifest, "TEST_03_UPSERT_IDEMPOTENCY", None,
            canonical, canonical, "existing_update", "update", "",
            "Business Key موجود والقيم تغيّرت."
        )

    # Existing unchanged.
    for oid in unchanged_ids:
        canonical = deepcopy(state_after_03[oid])
        test03_rows.append(canonical)
        add_manifest(
            manifest, "TEST_03_UPSERT_IDEMPOTENCY", None,
            canonical, canonical, "existing_unchanged", "unchanged", "",
            "السجل موجود ولم يتغير؛ لا Insert ولا Duplicate."
        )

    # Quarantine.
    q_cases = distribute(n3_quarantine, QUARANTINE_CASES)
    for j, case in enumerate(q_cases, start=1):
        canonical = make_clean_row(rng, 200_000 + j, 3_000_000)
        raw = deepcopy(canonical)
        note = apply_quarantine(raw, case)
        test03_rows.append(raw)
        add_manifest(
            manifest, "TEST_03_UPSERT_IDEMPOTENCY", None,
            raw, canonical, "quarantine", "quarantine", case, note
        )

    rng.shuffle(test03_rows)
    test03_path = out / "test_03_upsert_idempotency.csv"
    write_csv(test03_path, test03_rows)

    # ------------------------------------------------------------------
    # Test 04 for Plan B:
    # 50% new valid, 30% existing update, 10% unchanged, 10% quarantine.
    # It is a Delta file. Expected: process once; rerun must be skipped/no-op.
    # ------------------------------------------------------------------
    n4_new = round(args.test04_n * 0.50)
    n4_update = round(args.test04_n * 0.30)
    n4_unchanged = round(args.test04_n * 0.10)
    n4_quarantine = args.test04_n - n4_new - n4_update - n4_unchanged

    n4_new_correctable = round(n4_new * 0.30)
    n4_new_clean = n4_new - n4_new_correctable

    ids4 = list(state_after_03.keys())
    rng.shuffle(ids4)
    need4 = n4_update + n4_unchanged
    if need4 > len(ids4):
        raise ValueError("State after Test 03 is too small for Test 04.")
    update4 = ids4[:n4_update]
    unchanged4 = ids4[n4_update:n4_update + n4_unchanged]

    test04_rows = []
    state_after_04 = deepcopy(state_after_03)

    for j in range(1, n4_new_clean + 1):
        canonical = make_clean_row(
            rng, j, 4_000_000, start=datetime(2026, 8, 1, 8, 0, 0)
        )
        test04_rows.append(deepcopy(canonical))
        state_after_04[canonical["order_id"]] = deepcopy(canonical)
        add_manifest(
            manifest, "TEST_04_INCREMENTAL_PLAN_B", None,
            canonical, canonical, "delta_new_clean", "insert", "",
            "سجل جديد في ملف Delta."
        )

    c4 = distribute(n4_new_correctable, CORRECTABLE_CASES)
    for j, case in enumerate(c4, start=1):
        canonical = make_clean_row(
            rng, 100_000 + j, 4_000_000, start=datetime(2026, 8, 1, 8, 0, 0)
        )
        raw = deepcopy(canonical)
        note = apply_correctable(raw, case)
        test04_rows.append(raw)
        state_after_04[canonical["order_id"]] = deepcopy(canonical)
        add_manifest(
            manifest, "TEST_04_INCREMENTAL_PLAN_B", None,
            raw, canonical, "delta_new_correctable", "insert", case, note
        )

    for oid in update4:
        canonical = deepcopy(state_after_04[oid])
        canonical["status"] = rng.choice([s for s in STATUSES if s != canonical["status"]])
        canonical["order_date"] = random_datetime(
            rng, datetime(2026, 8, 1, 8, 0, 0)
        )
        state_after_04[oid] = deepcopy(canonical)
        test04_rows.append(canonical)
        add_manifest(
            manifest, "TEST_04_INCREMENTAL_PLAN_B", None,
            canonical, canonical, "delta_existing_update", "update", "",
            "سجل موجود وصل ضمن Delta بقيم أحدث."
        )

    for oid in unchanged4:
        canonical = deepcopy(state_after_04[oid])
        test04_rows.append(canonical)
        add_manifest(
            manifest, "TEST_04_INCREMENTAL_PLAN_B", None,
            canonical, canonical, "delta_existing_unchanged", "unchanged", "",
            "سجل موجود بلا تغيير."
        )

    q4 = distribute(n4_quarantine, QUARANTINE_CASES)
    for j, case in enumerate(q4, start=1):
        canonical = make_clean_row(
            rng, 200_000 + j, 4_000_000, start=datetime(2026, 8, 1, 8, 0, 0)
        )
        raw = deepcopy(canonical)
        note = apply_quarantine(raw, case)
        test04_rows.append(raw)
        add_manifest(
            manifest, "TEST_04_INCREMENTAL_PLAN_B", None,
            raw, canonical, "delta_quarantine", "quarantine", case, note
        )

    rng.shuffle(test04_rows)
    test04_path = out / "test_04_incremental_plan_b.csv"
    write_csv(test04_path, test04_rows)

    # Assign row numbers to shuffled Test03/04 using order_id queues.
    for dataset_name, rows in [
        ("TEST_03_UPSERT_IDEMPOTENCY", test03_rows),
        ("TEST_04_INCREMENTAL_PLAN_B", test04_rows),
    ]:
        qmap: dict[str, deque[int]] = defaultdict(deque)
        for idx, row in enumerate(rows, start=2):
            qmap[str(row.get("order_id", ""))].append(idx)
        for item in manifest:
            if item["dataset"] == dataset_name and item["csv_row_number"] is None:
                oid = str(item["input_order_id"])
                if qmap[oid]:
                    item["csv_row_number"] = qmap[oid].popleft()

    manifest_path = out / "teacher_manifest.csv"
    manifest_fields = [
        "dataset", "csv_row_number", "input_order_id", "expected_order_id",
        "expected_class", "expected_action", "error_type", "teacher_note",
        "expected_clean_record_json",
    ]
    with manifest_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=manifest_fields)
        w.writeheader()
        w.writerows(manifest)

    baseline_count = len(baseline_validated)
    final03 = len(state_after_03)
    final04 = len(state_after_04)

    sizes = {
        test01_path.name: test01_path.stat().st_size,
        test02_path.name: test02_path.stat().st_size,
        test03_path.name: test03_path.stat().st_size,
        test04_path.name: test04_path.stat().st_size,
    }

    key = {
        "seed": args.seed,
        "recommended_discussion_threshold_mb": 20,
        "test_sequence": [
            "Reset -> Test 01 (Batch + Pipeline)",
            "Reset -> Test 02 (Spark / Cluster)",
            "Reset -> Test 01 again to establish baseline -> Test 03 -> rerun Test 03",
            "Plan B only: continue from Test 03 -> Test 04 -> rerun Test 04",
        ],
        "file_sizes_bytes": sizes,
        "test_01": {
            "file": test01_path.name,
            "input": args.test01_n,
            "clean": n1_clean,
            "correctable": n1_correctable,
            "quarantine": n1_quarantine,
            "validated_after_run": baseline_count,
            "expected_engine_at_20mb_threshold": "python_batch",
        },
        "test_02": {
            "file": test02_path.name,
            "input": args.test02_n,
            "clean": args.test02_n,
            "correctable": 0,
            "quarantine": 0,
            "validated_after_run": args.test02_n,
            "expected_engine_at_20mb_threshold": "pyspark",
        },
        "test_03": {
            "file": test03_path.name,
            "input": args.test03_n,
            "new_clean": n3_new_clean,
            "new_correctable": n3_new_correctable,
            "inserted": n3_new,
            "updated": n3_update,
            "unchanged": n3_unchanged,
            "quarantine": n3_quarantine,
            "baseline_validated_before_test": baseline_count,
            "validated_after_first_run": final03,
            "validated_after_rerun": final03,
            "duplicate_business_keys_after_rerun": 0,
        },
        "test_04": {
            "file": test04_path.name,
            "input": args.test04_n,
            "new_clean": n4_new_clean,
            "new_correctable": n4_new_correctable,
            "inserted": n4_new,
            "updated": n4_update,
            "unchanged": n4_unchanged,
            "quarantine": n4_quarantine,
            "baseline_validated_before_test": final03,
            "validated_after_first_run": final04,
            "validated_after_rerun": final04,
            "duplicate_business_keys_after_rerun": 0,
            "incremental_expectation": (
                "The pipeline should record the delta file/run in metadata "
                "and on rerun either skip the already-processed file or produce a no-op."
            ),
        },
    }

    key_path = out / "teacher_key.json"
    key_path.write_text(json.dumps(key, ensure_ascii=False, indent=2), encoding="utf-8")

    readme_path = out / "teacher_readme.txt"
    readme_path.write_text(
        f"""دليل اختبار المناقشة
=====================

الحد الموحد المقترح أثناء المناقشة:
FILE_SIZE_THRESHOLD_MB = 20
ويفضل أن يكون هذا الإعداد Config/Environment Variable في مشروع الطالب.

المرحلة 1 — Batch + Pipeline
----------------------------
1) نظف Collections الاختبار.
2) شغّل {test01_path.name}
3) المتوقع:
   Input       = {args.test01_n:,}
   Validated   = {baseline_count:,}
   Quarantine  = {n1_quarantine:,}
   Engine      = Python Batch عند Threshold=20MB
4) افحص عينة Cleaning يدويًا باستخدام teacher_manifest.csv.

المرحلة 2 — Spark
-----------------
1) نظف Collections الاختبار.
2) شغّل {test02_path.name}
3) المتوقع:
   Input/Validated = {args.test02_n:,}
   Quarantine      = 0
   Engine          = PySpark عند Threshold=20MB
4) اطلب Spark UI / Partitions / زمن التنفيذ.
5) مجموعة Cluster: يجب ألا يكون التنفيذ local[*] فقط، ويجب إظهار Cluster/Workers فعليًا.

المرحلة 3 — Upsert + Idempotency للجميع
----------------------------------------
1) نظف Collections.
2) شغّل Test 01 أولًا لبناء Baseline:
   orders_validated = {baseline_count:,}
3) شغّل {test03_path.name}
   Inserted   = {n3_new:,}
   Updated    = {n3_update:,}
   Unchanged  = {n3_unchanged:,}
   Quarantine = {n3_quarantine:,}
   Final orders_validated = {final03:,}
4) أعد نفس Test 03.
   Final orders_validated يجب أن يبقى = {final03:,}
   Duplicate business keys = 0

المرحلة 4 — Plan B فقط
-----------------------
ابدأ من حالة نهاية Test 03.
شغّل {test04_path.name}
   Inserted   = {n4_new:,}
   Updated    = {n4_update:,}
   Unchanged  = {n4_unchanged:,}
   Quarantine = {n4_quarantine:,}
   Final orders_validated = {final04:,}

أعد نفس Test 04:
- Final orders_validated يبقى {final04:,}
- Duplicate business keys = 0
- يجب أن يثبت المشروع Metadata / processed-file state / watermark أو آلية Incremental مكافئة.
- المقبول: Skip للملف المعالج سابقًا أو No-op كامل مع إثبات عدم إعادة التغييرات.

تنبيه:
orders_raw قد يكون Append-only حسب التصميم، لذلك لا تقِس Idempotency من حجمه وحده.
المقياس الأساسي هو الحالة النهائية في orders_validated وعدم وجود Duplicate Business Keys.
""",
        encoding="utf-8",
    )

    print("=" * 76)
    print("Generated discussion tests")
    print("=" * 76)
    for p in [test01_path, test02_path, test03_path, test04_path]:
        print(f"{p.name:38} {p.stat().st_size / 1024 / 1024:8.2f} MB")
    print("-" * 76)
    print(f"Test01 validated : {baseline_count:,}")
    print(f"Test03 final     : {final03:,}")
    print(f"Test04 final     : {final04:,}")
    print("Teacher files    : teacher_key.json, teacher_manifest.csv, teacher_readme.txt")
    print("=" * 76)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
