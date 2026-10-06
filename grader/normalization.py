from __future__ import annotations
import json
import math
from datetime import datetime
from typing import Any

FIELD_ALIASES = {
    'order_id': ['order_id', 'id_order'],
    'order_date': ['order_date', 'date_order'],
    'status': ['status', 'order_status'],
    'customer_id': ['customer_id', 'id_customer'],
    'customer_name': ['customer_name', 'name_customer'],
    'customer_phone': ['customer_phone', 'phone', 'phone_customer'],
    'customer_email': ['customer_email', 'email', 'email_customer'],
    'city': ['city'],
    'district': ['district'],
    'delivery_type': ['delivery_type'],
    'delivery_cost': ['delivery_cost'],
    'payment_method': ['payment_method'],
    'payment_status': ['payment_status'],
    'payment_amount': ['payment_amount'],
    'currency': ['currency'],
    'total_amount': ['total_amount'],
    'items': ['items', 'items_json'],
}

META_KEYS = {
    '_id', 'id_run', 'run_id', 'last_id_run', 'source_file', 'file_source',
    'source_row_number', 'number_row_source', 'last_raw_id', 'processed_at',
    'updated_at', 'created_at', 'classification', 'quality_status', 'corrections',
    'error_codes', 'error_details', 'engine_used', 'used_engine', 'raw_record',
    'record_raw', 'processing_outcome', 'processing_error_codes', 'source_run_id',
    'first_validated_at', 'quarantined_at',
}


def _pick(mapping: dict[str, Any], names: list[str]) -> Any:
    for n in names:
        if n in mapping:
            return mapping[n]
    return None


def _normalize_date_value(value: Any) -> Any:
    """Normalize equivalent ISO-like date representations for fair comparison."""
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        raw = value.strip()
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return value
    else:
        return value
    # Preserve timezone information when present; normalize separator/precision.
    return dt.isoformat(timespec="seconds")


def _parse_items(value: Any) -> Any:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            return value
    if isinstance(value, list):
        out = []
        for item in value:
            if not isinstance(item, dict):
                out.append(item)
                continue
            out.append({
                'sku': item.get('sku') or item.get('product_id') or item.get('id_product'),
                'name': item.get('name') or item.get('product_name'),
                'qty': item.get('qty') if item.get('qty') is not None else item.get('quantity'),
                'unit_price': item.get('unit_price') if item.get('unit_price') is not None else item.get('price'),
                'total': item.get('total') if item.get('total') is not None else item.get('line_total'),
            })
        return out
    return value


def clean_payload(doc: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(doc, dict):
        return {}
    nested = None
    for key in ('record_clean', 'cleaned_record', 'clean_record', 'data_clean'):
        if isinstance(doc.get(key), dict):
            nested = doc[key]
            break
    source = nested if nested is not None else doc
    out: dict[str, Any] = {}
    for canon, aliases in FIELD_ALIASES.items():
        value = _pick(source, aliases)
        if value is None and nested is not None:
            value = _pick(doc, aliases)
        if value is not None:
            if canon == 'items':
                out[canon] = _parse_items(value)
            elif canon == 'order_date':
                out[canon] = _normalize_date_value(value)
            else:
                out[canon] = value
    return out


def audit_entries(doc: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(doc, dict):
        return []
    for key in ('corrections', 'audit_trail', 'audit', 'changes'):
        val = doc.get(key)
        if isinstance(val, list):
            return [x for x in val if isinstance(x, dict)]
    nested = doc.get('record_clean')
    if isinstance(nested, dict):
        for key in ('corrections', 'audit_trail'):
            val = nested.get(key)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict)]
    return []


def error_codes(doc: dict[str, Any] | None) -> list[str]:
    if not isinstance(doc, dict):
        return []
    for key in ('error_codes', 'errors', 'quarantine_codes', 'processing_error_codes'):
        val = doc.get(key)
        if isinstance(val, list):
            return [str(x) if not isinstance(x, dict) else str(x.get('code') or x.get('error_code') or x) for x in val]
        if isinstance(val, str):
            return [val]
    return []


def _num_equal(a: Any, b: Any) -> bool:
    try:
        fa, fb = float(a), float(b)
        return math.isclose(fa, fb, rel_tol=1e-9, abs_tol=1e-6)
    except Exception:
        return False


def semantic_equal(actual: Any, expected: Any) -> bool:
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        return _num_equal(actual, expected)
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            return False
        return all(semantic_equal(a, e) for a, e in zip(actual, expected))
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        for k, v in expected.items():
            if k not in actual or not semantic_equal(actual[k], v):
                return False
        return True
    return actual == expected


def compare_clean_record(actual_doc: dict[str, Any] | None, expected_record: dict[str, Any] | None) -> tuple[bool, list[str]]:
    if not expected_record:
        return False, ['لا توجد قيمة متوقعة في الـoracle لهذه الحالة.']
    actual = clean_payload(actual_doc)
    expected = clean_payload(expected_record)
    missing = []
    mismatched = []
    for key, exp in expected.items():
        if key not in actual:
            missing.append(key)
            continue
        if not semantic_equal(actual[key], exp):
            mismatched.append(key)
    notes = []
    if missing:
        notes.append('حقول مفقودة: ' + ', '.join(missing))
    if mismatched:
        notes.append('حقول مختلفة: ' + ', '.join(mismatched))
    return not missing and not mismatched, notes
