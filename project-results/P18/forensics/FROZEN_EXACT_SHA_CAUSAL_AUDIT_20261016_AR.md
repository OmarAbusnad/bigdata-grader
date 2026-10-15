# التحقيق السببي الكامل في خصومات P18 — أيمن قيس

**المصدر المجمد**: `aimanqais1/big-data-pipeline-project@2024f325c24c3626c30193ab27945d9440093c25`. **لا تغيير في كود الطالب ولا في كشف الدرجات**.

## أدلة تجريبية مستقلة
1. [تقييم المصحح الأصلي](https://github.com/omrbosnd/bigdata-grader/actions/runs/38088837812) / artifact `11683856974`: النصفي PASS=27 FAIL=7 INCONCLUSIVE=1؛ النهائي PASS=21 FAIL=1 INCONCLUSIVE=3.
2. [فحص جميع 20,000 سطر مقابل Oracle سري بنفس seed](https://github.com/omrbosnd/bigdata-grader/actions/runs/38807180610)، artifact `12006473545`. تأكد التطابق التام مع snapshot: validated=18,250 و quarantine=1,750 مقابل المتوقّع 17,000 و3,000.
3. [إعادة بناء أسباب Upsert وIncremental على المعرّفات الفعلية في المصدر](https://github.com/omrbosnd/bigdata-grader/actions/runs/38807539616)، artifact `12006733611`. تطابق 18,994 بعد test03 و19,539 بعد test04.
4. [تشغيل اختبارات الطالب الأصلية](https://github.com/omrbosnd/bigdata-grader/actions/runs/38807910308)، artifact `12006449725`: 15/15 PASS من `tests/test_cleaning_rules.py`. مجموع الدوال `test_*` في تسليم الطالب 67 موزعة على 8 ملفات.

## 1. أسباب فرق Batch: 1,250 سجلًا

جميع الحالات الآتية مخفية في مجموعة المدرس، ومع ذلك اختبرها الفاحص مباشرة عبر `src.quality_rules.process_and_classify_record`:

| الحالة | المقبول خطأً | السبب الموجود في المصدر |
|---|---:|---|
| `invalid_phone_too_short` | 250 | `normalize_phone()` يعيد `err=None` في حال الهاتف غير الصالح |
| `missing_item_sku` | 250 | `validate_and_recalculate_order()` يستخدم `str(item.get('sku',''))` دون رفض الفراغ |
| `negative_quantity` | 250 | لا يعزل الكمية السالبة إلا بشرط إضافي `calculated_items_total <= 0` |
| `unknown_currency` | 250 | لا يتحقق من قيمة `raw_record.currency` بل يستنتج `YER` من مبلغ الدفع |
| `unknown_order_status` | 250 | `normalize_text_and_synonyms()` لا يرفض حالة لا تنتمي إلى قائمة الحالات |
| **المجموع** | **1,250** | تطابق تام مع قاعدة البيانات الفعلية |

**صحيح نصفي**: `batch.validated_count` = 18,250 بدل 17,000؛ `batch.quarantine_count` = 1,750 بدل 3,000. تسجيل أسباب الحالات *التي عُزلت فعلًا* 40/40 PASS، لكنه لا يغطي الأخطاء التي لم تُعزل.

## 2. Audit Trail غير مكتمل

حالات `correctable` ذات `corrections=[]` عبر مجموعة الـ5,000:
- `currency_arabic_name` 294 من 294؛
- `order_id_extra_spaces` 295/295؛
- `order_id_missing_prefix` 295/295 **ويظل business ID خاطئًا**؛
- `qty_as_string_in_items` 294/294؛
- `status_extra_spaces` 294/294؛
- `unit_price_as_string_in_items` 294/294.

تقرير المصحح الأصلي 10/18 (56%) على عينة Audit، أقل من حد PASS 70% وأعلى من FAIL المؤكد 40%؛ لذلك نتيجته `INCONCLUSIVE` (ليس PASS ولا FAIL تقنيًا). نقص التوثيق في ستة أنواع من التصحيحات **حقيقي**؛ عدم استرداد كامل 1.25 دون تقييم rubric، مع الاعتراف بنجاح 10 حالات.

## 3. أسباب Upsert وIncremental EXACT

- `test_03`: actual **744** keys جديدة مقابل expected **600**؛ تتكون الزيادة +144 من **125** حالة عزل خاطئة (25 لكل فئة من الخمس) و**19** سجلًا `update` / `unchanged` صار مُدخلًا جديدًا لعدم استعادة بادئة `طلب-` في Batch (**11 updates + 8 unchanged**).
- `test_04`: actual **545** مقابل expected **500**؛ تتكون الزيادة +45 من **41** حالة عزل خاطئة و**4** سجلات update/unchanged بمفتاح غير مطابق (**2+2**).
- إعادة تشغيل test03 وtest04 لم تُنشئ مفاتيح validated جديدة (Idempotent على المعرّف الخاطئ)، لذلك حصلت الاختبارات المعاد تشغيلها على PASS رغم خطأ التصنيف.
- `src/incremental_loader.py` في المصدر **مجرد placeholder** يعيد `OPTIONAL_PATH_B_AVAILABLE` ولا ينفذ CDC حقيقيًا. قد يستلزم ذلك تقييمًا مستقلًا إن كان Plan B إلزاميًا؛ لا تُضاعف العقوبة دون rubric.

## 4. Spark

- `spark_pipeline.command=FAIL`: `ClassNotFoundException: mongodb.DefaultSource`.
- `src/spark_loader.py` يستخدم `get_spark_classpath()` من `jars/*.jar`؛ لا توجد أي ملفات `.jar` في Git tree المجمد، ولا `spark.jars.packages` لتحميل الموصل آليًا.
- `get_spark_classpath` يجمع ملفات JVM بـ`;` المخصص لـWindows بدل `os.pathsep`؛ مخاطرة إضافية على Linux عند وجود عدة JARs.
- `spark.raw_count=0` و `spark.validated_count=0` يعكسان فشل تهيئة كتابة MongoDB، **وليس إثبات أن معالجة PySpark الداخلية خاطئة**.
- **ملاحظة على المصحح لصالح الطالب**: `spark.quarantine_count=PASS` و `spark.duplicates=PASS` على قاعدة فارغة، رغم فشل Spark في إدخال أي سجل. ينبغي اعتبارهما محجوبين عند توقف المحرك، لا PASS فعليين.

## 5. النهائي

- API, Queries, Aggregations, 3 Materialized Views, Scheduled Jobs: PASS بالمصحح.
- `final.indexes.explain=INCONCLUSIVE`، خسارة 0.30: كود `src/queries/index_manager.py` يضم `.explain()`؛ المصحح أثبت 3 IXSCAN. لكن **لا توجد مقارنة Before/After موثقة على 3 استعلامات**. لا يوجد دليل كافٍ لمنح PASS لهذا البند.
- `final.github_readme=INCONCLUSIVE`، خسارة 0.25: README شامل لمعظم الموضوعات، لكنه **لا يحتوي شرح Explain أو executionStats**. فحص المصدر أكد ذلك.
- `final.dependencies=FAIL`، خسارة 0.25: ملف المتطلبات موجود، FastAPI/Uvicorn موجودان، لكن `.env.example` غير موجود. **قاعدة المصحح الأحدث** تفصل فحص `.env` عن الاعتماديات: `deps_ok = has_requirements and fastapi_declared and uvicorn_declared`. لا يشترط ملف env إذا لم يوثق README نسخه؛ README المجمد لا يطلبه. لذا 0.25 من الخصم خطأ مصحح بموجب القاعدة الحالية، ما لم يكن شرطًا صريحًا في rubric الرسمي.
- `final.discussion=INCONCLUSIVE`، خسارة 0.25: تقييم شفهي يدوي، **ليس خطأ برمجيًا**.

## 6. معيار code/tests/docs — درجة كاملة لم تختبر

- `__UNTESTED_CRITERION__.code_tests_docs` منح 0/1 دون اختبار آلي، وهو **لا يثبت فشل الطالب**.
- في SHA يوجد README ~33 ألف حرف، requirements، 8 ملفات اختبارات، 67 دالة اختبار. نجح اختبار التنظيف الحقيقي `15/15` على GitHub Actions.
- لم يُعد تشغيل جميع 67 اختبارًا؛ لذلك لا يُمنح 1/1 تلقائيًا. يلزم Rubric شفهي/يدوي لتقدير الدرجة.

## مجموع الدرجة وفق الملف الحالي (من دون تعديل)
- النصفي `11.811/18`، النهائي `5.950/7`، المجموع `17.761/25`.
- خصم النصفي 6.189 = Batch 0.667 + Spark 1.8 + Audit 1.25 + Quarantine 0.75 + Upsert 0.222 + Incremental 0.5 + code/docs غير مختبر 1.0.
- خصم النهائي 1.05 = Explain .30 + README .25 + Dependencies .25 + المناقشة اليدوية .25.
- **المقدار الوحيد القابل للاسترداد آليًا بثقة بموجب كود المصحح الجديد هو `final.dependencies` 0.25؛ تصبح الدرجة المحتملة 18.011/25، لكنها غير معدلة في الكشف**.
- كل ما عدا ذلك يحتاج حكم rubric واضح، خاصة 1.0 code/tests/docs و0.25 شفهي و0.30 Explain و0.25 README و1.25 Audit.

**قواعد العدالة:** لا استبدال لنسخة الطالب، لا كشف لأسرار teacher oracle، لا تحوير لكود الطالب، ولا درجة مضافة آليًا دون إثبات أو موافقة المدرس.
