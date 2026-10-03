from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

SEED = 20261003
FIELDNAMES = [
    "order_id", "order_date", "status", "customer_id", "customer_name",
    "customer_phone", "customer_email", "city", "district", "delivery_type",
    "delivery_cost", "payment_method", "payment_status", "payment_amount",
    "currency", "total_amount", "items_json",
]
CITIES = ["صنعاء", "عدن", "تعز", "إب", "الحديدة", "ذمار", "المكلا"]
DISTRICTS = ["التحرير", "الحصبة", "حدة", "شعوب", "كريتر", "خور مكسر", "القاهرة"]
STATUSES = ["قيد الانتظار", "مؤكد", "قيد الشحن", "تم التسليم", "مرتجع", "ملغي"]
PAYMENT_METHODS = ["نقدًا عند التسليم", "بطاقة", "محفظة إلكترونية"]
DELIVERY_TYPES = ["عادي", "سريع"]
NAMES = ["أحمد محمد", "محمد علي", "خالد سالم", "علي حسين", "يوسف طارق", "فاطمة أحمد", "أروى محمد", "سارة ياسر"]
PRODUCTS = [
    ("SKU-1010", "هاتف سامسونج A54", 180_000, 260_000),
    ("SKU-1009", "شاحن سريع", 4_000, 12_000),
    ("SKU-1007", "قرص SSD محمول", 40_000, 180_000),
    ("SKU-1002", "فأرة لاسلكية", 6_000, 12_000),
    ("SKU-1005", "سماعات رأس", 12_000, 45_000),
    ("SKU-1008", "محول HDMI", 5_000, 15_000),
]
CORRECTION_CASES = [
    "arabic_digits_delivery_cost", "arabic_digits_payment_amount",
    "price_with_thousands_commas", "email_double_at", "phone_with_country_code",
    "date_dd_mm_yyyy", "currency_arabic_name", "status_extra_spaces",
    "qty_as_string_in_items", "total_amount_mismatch_recomputable",
]
QUARANTINE_CASES = [
    "missing_order_id", "missing_customer_id", "invalid_phone_too_short",
    "email_missing_domain", "invalid_date_impossible", "unknown_order_status",
    "empty_items", "corrupted_items_json", "missing_item_sku",
    "negative_quantity", "unknown_currency", "multiple_conflicting_errors",
]


def ar_digits(value):
    return str(value).translate(str.maketrans("0123456789.", "٠١٢٣٤٥٦٧٨٩٫"))


def random_phone(rng: random.Random) -> str:
    return rng.choice(["77", "73", "70", "71"]) + "".join(str(rng.randint(0, 9)) for _ in range(7))


def make_items(rng: random.Random):
    items = []
    for _ in range(rng.randint(1, 3)):
        sku, name, low, high = rng.choice(PRODUCTS)
        qty = rng.randint(1, 3)
        unit = float(rng.randrange(low, high + 1, 500))
        items.append({"sku": sku, "name": name, "qty": qty, "unit_price": unit, "total": float(qty * unit)})
    return items


def make_clean_row(rng: random.Random, seq: int, namespace: int):
    items = make_items(rng)
    delivery_type = rng.choice(DELIVERY_TYPES)
    delivery_cost = 2000.0 if delivery_type == "عادي" else 5000.0
    total = float(sum(item["total"] for item in items) + delivery_cost)
    method = rng.choice(PAYMENT_METHODS)
    payment_status = "بانتظار الدفع" if method == "نقدًا عند التسليم" else rng.choice(["بانتظار الدفع", "تم الدفع"])
    dt = datetime(2026, 1, 1, 8, 0, 0) + timedelta(minutes=rng.randint(0, 180 * 24 * 60))
    n = namespace + seq
    return {
        "order_id": f"طلب-{n}", "order_date": dt.isoformat(timespec="seconds"),
        "status": rng.choice(STATUSES), "customer_id": f"عميل-{n}",
        "customer_name": rng.choice(NAMES), "customer_phone": random_phone(rng),
        "customer_email": f"customer{n}_{rng.randint(1000, 999999)}@example.com",
        "city": rng.choice(CITIES), "district": rng.choice(DISTRICTS),
        "delivery_type": delivery_type, "delivery_cost": delivery_cost,
        "payment_method": method, "payment_status": payment_status,
        "payment_amount": total, "currency": "YER", "total_amount": total,
        "items_json": json.dumps(items, ensure_ascii=False, separators=(",", ":")),
    }


def apply_correction(row: dict, case: str):
    if case == "arabic_digits_delivery_cost": row["delivery_cost"] = ar_digits(row["delivery_cost"])
    elif case == "arabic_digits_payment_amount": row["payment_amount"] = ar_digits(row["payment_amount"])
    elif case == "price_with_thousands_commas": row["total_amount"] = f"{float(row['total_amount']):,.2f}"
    elif case == "email_double_at": row["customer_email"] = str(row["customer_email"]).replace("@", "@@", 1)
    elif case == "phone_with_country_code": row["customer_phone"] = "+967 " + str(row["customer_phone"])
    elif case == "date_dd_mm_yyyy": row["order_date"] = datetime.fromisoformat(str(row["order_date"])).strftime("%d-%m-%Y %H:%M:%S")
    elif case == "currency_arabic_name": row["currency"] = "ريال يمني"
    elif case == "status_extra_spaces": row["status"] = f"   {row['status']}   "
    elif case == "qty_as_string_in_items":
        items = json.loads(row["items_json"]); items[0]["qty"] = str(items[0]["qty"])
        row["items_json"] = json.dumps(items, ensure_ascii=False, separators=(",", ":"))
    elif case == "total_amount_mismatch_recomputable": row["total_amount"] = float(row["total_amount"]) + 1000.0


def apply_quarantine(row: dict, case: str):
    if case == "missing_order_id": row["order_id"] = ""
    elif case == "missing_customer_id": row["customer_id"] = ""
    elif case == "invalid_phone_too_short": row["customer_phone"] = "12345"
    elif case == "email_missing_domain": row["customer_email"] = "customer_without_domain"
    elif case == "invalid_date_impossible": row["order_date"] = "2026-19-45 99:70:00"
    elif case == "unknown_order_status": row["status"] = "حالة غامضة غير معروفة"
    elif case == "empty_items": row["items_json"] = "[]"
    elif case == "corrupted_items_json": row["items_json"] = '[{"sku":"SKU-1009","qty":2'
    elif case == "missing_item_sku":
        items = json.loads(row["items_json"]); items[0].pop("sku", None)
        row["items_json"] = json.dumps(items, ensure_ascii=False, separators=(",", ":"))
    elif case == "negative_quantity":
        items = json.loads(row["items_json"]); items[0]["qty"] = -abs(int(items[0]["qty"]))
        row["items_json"] = json.dumps(items, ensure_ascii=False, separators=(",", ":"))
    elif case == "unknown_currency": row["currency"] = "UNKNOWN"
    elif case == "multiple_conflicting_errors":
        row["customer_id"] = ""; row["customer_email"] = "@@"; row["items_json"] = "not-json"; row["total_amount"] = "???"


def generate(out_dir: Path, seed: int = SEED):
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    total, clean, corrected, quarantine = 20_000, 12_000, 5_000, 3_000
    labels = [("clean", None)] * clean
    labels += [("corrected", case) for case in CORRECTION_CASES for _ in range(corrected // len(CORRECTION_CASES))]
    labels += [("quarantine", case) for case in QUARANTINE_CASES for _ in range(quarantine // len(QUARANTINE_CASES))]
    rng.shuffle(labels)
    csv_path = out_dir / "01_student_test_small.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig", buffering=1024 * 1024) as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES); writer.writeheader()
        for i, (kind, case) in enumerate(labels, start=1):
            row = make_clean_row(rng, i, 8_000_000)
            if kind == "corrected": apply_correction(row, case)
            elif kind == "quarantine": apply_quarantine(row, case)
            writer.writerow(row)

    expected = {
        "seed": seed, "input_rows": total, "clean": clean, "corrected": corrected,
        "orders_validated": clean + corrected, "orders_quarantine": quarantine,
        "correction_case_count_each": corrected // len(CORRECTION_CASES),
        "quarantine_case_count_each": quarantine // len(QUARANTINE_CASES),
    }
    (out_dir / "EXPECTED_RESULTS.json").write_text(json.dumps(expected, ensure_ascii=False, indent=2), encoding="utf-8")
    readme = out_dir / "README_STUDENTS.txt"
    readme.write_text(
        "Big Data practice dataset\n"
        "Input=20,000 | Clean=12,000 | Corrected=5,000 | Validated=17,000 | Quarantine=3,000\n",
        encoding="utf-8",
    )
    sums = out_dir / "SHA256SUMS.txt"
    with sums.open("w", encoding="utf-8") as out:
        for path in (csv_path, out_dir / "EXPECTED_RESULTS.json", readme):
            out.write(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n")
    zip_path = out_dir / "BigData_Student_Practice_Small_Only.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in (csv_path, out_dir / "EXPECTED_RESULTS.json", readme, sums):
            zf.write(path, arcname=path.name)
    print(csv_path)
    print(zip_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="datasets/practice/generated")
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    generate(Path(args.out), args.seed)


if __name__ == "__main__":
    main()
