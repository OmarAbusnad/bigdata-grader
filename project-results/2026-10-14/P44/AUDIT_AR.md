# P44 — طارق ثامر

> Forensic evidence review: no reruns and no grade changes. This report documents old evidence only.

- Frozen source SHA: `ecf2c4bd368689ed80e28eb68bce402ab29f2154`
- [Immutable student source](https://github.com/tarep2021-hue/big-data-pipeline/tree/ecf2c4bd368689ed80e28eb68bce402ab29f2154)
- Old evidence: [GitHub Actions #37874152827](https://github.com/omrbosnd/bigdata-grader/actions/runs/37874152827); [follow-up #38088837812](https://github.com/omrbosnd/bigdata-grader/actions/runs/38088837812)
- Previously calculated credit-only score: **14.111/25** (NOT an approved final academic mark: midterm rubric was DRAFT_DISABLED)
- Assertion summary: **31 PASS / 1 FAIL / 4 INCONCLUSIVE / 25 NO_EVIDENCE**. The PASS tally is not the academic mark.

## Independent frozen-source findings

بنية المشروع المجمدة تحتوي النصفي، ولا يوجد تطبيق FastAPI النهائي. بعض مخرجات البيانات اختلفت عن مرجع الاختبار: validated 16706، quarantine 3044، وUpsert 628. دليل Audit 10/18.

## Adjudication of pending or failed checks

batch.validated_count / batch.quarantine_count / upsert.final_validated — فروق أعداد فعلية لا تثبت أن حساب Oracle خطأ؛ batch.audit_trail — بعض العينات لم تحقق التوقع. بلا تطبيق نهائي لا يصح عد كل final endpoint إخفاقًا وظيفيًا مستقلا.

## Responsibility policy and evidence trail

- Every historical PASS for the same exact SHA is preserved.
- Student-source failure: identify actual frozen file/line or logged runtime discrepancy; a blocked downstream check is not a second independent failure.
- Grader problem: open a tracked issue; a flawed probe cannot be charged as student failure and cannot automatically become PASS.
- No evidence / untested rubric item: grader coverage gap to document (see [issue #33](https://github.com/omrbosnd/bigdata-grader/issues/33)).
- Discussion: human academic judgment only.
- Original evidence artifact `unified-P44-37874152827` has `reports/P44/result.json`, `reports_final/P44/result.json`, and `reports_unified/P44/result.json` with matching evaluation.md. This is the primary raw evidence for the counts above.
- Detailed audit CSV covering every recorded assertion is in the externally generated review package; it is **not** a claim that the official rubric has been approved.

**Do not run tests or change existing grades as part of this evidence-only report.**
