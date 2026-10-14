# P68 النهائي وP69 النصفي — نتائج استكمال المرحلتين المحذوفتين

**تاريخ التحقق:** 2026-10-15. **التشغيل:** [38636543404](https://github.com/omrbosnd/bigdata-grader/actions/runs/38636543404)، اكتمل بنجاح من ناحية GitHub Actions في 2026-10-14T21:20:46Z. **PR:** [#42](https://github.com/omrbosnd/bigdata-grader/pull/42). **قضية الإنصاف:** [#44](https://github.com/omrbosnd/bigdata-grader/issues/44). جميع الأعداد هنا نتائج assertions، **ليست درجات /25**.

## إثبات تجميد المصدر والنتائج

| المشروع والمرحلة | SHA المجمد بالضبط | Artifact | PASS | FAIL | INCONCLUSIVE | Runtime |
|---|---|---|---:|---:|---:|---|
| P68 — النهائي فقط | `1c0b2b4652e51c33209f6a89e7a580100276f591` | [11928566492](https://github.com/omrbosnd/bigdata-grader/actions/runs/38636543404/artifacts/11928566492) | **24** | **0** | **1** | COMPLETED |
| P69 — النصفي فقط | `cfce6b1d0b0b8fcae26a6b6f2e805c10479539cf` | [11929697855](https://github.com/omrbosnd/bigdata-grader/actions/runs/38636543404/artifacts/11929697855) | **0** | **1** | **23** | STARTUP_BLOCKED |

الأعداد مستخرجة من `reports_final/P68/result.json` و`reports/P69/result.json` داخل Artifacts، لا من نجاح GitHub Actions. ملفات `frozen/P68.metadata.json` و`frozen/P69.metadata.json` تؤكد SHA المطلوب لكل مشروع. لم تُعَد مرحلة P68 النصفي أو P69 النهائي، ولم تُعدّل مصادر الطلاب أو درجاتهم.

## P68 — النهائي

**كل الاختبارات الآلية الـ24 PASS**. مفاتيحها:

`final.api.discovered, final.api.server, final.api.contract, final.api.health, final.api.docs, final.api.json, final.api.ingest, final.queries.count, final.queries.runtime, final.aggregations.count, final.aggregations.runtime, final.indexes.count, final.indexes.compound, final.indexes.explain, final.mv.refresh, final.mv.collections, final.mv.incremental, final.mv.aggregation_basis, final.jobs.count, final.jobs.manual_run, final.jobs.schedule, final.jobs.logging, final.github_readme, final.dependencies`.

الاختبار الوحيد غير المحسوم هو `final.discussion`، وحالته **INCONCLUSIVE** لأن المناقشة اليدوية (0.25) لا تُصحح آليًا. من الأدلة التنفيذية: `GET /health` أعاد 200؛ `POST /ingest` أعاد 200 ونتجت في MongoDB **20,000 raw و17,000 validated و3,000 quarantine**؛ نجحت استعلامات وتقارير التجميع والفهارس والعروض المادية والمهام. لا توجد نتيجة FAIL في النهائي على هذا SHA.

**إسناد المسؤولية:** حذف مرحلة النهائي سابقًا بسبب تسجيل المشروع على أنه midterm فقط كان نقصًا في جدولة المصحح/سجل التسليم، وليس إخفاقًا من الطالب. الاستكمال عالج هذا النقص. لا يلزم إعادة اختبار النصفي الناجح سابقًا.

## P69 — النصفي

**FAIL واحد فقط**: `batch_pipeline.command`، حيث اختار المصحح أمر `python -m src.main /grader-tests/test_01_small_batch_pipeline.csv` وانتهى بـ `TIMEOUT` بعد **1200.163 ثانية**، `returncode=124`.

**الاختبارات الـ23 الأخرى INCONCLUSIVE** وليست FAIL مثبتًا. مفاتيحها:

`batch_pipeline.engine, batch.raw_count, batch.validated_count, batch.quarantine_count, batch.duplicates, batch.unique_index_runtime, batch.schema_validator_runtime, batch.cleaning_samples, batch.audit_trail, batch.quarantine_errors, spark_pipeline.command, spark_pipeline.engine, spark.raw_count, spark.validated_count, spark.quarantine_count, spark.duplicates, upsert.baseline_validated, upsert.final_validated, upsert.insert_samples, upsert.update_samples, upsert.unchanged_samples, idempotency.validated_stable, idempotency.duplicates`.

سبب الحجب المتسلسل أن الأمر المختار شغّل خادم API طويل التشغيل بدل مهمة استيراد بيانات تنتهي. في SHA المجمد:
- `README.md` يفصل أمر النصفي `python -m src.ingestion.pipeline --file data/sample.csv` عن أمر API `python -m src.main`.
- `src/main.py` يستدعي `uvicorn.run(app,...)`، لذلك لا يتوقع انتهاء تشغيله تلقائيًا.
- `src/ingestion/pipeline.py` يحتوي دالة `run_pipeline(file_path)` تعيد استجابة تجريبية `status: ingested` مع ملاحظة `Wire this to your existing midterm pipeline`؛ ولا يحتوي مسار `__main__` أو CLI ينفذ معالجة البيانات. إذن **يوجد أيضًا قصور مستقل في مصدر الطالب**: الأمر الموثق في README ليس تنفيذًا فعليًا للـpipeline، لكن لم يُختبر سلوكه في هذا التشغيل بسبب خطأ الاكتشاف الأول.

**إسناد المسؤولية:**
1. **خطأ المصحح المؤكد:** اختيار أمر API لتقييم النصفي، وتحويل انتهاء مهلة الخادم إلى FAIL لعملية ingest. لا يجوز تحميل الطالب هذه المهلة أو اعتبار الـ23 اختبارات راسبة.
2. **قصور كود الطالب المثبت بالمراجعة:** `src/ingestion/pipeline.py` ليس Pipeline حقيقيًا؛ الدالة stub ولا تُشغَّل عبر CLI كما يذكر README. هذا دليل مصدري، **وليس نتيجة اختبار سلوكي جديدة**. لا تمنح PASS أو درجة اعتمادًا عليه.
3. **المطلوب:** إصلاح اكتشاف أمر النصفي في المصحح، ثم اختبار **P69 النصفي وحده** على SHA نفسه بعقد تشغيل واضح ومثبت؛ الاحتفاظ بنهائي P69 الذي اختُبر سابقًا. إن لم يكن هناك CLI عامل، تُوثق حالة التشغيل الفعلية والسبب بدقة دون نسبة خطأ المصحح للطالب.

## متابعة مسائل الإنصاف

- [Issue #45](https://github.com/omrbosnd/bigdata-grader/issues/45) يوثق خطأ `NameError: json not defined` السابق في المصحح وإصلاحه في `c9a527b`، مع إعادة اختبارات النصفي المحجوبة فقط. هذه مشكلة مستقلة عن اكتشاف أمر P69.
- [Issue #44](https://github.com/omrbosnd/bigdata-grader/issues/44) يحتفظ بجدول فرص الطلاب وأدلة كل SHA. كان تعليقه الأقدم يصف P68 النهائي وP69 النصفي بـ`NOT_ASSESSED`؛ هذا التقرير يسد النقص دون تغيير النتائج السابقة.
- P23/P33 يحتاجان موافقة بشرية على مصدر Git ذي التاريخ المنفصل قبل دمج أي حكم.
- لا درجات رسمية ولا مناقشة يدوية عُدلت. لا إعادة للمرحلتين السابقتين.

## مصادر الإثبات

- [تشغيل المرحلتين فقط](https://github.com/omrbosnd/bigdata-grader/actions/runs/38636543404)
- [Artifact P68](https://github.com/omrbosnd/bigdata-grader/actions/runs/38636543404/artifacts/11928566492)
- [Artifact P69](https://github.com/omrbosnd/bigdata-grader/actions/runs/38636543404/artifacts/11929697855)
- [كود P69 المجمد](https://github.com/newump2017-coder/Final-project-bigdata/tree/cfce6b1d0b0b8fcae26a6b6f2e805c10479539cf)
- [كود P68 المجمد](https://github.com/Bilal-AlShami/bigdata-hybrid-pipeline/tree/1c0b2b4652e51c33209f6a89e7a580100276f591)
