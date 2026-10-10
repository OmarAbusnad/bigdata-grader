from __future__ import annotations
import json
import math
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any

FIELD_ALIASES = {
    'order_id': ['order_id', 'id_order', 'orderid', 'order_no', 'order_number'],
    'order_date': ['order_date', 'date_order', 'orderdate', 'created_date', 'date'],
    'status': ['status', 'order_status', 'orderstatus', 'state'],
    'customer_id': ['customer_id', 'id_customer', 'customerid', 'customer.id', 'customer_code'],
    'customer_name': ['customer_name', 'name_customer', 'customername', 'customer.name', 'client_name'],
    'customer_phone': ['customer_phone', 'phone', 'phone_customer', 'customerphone', 'customer.phone',
                       'phone_number', 'mobile', 'customer_mobile'],
    'customer_email': ['customer_email', 'email', 'email_customer', 'customeremail', 'customer.email'],
    'city': ['city', 'address.city', 'location.city', 'customer.city'],
    'district': ['district', 'address.district', 'location.district', 'customer.district', 'area'],
    'delivery_type': ['delivery_type', 'deliverytype', 'delivery.type', 'shipping_type', 'delivery_method'],
    'delivery_cost': ['delivery_cost', 'deliverycost', 'delivery.cost', 'shipping_cost', 'delivery_fee'],
    'payment_method': ['payment_method', 'paymentmethod', 'payment.method', 'pay_method'],
    'payment_status': ['payment_status', 'paymentstatus', 'payment.status', 'pay_status'],
    'payment_amount': ['payment_amount', 'paymentamount', 'payment.amount', 'amount_paid', 'paid_amount'],
    'currency': ['currency', 'currency_code', 'payment.currency'],
    'total_amount': ['total_amount', 'totalamount', 'total', 'order_total', 'grand_total', 'totals.total'],
    'items': ['items', 'items_json', 'order_items', 'line_items', 'products'],
}

# Wrapper keys under which students commonly nest the cleaned business record.
NESTED_WRAPPERS = (
    'record_clean', 'cleaned_record', 'clean_record', 'data_clean', 'record', 'cleaned', 'clean',
    'data', 'payload', 'document', 'doc', 'fields', 'order', 'validated', 'validated_record',
    'normalized', 'normalized_record', 'clean_data', 'cleaned_data', 'business_record',
)
# Critical business fields: a record cannot pass if these are present in the oracle and wrong.
CRITICAL_FIELDS = ('total_amount', 'items')
# Share of the remaining oracle fields that must match for a record to count as correct.
MIN_FIELD_MATCH_RATIO = 0.80

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


def _nk(key: Any) -> str:
    """Case/underscore/dash insensitive key: customerId == customer_id == Customer-ID."""
    return re.sub(r'[\s_\-]+', '', str(key)).lower()


def _flat(source: dict[str, Any]) -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for k, v in source.items():
        if str(k).startswith('_'):  # Mongo's _id and other private keys are never business fields
            continue
        flat.setdefault(_nk(k), v)
        if isinstance(v, dict):
            for k2, v2 in v.items():
                if str(k2).startswith('_'):
                    continue
                flat.setdefault(f'{_nk(k)}.{_nk(k2)}', v2)
    return flat


def _alias_hits(flat: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for canon, aliases in FIELD_ALIASES.items():
        for a in aliases:
            na = _nk(a) if '.' not in a else '.'.join(_nk(x) for x in a.split('.'))
            if na in flat and flat[na] is not None:
                out[canon] = flat[na]
                break
    return out


def _candidate_dicts(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """The document itself plus any dict nested up to two levels (any key, wrappers first)."""
    cands = [doc]
    seen = {id(doc)}
    level = [doc]
    for _ in range(2):
        nxt = []
        for d in level:
            keys = sorted(d.keys(), key=lambda k: (_nk(k) not in {_nk(w) for w in NESTED_WRAPPERS}, str(k)))
            for k in keys:
                v = d[k]
                if isinstance(v, dict) and id(v) not in seen and not str(k).startswith('$'):
                    seen.add(id(v))
                    cands.append(v)
                    nxt.append(v)
        level = nxt
    return cands


def clean_payload(doc: dict[str, Any] | None) -> dict[str, Any]:
    """Extract the cleaned business record from ANY reasonable student document shape.

    Supports flat documents, wrapper keys (record/data/payload/...), camelCase or
    snake_case field names and grouped sub-documents (customer.{id,name,...}).
    The candidate exposing the most business fields wins; missing fields are filled from
    the remaining candidates so a record split across levels is still read completely.
    """
    if not isinstance(doc, dict):
        return {}
    scored = []
    for idx, cand in enumerate(_candidate_dicts(doc)):
        hits = _alias_hits(_flat(cand))
        scored.append((len(hits), -idx, hits))
    if not scored:
        return {}
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    merged: dict[str, Any] = {}
    for _, _, hits in scored:
        for k, v in hits.items():
            merged.setdefault(k, v)
    out: dict[str, Any] = {}
    for canon, value in merged.items():
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
    for cand in _candidate_dicts(doc):
        for key in ('corrections', 'audit_trail', 'audit', 'changes', 'correction_log', 'fixes'):
            val = cand.get(key)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict)]
    return []


def error_codes(doc: dict[str, Any] | None) -> list[str]:
    if not isinstance(doc, dict):
        return []
    for cand in _candidate_dicts(doc):
        for key in ('error_codes', 'errors', 'quarantine_codes', 'processing_error_codes', 'error_code',
                    'reasons', 'reason_codes', 'quarantine_reason'):
            val = cand.get(key)
            if isinstance(val, list) and val:
                return [str(x) if not isinstance(x, dict) else str(x.get('code') or x.get('error_code') or x) for x in val]
            if isinstance(val, str) and val.strip():
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


# ---------------------------------------------------------------------------
# Lenient (format-tolerant) comparison.
#
# The assignment says "unify the format" / "standard dictionary" without fixing the exact
# canonical spelling, so a student's equivalent representation must not be failed for a
# formatting choice. Values are compared AFTER normalisation; real content errors
# (a wrong amount, a different status meaning, a wrong date) still fail.
# ---------------------------------------------------------------------------
_AR_DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩٫٬', '0123456789.,')
_TASHKEEL = re.compile('[\u064B-\u065F\u0670\u0640]')


def _norm_text(value: Any) -> str:
    s = unicodedata.normalize('NFKC', str(value)).translate(_AR_DIGITS)
    s = _TASHKEEL.sub('', s)
    for a, b in (('أ', 'ا'), ('إ', 'ا'), ('آ', 'ا'), ('ٱ', 'ا'), ('ى', 'ي'), ('ة', 'ه'), ('ؤ', 'و'), ('ئ', 'ي')):
        s = s.replace(a, b)
    s = re.sub(r'[\s\u200b\u200c\u200d]+', ' ', s).strip().casefold()
    return s


_VOCAB: dict[str, dict[str, list[str]]] = {
    'status': {
        'pending': ['قيد الانتظار', 'قيد الإنتظار', 'انتظار', 'pending', 'waiting', 'new', 'جديد'],
        'confirmed': ['مؤكد', 'مؤكدة', 'confirmed', 'approved', 'تم التأكيد'],
        'shipping': ['قيد الشحن', 'شحن', 'قيد التوصيل', 'shipping', 'shipped', 'in transit', 'processing', 'out for delivery'],
        'delivered': ['تم التسليم', 'تم التوصيل', 'مسلم', 'delivered', 'completed', 'complete'],
        'returned': ['مرتجع', 'مرجع', 'returned', 'refunded'],
        'cancelled': ['ملغي', 'ملغى', 'ملغاة', 'cancelled', 'canceled', 'cancel'],
    },
    'payment_status': {
        'unpaid': ['بانتظار الدفع', 'قيد الدفع', 'غير مدفوع', 'لم يتم الدفع', 'pending', 'unpaid', 'awaiting payment', 'not paid'],
        'paid': ['تم الدفع', 'مدفوع', 'paid', 'completed'],
    },
    'payment_method': {
        'cod': ['نقدا عند التسليم', 'نقد', 'نقدي', 'الدفع عند الاستلام', 'cash', 'cod', 'cash on delivery'],
        'card': ['بطاقه', 'بطاقة', 'بطاقه ائتمانيه', 'card', 'credit card', 'debit card', 'visa'],
        'wallet': ['محفظه الكترونيه', 'محفظة إلكترونية', 'محفظه', 'wallet', 'e-wallet', 'ewallet', 'mobile wallet'],
    },
    'delivery_type': {
        'standard': ['عادي', 'عاديه', 'standard', 'normal', 'regular'],
        'express': ['سريع', 'سريعه', 'express', 'fast', 'urgent'],
    },
    'currency': {
        'YER': ['yer', 'ريال', 'ريال يمني', 'ر.ي', 'ر ي', '﷼', 'yr', 'yemeni rial', 'yemeni riyal', 'rial', 'riyal'],
    },
    'city': {
        'sanaa': ['صنعاء', 'sanaa', "sana'a", 'sana a', 'sanaa city'],
        'aden': ['عدن', 'aden'],
        'taiz': ['تعز', 'taiz', 'taizz'],
        'ibb': ['اب', 'إب', 'ibb'],
        'hodeidah': ['الحديده', 'الحديدة', 'hodeidah', 'hudaydah', 'hodeida', 'al hudaydah'],
        'dhamar': ['ذمار', 'dhamar'],
        'mukalla': ['المكلا', 'mukalla', 'al mukalla'],
    },
}
_VOCAB_REV: dict[str, dict[str, str]] = {
    field: {_norm_text(syn): code for code, syns in groups.items() for syn in syns}
    for field, groups in _VOCAB.items()
}


def _canon_text(field: str, value: Any) -> str:
    n = _norm_text(value)
    return _VOCAB_REV.get(field, {}).get(n, n)


def _to_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).translate(_AR_DIGITS)
    m = re.search(r'-?\d[\d,]*(?:\.\d+)?|-?\.\d+', s)
    if not m:
        return None
    token = m.group(0)
    if re.fullmatch(r'-?\d{1,3}(?:,\d{3})+(?:\.\d+)?', token) or ',' in token:
        token = token.replace(',', '')
    try:
        return float(token)
    except ValueError:
        return None


def _money_equal(a: Any, e: Any) -> bool:
    fa, fe = _to_number(a), _to_number(e)
    if fa is None or fe is None:
        return False
    return math.isclose(fa, fe, rel_tol=1e-6, abs_tol=0.011)


_DATE_FORMATS = (
    '%d-%m-%Y %H:%M:%S', '%d/%m/%Y %H:%M:%S', '%d-%m-%Y %H:%M', '%d/%m/%Y %H:%M',
    '%Y/%m/%d %H:%M:%S', '%Y-%m-%d %H:%M:%S', '%d-%m-%Y', '%d/%m/%Y', '%Y/%m/%d', '%Y-%m-%d', '%d.%m.%Y',
)


def _to_dt(value: Any) -> tuple[datetime, bool] | None:
    """Return (naive datetime, has_time_component)."""
    if isinstance(value, datetime):
        dt = value
        has_time = (dt.hour, dt.minute, dt.second) != (0, 0, 0)
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        v = float(value)
        if v > 1e11:
            v /= 1000.0
        try:
            dt = datetime.fromtimestamp(v, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
        has_time = True
    elif isinstance(value, str):
        raw = unicodedata.normalize('NFKC', value).translate(_AR_DIGITS).strip()
        if not raw:
            return None
        dt = None
        try:
            dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
            has_time = bool(re.search(r'[T\s]\d{1,2}:\d{2}', raw))
        except ValueError:
            for fmt in _DATE_FORMATS:
                try:
                    dt = datetime.strptime(raw, fmt)
                    has_time = ':' in fmt
                    break
                except ValueError:
                    continue
        if dt is None:
            return None
    else:
        return None
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    return dt, has_time


def _date_equal(a: Any, e: Any) -> bool:
    pa, pe = _to_dt(a), _to_dt(e)
    if pa is None or pe is None:
        return _norm_text(a) == _norm_text(e)
    (da, ta), (de, te) = pa, pe
    if da.date() != de.date():
        return False
    if ta and te:
        return abs((da - de).total_seconds()) <= 1.5
    return True  # one side carries no time: date-level equality is enough


def _phone_core(value: Any) -> str:
    digits = re.sub(r'\D', '', str(value).translate(_AR_DIGITS))
    if digits.startswith('00'):
        digits = digits[2:]
    if digits.startswith('967') and len(digits) > 9:
        digits = digits[3:]
    return digits.lstrip('0') if len(digits) > 9 else digits.lstrip('0') or digits


def _phone_equal(a: Any, e: Any) -> bool:
    pa, pe = _phone_core(a), _phone_core(e)
    return bool(pa) and bool(pe) and (pa == pe or pa[-9:] == pe[-9:])


def _id_equal(a: Any, e: Any) -> bool:
    na, ne = _norm_text(a), _norm_text(e)
    if na == ne:
        return True
    da, de = re.sub(r'\D', '', na), re.sub(r'\D', '', ne)
    return bool(da) and da == de


def _item_list(value: Any) -> list[dict[str, Any]] | None:
    value = _parse_items(value)
    return value if isinstance(value, list) and all(isinstance(x, dict) for x in value) else None


def _items_equal(a: Any, e: Any) -> bool:
    la, le = _item_list(a), _item_list(e)
    if la is None or le is None or len(la) != len(le):
        return False
    pool = list(la)
    for exp in le:  # order-insensitive matching
        hit = None
        for cand in pool:
            qty_ok = exp.get('qty') is None or _money_equal(cand.get('qty'), exp.get('qty'))
            price_ok = exp.get('unit_price') is None or _money_equal(cand.get('unit_price'), exp.get('unit_price'))
            total_ok = exp.get('total') is None or cand.get('total') is None or _money_equal(cand.get('total'), exp.get('total'))
            sku_ok = not (exp.get('sku') and cand.get('sku')) or _norm_text(cand['sku']) == _norm_text(exp['sku'])
            if qty_ok and price_ok and total_ok and sku_ok:
                hit = cand
                break
        if hit is None:
            return False
        pool.remove(hit)
    return True


_MONEY_FIELDS = {'delivery_cost', 'payment_amount', 'total_amount'}
_VOCAB_FIELDS = {'status', 'payment_status', 'payment_method', 'delivery_type', 'currency', 'city'}


def lenient_equal(field: str, actual: Any, expected: Any) -> bool:
    if expected is None:
        return True
    if actual is None:
        return False
    try:
        if field == 'items':
            return _items_equal(actual, expected)
        if field in _MONEY_FIELDS:
            return _money_equal(actual, expected)
        if field == 'order_date':
            return _date_equal(actual, expected)
        if field == 'customer_phone':
            return _phone_equal(actual, expected)
        if field == 'customer_email':
            return _norm_text(actual) == _norm_text(expected)
        if field in {'order_id', 'customer_id'}:
            return _id_equal(actual, expected)
        if field in _VOCAB_FIELDS:
            return _canon_text(field, actual) == _canon_text(field, expected)
        if isinstance(expected, (int, float)) and not isinstance(expected, bool):
            return _money_equal(actual, expected)
        return _norm_text(actual) == _norm_text(expected)
    except Exception:
        return semantic_equal(actual, expected)


def compare_clean_record(actual_doc: dict[str, Any] | None, expected_record: dict[str, Any] | None,
                         min_ratio: float = MIN_FIELD_MATCH_RATIO) -> tuple[bool, list[str]]:
    """Tolerant record check: critical fields must match; the rest must match >= min_ratio."""
    if not expected_record:
        return False, ['لا توجد قيمة متوقعة في الـoracle لهذه الحالة.']
    actual = clean_payload(actual_doc)
    expected = clean_payload(expected_record)
    if not actual:
        return False, ['لم يتم العثور على سجل أعمال قابل للقراءة داخل الوثيقة.']
    missing: list[str] = []
    mismatched: list[str] = []
    matched = 0
    considered = 0
    critical_bad = False
    for key, exp in expected.items():
        considered += 1
        if key not in actual:
            missing.append(key)
            critical_bad = critical_bad or key in CRITICAL_FIELDS
            continue
        if lenient_equal(key, actual[key], exp):
            matched += 1
        else:
            mismatched.append(key)
            critical_bad = critical_bad or key in CRITICAL_FIELDS
    notes = []
    if missing:
        notes.append('حقول مفقودة: ' + ', '.join(missing))
    if mismatched:
        notes.append('حقول مختلفة: ' + ', '.join(mismatched))
    ratio = matched / considered if considered else 0.0
    ok = (not critical_bad) and ratio >= min_ratio
    if not ok or notes:
        notes.append(f'تطابق الحقول بعد التطبيع: {matched}/{considered}')
    return ok, notes


def records_equivalent(a_doc: dict[str, Any] | None, b_doc: dict[str, Any] | None) -> bool:
    """True when two stored documents carry the same business record (format-insensitive)."""
    a, b = clean_payload(a_doc), clean_payload(b_doc)
    if not a or not b:
        return False
    keys = set(a) | set(b)
    return all(k in a and k in b and lenient_equal(k, a[k], b[k]) for k in keys)
