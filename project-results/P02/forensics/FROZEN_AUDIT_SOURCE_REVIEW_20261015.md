# P02 frozen-source Audit Trail targeted proof

Frozen SHA: `f5558c250922f306e0389c7c915edc5c78e9ba05`.

The midterm grader selects `oracle.sample('test_01', classes=['correctable'], n=18)`. All 18 are specifically correctable fixtures, **not clean unmodified examples**. Grader result after NameError repair [38633271725](https://github.com/omrbosnd/bigdata-grader/actions/runs/38633271725) reports:
- `batch.cleaning_samples`: PASS 17/18.
- `batch.audit_trail`: INCONCLUSIVE 10/18 (56%). Detailed evidence: 10 embedded audits, 7 documents present and matching Oracle cleaning but with no audit (`external_audit_status: NO_MATCH`), 1 expected document absent in validated.
- Grader policy: PASS >=70%, FAIL <40%, middle band INCONCLUSIVE.
- `src/quality_rules.py` writes audit correction records for date/email/phone/currency/financial values but:
  1. Strips leading/trailing whitespace in `order_id` and `status` (and other text fields) without correction event.
  2. Never changes string `items_json.qty` to integer, or string `unit_price` to numeric.
  3. Fails to strip `YER` suffix from financial string, quaratines it instead of correcting.
  4. Does not restore missing order prefix `طلب-` from `order_id`.
  5. Does not recalculate total from items + delivery where needed.
- `src/elt_pipeline.py` persists the `data` including `corrections` using `UpdateOne({'order_id':...},{'$set':data},upsert=True)`; no evidence that grader stripped this field on persistence.
- Teacher's original fixture generator `datasets/generate_hidden_tests.py` has correctable cases `order_id_extra_spaces`, `status_extra_spaces`, `qty_as_string_in_items`, `unit_price_as_string_in_items`, `price_with_currency_suffix` etc.

Run independent proof only against exact frozen SHA, no secrets, no student edits. Do not guess which of seven sample hashes maps to which case without hidden manifest; source-defect categories can be reproduced independently.
