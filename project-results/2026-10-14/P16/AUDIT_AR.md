# P16 — عبدالسلام الغبسي

> Forensic evidence review: no reruns and no grade changes. This report documents old evidence only.

- Frozen source SHA: `38b0d23dc6136f639a4b37aa0406a4da362fbaa8`
- [Immutable student source](https://github.com/abdalsalam77/midterm-data-pipeline/tree/38b0d23dc6136f639a4b37aa0406a4da362fbaa8)
- Old evidence: [GitHub Actions #37874152827](https://github.com/omrbosnd/bigdata-grader/actions/runs/37874152827); [follow-up #38088837812](https://github.com/omrbosnd/bigdata-grader/actions/runs/38088837812)
- Previously calculated credit-only score: **13.111/25** (NOT an approved final academic mark: midterm rubric was DRAFT_DISABLED)
- Assertion summary: **29 PASS / 4 FAIL / 3 INCONCLUSIVE / 25 NO_EVIDENCE**. The PASS tally is not the academic mark.

## Independent frozen-source findings

لا توجد شيفرة FastAPI للنهائي في التسليم المجمد؛ يوجد src/schema_validation.py لكن إثبات تشغيل Schema Validator لم يكتمل في الاختبار. اختلفت أعداد التنظيف والتحديث التزايدي عن Oracle.

## Adjudication of pending or failed checks

batch.schema_validator_runtime — فجوة إثبات في اختبار التشغيل، لا دليل لإدانة الطالب لمجرد فقدان probe؛ batch.audit_trail — 9/18 عينات تحقق، مراجعة دلالات عينات المصدر؛ incremental.final_validated — 483 مقابل المتوقع 500، اختلاف مخرج الطالب يحتاج مرجعًا مفصلًا. النهائي غير مختبر وظيفيًا لأن التطبيق غير موجود في المصادر.

## Responsibility policy and evidence trail

- Every historical PASS for the same exact SHA is preserved.
- Student-source failure: identify actual frozen file/line or logged runtime discrepancy; a blocked downstream check is not a second independent failure.
- Grader problem: open a tracked issue; a flawed probe cannot be charged as student failure and cannot automatically become PASS.
- No evidence / untested rubric item: grader coverage gap to document (see [issue #33](https://github.com/omrbosnd/bigdata-grader/issues/33)).
- Discussion: human academic judgment only.
- Original evidence artifact `unified-P16-37874152827` has `reports/P16/result.json`, `reports_final/P16/result.json`, and `reports_unified/P16/result.json` with matching evaluation.md. This is the primary raw evidence for the counts above.
- Detailed audit CSV covering every recorded assertion is in the externally generated review package; it is **not** a claim that the official rubric has been approved.

**Do not run tests or change existing grades as part of this evidence-only report.**
