# تحقق مصدر Git المجمد — P02 / P15 / P18 / P46
**التاريخ:** 15 أكتوبر 2026. **النتائج:** تحقق من أحكام تشغيل أصلية + شيفرة الطالب عند SHA محدد + فحص حي مستقل لـP46 فقط. لم تُعدل شيفرات الطلاب أو درجاتهم المنشورة.

## P46 أيهم — يوجد خطأ مصحح فعلي
- الطالب `AihamAlqasem/Enterprise-Grade-Data-Ingestion-ELT-Pipeline@c66ac3f53de2db27359ce2345b02e67b1cea9a33`.
- المصحح في التشغيل [38088837812](https://github.com/omrbosnd/bigdata-grader/actions/runs/38088837812) سجّل `final.jobs.manual_run FAIL` مع **0/0 طلبات**، ثم `final.jobs.logging FAIL` نتيجة عدم وجود سجلات.
- المسبّب: `grader/final_runtime.py` يشتق أسماء المهام من `GET /jobs`، لكن مشروع الطالب يعيد **سجل التنفيذ** (فارغ في البداية) لا القائمة؛ الأسماء `update_views` و`generate_report` موجودة صراحة في `src/api.py` و`src/scheduled_jobs.py` و`readme.md`.
- الاختبار الحي المستقل [38649411726](https://github.com/omrbosnd/bigdata-grader/actions/runs/38649411726)، artifact ID **11933453330**، تحقق SHA، Python 3.11 وMongoDB 7.0 منفصلين: `POST /jobs/update_views/run` و`POST /jobs/generate_report/run` أعادا **HTTP 200**، وسُجلت عمليتان `Success` في `jobs_log` تتضمنان `start_time,end_time,status,details`، وتولدت `daily_sales_mv` و`reports/latest_payment_report.json` بصورة فعلية.
- **القرار:** لا يصح اعتبار `final.jobs.manual_run` فشل طالب. وقد تحقق التسجيل عمليًا؛ `grader/final_compliance.py` يقبل `details` بديلًا عن `result`. وفقا للوزن المرجعي: `manual_run` = 0.25، و`logging` = 0.25، أي **استرداد محتمل مؤيد بالاختبار 0.50/25** بعد تحديث سجل الأحكام وإعادة الحساب. `final.jobs.count` و`final.jobs.schedule` يحتاجان تقييمًا مستقلًا: API لا تُعرّف أسماء الوظائف في GET /jobs، ولا يبدأ Scheduler تلقائيًا عند بدء API. لا تُمنح نقاطهما تلقائيًا.
- [Issue #46](https://github.com/omrbosnd/bigdata-grader/issues/46) لتعميم اكتشاف المهام وتصحيح السجل.

## P15 بلقيس — خلل اعتماديات الطالب مثبت، مع أثر بيئة مصحح متداخل
- المصدر `TheBalqees26Jamil/hybrid-orders-pipeline@4144a24b6331f7a411ec3ec2d78e9bfb6948edb3`.
- تنفيذ [38088837812](https://github.com/omrbosnd/bigdata-grader/actions/runs/38088837812) أخفق في Spark لأن Maven لا يستطيع جلب الموصل من شبكة الاختبار المعزولة؛ لا يجوز الاستناد إلى رسالة الشبكة وحدها لإثبات خلل الطالب.
- لكن `config/settings.py` يحدد `org.mongodb.spark:mongo-spark-connector_2.12:11.1.0`، و`requirements.txt` يحدد `pyspark>=3.5` بلا سقف. الإصدار 11.1.0 مطابق لنسخة Scala 2.13 (Spark 4)، بينما إصدار Mongo Spark Connector 10.x هو المتاح لـScala 2.12 (Spark 3.5) في قائمة الإصدارات الرسمية. بذلك يوجد **خلل قابل لإعادة الإثبات في مواصفة الاعتماديات المجمدة**، وليس مجرد شبكة.
- `config/settings.py` و`src/mongo_setup.py` يوجهان quarantine إلى `quarantine_orders` بينما عقد التقييم ونص متطلبات المساق يستخدمان `orders_quarantine`. النتيجة القديمة `0` هي رصد لمجموعة **مختلفة**، فلا تصلح لإثبات أن خوارزمية Quarantine أنتجت صفرًا. مع ذلك اسم المجموعة غير مطابق للعقد. لم يُقَس عدد `quarantine_orders` الحقيقي؛ لا ننسب مقدار فرق 3,000 كله إلى فشل التصنيف.
- في المجموعة الصحيحة `orders_validated` شوهد 18,206 مقابل 17,000 متوقع، و`upsert.final_validated` 810 مقابل 600؛ اختلافات مثبتة بالقياس، سببها التفصيلي يحتاج اختبار عينات.

## P18 أيمن — الاعتماديات الناقصة من المصدر المجمد تثبت فشل الطالب في Spark
- `aimanqais1/big-data-pipeline-project@2024f325c24c3626c30193ab27945d9440093c25`.
- `src/spark_loader.py` يستدعي `get_spark_classpath()` الذي لا يجلب شيئًا سوى `jars/*.jar` المحلي من `config/settings.py`. فحص شجرة SHA لم يجد مجلد `jars` أو أي ملف JAR. `requirements.txt` يحدد `pyspark>=4.2.0` لكن لا يثبّت Mongo Spark Connector تلقائيًا.
- فشل `ClassNotFoundException: mongodb.DefaultSource` في [38088837812](https://github.com/omrbosnd/bigdata-grader/actions/runs/38088837812) متسق تمامًا مع هذا النقص المحدد في المشروع. لا توجد أدلة كافية لتصنيف هذا الفشل خطأ مصحح. Batch أيضًا حقق 18,250 validated و1,750 quarantine مقابل 17,000 و3,000 متوقعة؛ فحوص كمية منفصلة يجب الإبقاء عليها ما لم يُثبت خلل Oracle.

## P02 أبرار — اختلاف حسابات فعلي وغياب Validator من الشيفرة
- `AbrarMarwan/BigData_pipline@f5558c250922f306e0389c7c915edc5c78e9ba05`. آخر نصفي مصحح [38633271725](https://github.com/omrbosnd/bigdata-grader/actions/runs/38633271725)؛ النهائي 24 PASS في [38632370130](https://github.com/omrbosnd/bigdata-grader/actions/runs/38632370130).
- Batch خرج صفر exit code؛ عدد `orders_raw` 20,000، `orders_validated` 17,706، `orders_quarantine` 2,294 مقابل العدد المرجعي Quarantine 3,000. Upsert final validated بلغ 728 مقابل 600؛ لا يوجد دليل على فشل بدء التشغيل. المصدر `src/quality_rules.py` يتضمن قواعد عزل فعلية، ولكنها تعطي نسبًا مختلفة على بيانات الاختبار.
- `src/mongo_setup.py` ينشئ المجموعات والفهارس الفريدة فقط، **ولا ينشئ `$jsonSchema` Validator**: غيابه مؤكد من كود SHA ومن اختبار MongoDB الحي القديم.
- Audit Trail في مصحح هذه النسخة 10/18؛ بعض أحداث التصحيح مفقودة من أدلة الاختبار. يظل وصف `INCONCLUSIVE` أدق من نسبة جميع النواقص إلى الطالب بلا فحص عينات كامل.

## ضوابط القرار
1. لم تكن إعادة التحقق شاملةً لكل وظائف المشاريع؛ إثبات أصل الاختبار المحدد فقط. لا يوصف خطأ الشبكة بأنه خطأ الطالب دون إثبات خطأ اعتماديات من SHA.
2. نجاح GitHub Actions يعني نجاح تشغيل المختبر لا نجاح جميع الاختبارات الأكاديمية.
3. لا تمس درجات المعايير الأخرى ولا تحول INCONCLUSIVE إلى FAIL مثبت بسبب سياسة الصفر.
4. لم تتغير الدرجات الرسمية؛ تصحيح P46 يتطلب إدخال PASS الجديدة في ledger ثم إعادة الحساب بنفس أوزان ملف الطالب.

## المراجع
- [MongoDB Spark Connector 11.x](https://www.mongodb.com/docs/spark-connector/current/getting-started/)
- [MongoDB Spark Connector 10.x](https://www.mongodb.com/docs/spark-connector/v10.x/getting-started/)
- [Maven 2.12 available versions](https://www.javadoc.io/versions/org.mongodb.spark/mongo-spark-connector_2.12)
