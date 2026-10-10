# الدليل الشامل لمصحّح مشاريع Big Data — مرجع التشغيل والتطوير وتسليم المهمة

> **اقرأ هذا الملف أولًا إذا انضممت للمشروع الآن.**  
> **تاريخ توثيق الحالة:** 10 أكتوبر 2026.  
> **المستودع:** `Prideidea/bigdata-grader` (خاص؛ لا تشارك بيانات الطلاب أو الاختبارات السرية علنًا).  
> **الفرع المعتمد للتوثيق:** `main`.  
> **نقطة الأساس التي راجعتها قبل كتابة هذا الدليل:** `bf81642eee7b52b9e43193e3209addcc2c8f89a5`، مع ملاحظة أن `main` قد يتحرك؛ افحص SHA الفعلي قبل كل تشغيل.  
> **الوضع الأكاديمي:** لم تُعتمد نتائج الـ68 مشروعًا نهائيًا. مصحّح النصفي يعمل سلوكيًا لكن Rubric النصفي الرسمي غير مفعل؛ النهائي له Rubric نشط من 7 درجات، بينها مناقشة يدوية.  
> **مهم:** هذا الدليل ليس جدول درجات ولا يأذن بإعادة تشغيل جميع الطلاب. هو وثيقة معرفة وتشغيل ومراجعة وقرار.

---

## 0. ابدأ من هنا — ماذا يفعل الشخص الجديد خلال أول 15 دقيقة؟

1. اقرأ الأقسام **1–6** لفهم الغرض، الأمان، وتجميد المشاريع؛ ثم الأقسام **7–10** لمعرفة الاختبارات والدرجات؛ ثم **15–19** لمعرفة المشكلات والقرارات الحالية.
2. افتح [المستودع](https://github.com/Prideidea/bigdata-grader)، واقرأ أيضًا `README.md` و`ARCHITECTURE.md` و`grader-policy.yaml` و`MANUAL_SETUP.md`.
3. افتح [تشغيل تجميد المشاريع 37390623044](https://github.com/Prideidea/bigdata-grader/actions/runs/37390623044)، ثم [التقييم المرجعي الموحد 37874152827](https://github.com/Prideidea/bigdata-grader/actions/runs/37874152827). هذه هي **لقطة الطالب** و**التقييم المرجعي التاريخي**؛ ليست أحدث حكم بعد الإصلاحات.
4. شغّل **CI فقط** على الفرع الذي ستعمل عليه. لا تشغل `Grade Project Unified` لجميع المشاريع.
5. اجمع الأحكام المرجعية والإضافات المستهدفة عبر `project_id + test_key + commit_sha + evidence_run_id`، واحتفظ دائمًا بأصل الحكم وسجل التغيير.
6. إذا كانت المشكلة مثبتة في المصحح، أصلح **القانون العام** مع اختبار Regression، ثم أعد **الاختبار/المرحلة المحجوبة فقط**. **إذا كان السبب طالبًا مثبتًا، وثِّقه ولا تُعد تشغيله بلا سبب**.
7. لا تُصدر درجة معتمدة دون Rubric النصفي الرسمي ومراجعة درجة المناقشة وأدلة الاعتراضات.

### حقائق تشغيلية سريعة

| العنصر | الحقيقة |
|---|---|
| إجمالي التسليمات | 68 مشروعًا/مجموعة، IDs من `P01` إلى `P68` |
| اللقطة المجمدة | Freeze run `37390623044` |
| خط أساس النتائج | Unified grading run `37874152827` |
| الاختبارات | Midterm Test 01/02/03 وTest 04 لـPlan B، واختبارات Final API + MongoDB + الوظائف |
| التقييم | `PASS` / `FAIL` / `INCONCLUSIVE` / `ERROR` / `SKIP`؛ ليست درجات عددية بحد ذاتها |
| Rubric النصفي | `rubrics/midterm_18.json`، الحالة `DRAFT_DISABLED`، 18 نقطة **تجريبية وغير معتمدة** |
| Rubric النهائي | `rubrics/final_7.json`، الحالة `ACTIVE`، 7 نقاط بينها 0.25 مناقشة بشرية |
| الذكاء الاصطناعي | لفهم المستودع واكتشاف أمر التشغيل وتشخيص عدم اليقين؛ **لا يمنح الدرجة** |
| التنفيذ | Docker مستقل لكل مشروع، MongoDB معزولة، ومدخلات مخفية لا يرى الطالب مفاتيح تصحيحها |
| السياسة المتفق عليها | تصحيح تراكمي؛ لا إعادة للمشاريع الـ68؛ لا مسح أي PASS؛ لا خصم بلا دليل |
| GitHub Actions باللون الأخضر | يعني أن الـworkflow اكتمل، **ولا يعني أن الطالب PASS في كل الاختبارات** |

---

## 1. لماذا بنينا المصحح أصلًا؟ المشكلة التعليمية والتقنية

المقرر هو **Big Data العملي**. طُلب من الطلاب بناء خطوط بيانات على Python/PySpark/MongoDB مع تنظيف السجلات، ELT، عزل المرفوض، Upsert، Idempotency، والعمل التزايدي وواجهة API في النهائي. تسليمات الطلاب ليست قالبًا موحدًا: تختلف أسماء الملفات، أوامر CLI، إعدادات MongoDB، طريقة اختيار Batch/Spark، الإصدارات، وحتى أن بعضهم سلّم ملفات مضغوطة.

التصحيح اليدوي لـ68 مشروعًا يخلق مشكلات: اختلاف طريقة الاختبار بين طالب وآخر، صعوبة التحقق من ملايين الصفوف، الاعتماد على لقطات شاشة أو README بدل تشغيل السلوك، وتكرار الخصم على عطل واحد سبّب إخفاق عدة اختبارات تابعة. كذلك لا يصح إجبار الطالب على تعديل مشروعه لمجرد أن المصحح لم يفهم طريقة تشغيله.

بنينا **مصححًا مركزيًا موحّدًا** ليحقق:

- **العدالة وإعادة الإنتاج:** نفس البيانات المخفية، نفس الشروط المعلنة، نفس oracle، مع SHA مجمد لكل تسليم.
- **التقييم السلوكي:** إثبات نتائج MongoDB الحية والفهارس والتحويلات، لا الاكتفاء بوجود أسماء ملفات.
- **العزل:** لا تُشغّل شيفرة غير موثوقة على جهاز المعلم أو مستودع المصحح مباشرة.
- **الاستيعاب:** اختيار أمر التشغيل والـDB/collections وفق شيفرة/README كل مشروع؛ الذكاء الاصطناعي مساعد للاكتشاف فقط.
- **إثبات سبب الرسوب:** سجل أوامر، حالة Docker، stdout/stderr، snapshot قبل وبعد، expected/actual، ومعيار مرتبط بالدرجة.
- **التصحيح التراكمي:** إصلاح عيوب المصحح مرة واحدة، تعديل الأحكام المعيبة من أدلة محفوظة أو إعادة الاختبار المتأثر فقط، دون هدم النجاحات السابقة.
- **التمييز بين ثلاث قضايا مستقلة:** (أ) هل أمكن تنفيذ الاختبار؟ (ب) هل نجح الطالب في وظيفته؟ (ج) ما الدرجة الأكاديمية المستحقة؟

**خارج نطاق المصحح عمدًا:** لا يصلح ملفات الطلاب، لا يفترض حصولهم على درجات لم تختبر، لا يقرر درجة مناقشة شفوية، ولا يعتبر تعطل Docker/Gemini/Maven رسوبًا طالبًا.

---

## 2. المبادئ الإلزامية لأي شخص سيكمل العمل

1. **Freeze is immutable:** المصدر الرسمي للطالب هو Commit/أرشيف التجميد، وليس HEAD الحالي في مستودع الطالب.
2. **Never replay passed tests:** لا تعِد `PASS` سابقًا بسبب عطل في اختبار آخر. إن تطلب إصلاحٌ هندسي بناء البيئة، لا يعني ذلك إعادة كل مراحل المصحح.
3. **Only proven grader-originated retests:** المبرر المقبول لإعادة الاختبار: خطأ مصحح محدد + اختبارات متأثرة بالاسم + إصلاح اختُبر + حفظ الدليل.
4. **Evidence replay first:** إذا كانت snapshots والسجلات المحفوظة كافية لتصحيح حكم، استعمل overlay دون تنفيذ الطالب.
5. **No implicit zero:** `INCONCLUSIVE` و`ERROR` و`PRECONDITION_NOT_SATISFIED` ليست أصفارًا.
6. **No indiscriminate tolerance:** حدود ±1% للأعداد الإجمالية لا تلغي اختبار تنظيف عينة أو بنية فهرس أو صحة تحديث حقل.
7. **Don't reward empty success:** `0→0` لا يثبت Idempotency، وصفر duplicate في collection فارغة لا يثبت جودة المعالجة.
8. **Do not double count:** فشل Batch baseline لا يُعدّ خصمًا ثانيًا مستقلاً لـUpsert فقط بسبب اختلاف العدد الإجمالي الثابت.
9. **Fix general methods, not student-specific scores:** ممنوع «تعديل المصحح على مقاس P05 ثم كسره على P06». الاستثناء المشروع هو اختيار أمر تشغيل **موثق في مصدر الطالب** أو إعادة مقطع محدد بدليل.
10. **Original artifacts stay intact:** لا تكتب فوق `unified-Pxx-37874152827` ولا فوق `frozen-Pxx-37390623044`. كل تعديل حكم محفوظ في overlay مع `from/to/reason/evidence_run`.
11. **Student vs grader vs environment:** لا تُنسب مشكلة Java أو Spark أو PyPI أو إعداد المسار إلى الطالب دون معرفة هل السبب من تصريحه هو أم من قيود المصحح.
12. **Review gate before grades:** لا تُنشر درجات أو Issues عقابية قبل حسم الـRubric والاختبارات المعلقة وضوابط المراجعة.

---

## 3. المعمارية العامة

```text
submission_groups.csv / submissions.csv
             |
             v
FREEZE: checkout commit ثابت + tar.gz + frozen_submissions.csv
             |
             v
Heuristic discovery (README/config/argparse/files)
             |                \
             |                 --> Gemini README-first / targeted-on-failure
             |                                  |
             +---------- ExecutionPlan <--------+
                              |
                    confidence / command guard
                      |                  |
                   acceptable        uncertain
                      |                  |
                      v                  v
                 Docker per-project   MANUAL_REVIEW
                      |
        student runtime + MongoDB per project
        offline hidden CSV -> student input only
        teacher oracle stays outside the container
                      |
              Batch / Spark / Upsert / Delta
              Final FastAPI + endpoints + DB
                      |
                MongoDB host-side snapshots
                      |
         deterministic assertions + logs + source refs
                      |
            reports/Pxx/result.json
            reports_final/Pxx/result.json
            reports_unified/Pxx/result.json
                      |
       review-only overlays from cached evidence
       narrow retry artifacts when grader fault proven
                      |
     academic review + official rubric + discussion
                      |
         FINAL APPROVED GRADE (not yet done)
```

**لماذا MongoDB مستقلة؟** بعض المشاريع كتبت اسم قاعدة ثابتًا؛ عزل الخادم يمنع تداخل مجموعات الطلاب. توجد آلية `socat` لتمرير `localhost:27017` من حاوية الطالب إلى MongoDB الخاص به. يجب التحقق من قاعدة البيانات النشطة بصورة **غير ملتبسة** عند اختلاف الاسم.

**لماذا نسختان للشبكة؟** `isolated` الافتراضية تحمي التشغيل وتحصره. `compat` تتيح توافقًا أوسع، لكنها لا تُستخدم عامًا أو سرًا لإزالة مشكلات الطلاب. لعوائق Maven استُخدم نهج أفضل: تنزيل الاعتماديات المعلنة أثناء **بناء الحاوية** ثم استعمال Ivy cache المحلي وقت التنفيذ المعزول.

---

## 4. خريطة الملفات — لمن يتولى كل مسؤولية؟

### ملفات نقطة الدخول والإدارة

| الملف | وظيفته |
|---|---|
| `README.md` | التعريف الأصلي، الاستخدام، ومبادئ V4 |
| `ARCHITECTURE.md` | قرارات التصميم والعزل وعدم تحويل غياب الأدلة إلى صفر |
| `MANUAL_SETUP.md` | الأسرار والإعداد الأولي لـGitHub |
| `SECURITY.md` و`grader-policy.yaml` | الأمان وعدالة التقييم |
| `submission_groups.csv` | معرفات المشاريع وأعضاء المجموعات وروابط التسليم |
| `submissions.csv` | قائمة تسليمات/بيانات مدخلة؛ **ليست بديلًا عن manifest المجمد** |
| `freeze_submissions.py` | تجميد مشروع واحد أو بناء manifest |
| `evaluate_project.py` | المُنسّق الرئيسي لتقييم Midterm/Final/All |
| `evaluate.py` / `evaluate_all.py` | مسارات CLI تاريخية/مساندة؛ لا تُستخدم لإعادة شامل دون قرار |
| `evaluate_final.py` | مسار النهائي المستقل |
| `build_runtime_image.py` و`runtime-image/Dockerfile` | إنشاء بيئة الطلاب الأساسية |
| `regrade_saved_evidence.py` | إعادة إصدار أحكام من التقارير المحفوظة فقط |
| `doctor.py` / `setup.sh` / `setup.ps1` | فحص وإعداد المتطلبات المحلية |
| `VERSION` | يصرّح `4.1.0`؛ بعض تقارير المنسق تستخدم معرف `4.3-unified`. اعتمد SHA الفعلي لا اسم الإصدار وحده |

### مكتبة المصحح `grader/`

| الملف | أهم شيء يجب فهمه |
|---|---|
| `discovery.py` | Heuristics والأوامر والـstdin والـDB والعتبات من README/argparse |
| `agent_analyzer.py` | Gemini، تحليل README أولاً ثم الملفات المستهدفة عند الفشل، ضمن حدود الاستخدام |
| `plan_resolution.py` | دمج خطط Heuristic/AI وبوابة الثقة `0.80` |
| `models.py` | `ExecutionPlan` و`AssertionResult` و`RuntimeCaseResult` |
| `execution_contract.py` | التحقق من أوامر التشغيل ومتى يصلح استخدامها |
| `overrides.py` + `overrides/README.md` | Override تملكه هيئة التدريس لا يُضاف لمستودع الطالب |
| `sandbox.py` | Docker/Mongo، حدود الموارد، بناء الاعتماديات، Ivy offline وطرق التشغيل |
| `sandbox_runtime.py` | المنفذ الرسمي لاختبارات النصفي الفعلية |
| `tests_midterm.py` | تحقق عينات Cleaning/Quarantine/Upsert وعتبات النِّسب |
| `mongo_checker.py` | snapshots، مفاتيح مكررة، Indexes، schema validator |
| `normalization.py` | تنظيف الحقول والمقارنة الدلالية لسجلات الأعمال |
| `count_policy.py` | سماحية الأعداد 1% و5% والاستقرار قبل/بعد وإدخال سجلات جديدة |
| `oracle.py` | قراءة مفاتيح الاختبارات السرية على جهة المصحح |
| `spark_probe.py` / `runtime_evidence.py` | توليد large probe، وتحديد Batch/Spark من أدلة فعلية |
| `spark_dependency_audit.py` | تشخيص موصلات Spark المعلنة، وفرق خطأ الطالب/بيئة Maven |
| `spark_recovery_overlay.py` | دمج إثبات تشغيل Spark المستهدف مع أحكام اختباراته دون فقدان PASS |
| `final_discovery.py` | اكتشاف تطبيق FastAPI وREADME وإصداراته |
| `final_runtime.py` | اختبار الـAPI والبيانات والفهارس والـMVs والـJobs |
| `final_compliance.py` / `api_semantic_normalizer.py` | قراءة دلالات النتائج والتوثيق وExplain |
| `frozen_api_source_audit.py` | فحص مصدر FastAPI في تسليم مجمد دون تنفيذ |
| `safe_archive_submission.py` | استخراج ZIP/RAR التسليمات المجمّدة بأمان (P24/P52) |
| `evidence_regrade.py` | إعادة تقدير أحكام مخطئة من snapshots سابقة |
| `scoring.py` | تحويل Evidence capabilities إلى rubric **عندما تكون ACTIVE** |
| `report.py` / `static_checks.py` | كتابة التقارير والأدلة الثابتة غير الكافية وحدها للنجاح |

### ملفات الاختبار والتراجع

- `tests/test_count_policy.py`: سياسة الأعداد والعدّ النسبي.
- `tests/test_runtime_logic.py` و`test_runtime_orchestrator.py`: تسلسل مراحل النصفي.
- `tests/test_final_v42.py` و`test_final_binary_upload.py` و`test_final_ingest_path_contracts.py` و`test_final_ingest_transport_errors.py`: عقود النهائي والأخطاء السابقة في إرسال الطلب.
- `tests/test_final_refresh_contract.py` و`test_final_mv_transport_precondition.py`: معلمات الـMV وحالات المهلة.
- `tests/test_spark_prewarm_context.py` و`test_spark_dependency_audit.py` و`test_spark_recovery_overlay.py`: إصلاح Spark.
- `tests/test_safe_archive_submission.py`: منع Zip Slip والروابط الرمزية والغموض.
- `tests/test_interactive_detection.py` و`test_discovery_documented_mongo_backend.py`: اكتشاف CLI والمشروع التفاعلي.
- `tests/test_engine_router_json_regression.py`: لا تُفسّر عبارة Spark في نص سبب التشغيل كأن المحرك الفعلي Spark.
- مجمل اختبارات Regression يُشغّل بـ`pytest -q`، وCI يفحص `py_compile` كذلك. لا يعني نجاحها أن كل طلاب الدفعة اجتازوا.

---

## 5. مصادر الحقيقة وترقيم المشاريع

### ما الذي تم تجميده ولماذا؟

- **Freeze run:** [37390623044](https://github.com/Prideidea/bigdata-grader/actions/runs/37390623044)، من 5–6 أكتوبر 2026، يحتوي على 68 أرشيفًا باسم `frozen-P01-37390623044` … `frozen-P68-37390623044`، و`frozen-manifest-37390623044`.
- كل أرشيف يحتوي `Pxx.repo.tar.gz` وmetadata؛ manifest يربط `project_id` و`repo_url` و`commit_sha` وحالة التجميد.
- لا تستبدل المصدر المجمد بفرع `main` أو PR أحدث في مستودع الطالب، حتى لو أصلح الطالب أخطاءه بعد التسليم؛ إلا بقرار أكاديمي معلن بشأن المهلة.
- **Unified baseline:** [37874152827](https://github.com/Prideidea/bigdata-grader/actions/runs/37874152827)، بتاريخ 9 أكتوبر 2026؛ منشور فيه 68 artifact باسم `unified-Pxx-37874152827`. المرجع الذي بدأ منه التصحيح التراكمي.
- التقارير اللاحقة **مصادر إضافية** وليست نسخًا تمحو الأصل.

### الحقول الأساسية لربط الحكم

```json
{
  "project_id": "P05",
  "student_commit_sha": "SHA from the frozen manifest",
  "phase": "midterm",
  "test_key": "spark_pipeline.command",
  "old_verdict": "INCONCLUSIVE",
  "new_verdict": "PASS",
  "reason": "offline Maven grader environment fixed",
  "source_run_id": 37874152827,
  "proof_run_id": 38003977105,
  "student_code_changed": false,
  "passed_tests_reexecuted": 0,
  "academic_grade_approved": false
}
```

**قاعدة دمج حاسمة:** المفتاح المنطقي `(project_id, phase, assertion_key, frozen_commit)`، مع ترتيب الأدلة حسب `proof_run_id` والمصدر. احتفظ بسجل تغيير غير قابل للمحو `audit_log`. التناقض في `commit_sha` يمنع دمج الحكم آليًا.

### كيف تحصل على الأدلة من GitHub Actions؟

1. افتح رابط run ثم **Artifacts**؛ لا تكتفِ بالإشارة الخضراء.
2. للملف الأصلي ابحث عن `unified-Pxx-37874152827` ثم `reports/Pxx/result.json` أو `reports_final/Pxx/result.json`، وفي بعض تشغيلات `reports_unified/Pxx/result.json`.
3. لنتيجة مستهدفة اقرأ ملف `reports_targeted_* / Pxx / *.json`؛ قد يكون `verdict=INCONCLUSIVE` رغم أن وظيفة GitHub Actions انتهت `success`.
4. دقّق `runtime.cases[].runtime_log`، `snapshot_before`، `snapshot_after`، `assertions`، `stdout_tail` و`stderr_tail`، و`execution_plan`.
5. احفظ رقم run وSHA الخاص به مع أي تغيير، وتحقق من **محتوى** artifact قبل الاستناد إليه.

---

## 6. تجهيز المصحح وإعداد الأسرار

### المتطلبات التقنية

- Python **3.12** للمصحح في GitHub Actions.
- Docker Engine عامل، وبناء حاوية `bigdata-grader/student-runtime:4.1`؛ تأكد من `runtime-image/Dockerfile` لمعرفة إصدارات Java/PySpark الفعلية بدل التخمين.
- Git؛ MongoDB تعمل عادة من صورة `mongo:7.0` لكل مشروع.
- أدوات ملفات مضغوطة `rarfile` و`libarchive-tools` في workflow إصلاح P24/P52 فقط.
- لا تثبت متطلبات الطلاب على بيئة Python الخاصة بالمصحح؛ تتبع كل حاوية `requirements.txt` أو ملفات البناء الخاصة بذاك المشروع.

### الأسرار

| الاسم | وظيفته | ملاحظة |
|---|---|---|
| `GRADER_HIDDEN_SEED` | توليد ملفات Hidden Tests نفسها لكل مشروع | Required؛ لا تكتبه في Git أو المحادثات |
| `GEMINI_API_KEY` | المساعدة في قراءة README/إصلاح ExecutionPlan | Workflow الموحد قد يطلبه؛ لا تسجل قيمته |
| `STUDENT_REPOS_TOKEN` | قراءة المستودعات الخاصة إن وجدت | اختياري، محدود `read-only` |
| `GRADER_LLM_MODEL` | نموذج Gemini في Actions Variables | يمكن تغييره؛ الـworkflow الحالي قد يستخدم `gemini-3.1-pro-preview` |
| `GRADER_PREWARM_SPARK` | تمكين تجهيز Maven/Ivy المحلي وقت بناء حاوية مشروع معين | `1` فقط للحالات المثبتة؛ لا تضعه عامًا بلا فحص |

**ملاحظة تاريخية:** أجزاء من `README.md` تشير إلى `OPENAI_API_KEY` من تصميم سابق. **الكود الفعلي في `grader/agent_analyzer.py` والـGitHub workflows الحالية يستخدم Gemini** (`GEMINI_API_KEY`). اتبع الكود وSecrets الحالية، لا أمثلة README القديمة إذا تعارضت.

### أوامر محلية آمنة

```bash
python -m pip install -r requirements.txt
pytest -q
python -m py_compile evaluate.py evaluate_final.py evaluate_project.py grader/*.py
python doctor.py
python build_runtime_image.py
# لا تشغّل التقييم الجماعي هنا.
```

لتوليد بيانات مصحح محلية **دون كشف seed**:

```bash
python datasets/prepare_hidden_tests.py --regenerate --seed "$GRADER_HIDDEN_SEED"
```

لا تنشر `datasets/hidden/teacher_key.json` ولا `teacher_manifest.csv` ولا الملفات الطلابية أو بيانات الأسرار خارج المستودع الخاص/Artifacts المخوّلة.

---

## 7. حزمة الاختبارات المخفية (Midterm): البيانات والأهداف

المصدر: `datasets/generate_hidden_tests.py`، أداة التحضير `datasets/prepare_hidden_tests.py`، Oracle في `grader/oracle.py`. الأعداد التالية **إعداد افتراضي في generator**؛ تقارير run المجمد و`teacher_key.json` هي مصدر الحقيقة إذا عُدلت الأحجام بالمدخلات.

| الاختبار | الملف | الإدخال | التكوين المتوقع | الهدف |
|---|---|---:|---|---|
| **01 Batch** | `test_01_small_batch_pipeline.csv` | 20,000 صف | 12,000 نظيف + 5,000 قابل للتصحيح + 3,000 Quarantine = **17,000 Validated** | Batch، Raw، تنظيف، عزل، Audit، مؤشرات |
| **02 Spark** | `test_02_large_spark.csv` | 100,000 صف | نظيفة 100%، expected Validated=100,000 وQuarantine=0 | محرك Spark وLarge Data مع حفظ Mongo |
| **03 Upsert** | `test_03_upsert_idempotency.csv` | 2,000 صف | 600 Insert + 600 Update + 500 Unchanged + 300 Quarantine | حفظ السجل الموجود، تحديثه، منع التكرار؛ **الزيادة الجديدة 600** لا كل رصيد DB |
| **04 Incremental/Plan B** | `test_04_incremental_plan_b.csv` | 1,000 صف | 500 Insert + 300 Update + 100 Unchanged + 100 Quarantine | Delta/Lookback وRerun no-op؛ زيادة **500** |
 
**الحالات المصطنعة في البيانات:** أرقام هندية عربية، أسعار بعملة/فواصل، هواتف بنمط الدولة ومسافات، بريد مع `@@` أو نطاق غير صالح، تواريخ غير مقبولة أو `dd/mm/yyyy`، كمية وسعر كنص داخل `items_json`، `items_json` تالف، معلومات عملاء/مفاتيح ناقصة، قيمة سالبة، عملة غير معروفة، وقيم يمكن تصحيحها مقابل حالات لا يجوز تمريرها.

**المخرجات المرجعية للأعداد الافتراضية عند تنفيذ متسلسل صحيح:** Test01 = 17,000 Validated؛ بعد Test03 ≈17,600؛ بعد Test04 ≈18,100، مع شرط صحة بيانات السجلات والفهرس والعزل. الأرقام ليست بديلاً عن اختبار حالة الأعمال.

**عتبة اختيار المحرك:** generator يوصي بـ20MB لاختبار Batch مقابل Spark؛ عند وجود Threshold قابل للتغيير يضبطه المصحح لتمكين اختبار كلا المحركين. قد يولد `spark_probe.py` ملفًا أكبر لاختبار المسار الذي اختار Batch رغم توقع Spark. لا تفرض على مشروع Threshold لا يدعم تغييره؛ صنف الاختبار وفق العقد والأدلة.

### المعلومات المسموح للطالب برؤيتها

ملفات CSV مدخلات فقط على Mount معزول؛ **teacher_key.json** و**teacher_manifest.csv** و**expected.json** تبقى لدى المصحح، ولا تركب داخل حاوية الطالب. لا تكشف test IDs ومعايير manifest التفصيلية لجهة غير مخوّلة.

---

## 8. اختبارات النصفي كاملة — الـ35 Assertion

المصدر الفعلي: `grader/sandbox_runtime.py` و`grader/tests_midterm.py` و`grader/mongo_checker.py`. تنفذ خمس مراحل فكرية: **Batch → Spark → baseline → Upsert + rerun → Plan B Delta + rerun**. الأسماء التالية مأخوذة من تقرير سلوكي فعلي للمشروع P24 بعد تفعيل Plan B.

### (أ) Batch / Python — 11 معيارًا

| مفتاح الاختبار | ماذا يثبت؟ |
|---|---|
| `batch_pipeline.command` | أمر التشغيل أكمل المهمة؛ Exit code/timeout وسجل التنفيذ |
| `batch_pipeline.engine` | استخدم `python_batch` فعلًا، لا مجرد ذكر الكلمة في README |
| `batch.raw_count` | كل صفوف الملف وصلت `orders_raw` بالعدد المتوقع |
| `batch.validated_count` | العدد الإجمالي للصفوف المقبولة بعد التصحيح وفق سياسة الأعداد |
| `batch.quarantine_count` | عدد المرفوض الصحيح وفق سياسة الأعداد |
| `batch.duplicates` | لا توجد مفاتيح أعمال مكررة داخل بيانات Validated |
| `batch.unique_index_runtime` | فهرس Unique حقيقي على Business Key وليس ادعاءً نصيًا |
| `batch.schema_validator_runtime` | `$jsonSchema` فعّال داخل MongoDB |
| `batch.cleaning_samples` | مقارنة عينات حقول فعلية مع Oracle، وليس عدًّا فقط |
| `batch.audit_trail` | توثيق التحويل/التصحيح للسجلات المعالجة |
| `batch.quarantine_errors` | لكل سجل رفض أدلة/سبب Error Code قابل للفحص |

### (ب) Spark — 6 معايير

| المفتاح | الشرط |
|---|---|
| `spark_pipeline.command` | أمر Test02 أنجز مهمة الإدخال على البيانات الكبيرة |
| `spark_pipeline.engine` | المحرك الفعلي PySpark، مثبت بسجل تشغيل/DB engine metadata |
| `spark.raw_count` | إدخال بيانات Test02 الكبيرة في Raw |
| `spark.validated_count` | 100,000 Validated للملف النظيف افتراضيًا |
| `spark.quarantine_count` | Quarantine صفر في المدخل النظيف |
| `spark.duplicates` | لا duplicates غير مصرح بها في بيانات valid **غير فارغة** |

### (ج) Baseline + Upsert/Idempotency — 12 معيارًا

| المفتاح | الشرط |
|---|---|
| `upsert_baseline.command` | إعادة تأسيس baseline تعمل |
| `upsert_baseline.engine` | المحرك الموافق لملف Batch |
| `upsert.baseline_validated` | مقارنة baseline المعاد بـ**الواقع الذي أُنشئ أول مرة** لا بالرقم المثالي مجددًا |
| `upsert_first.command` | تشغيل ملف Test03 |
| `upsert.final_validated` | **الصفوف الجديدة فقط** من فرق `after−before`؛ الافتراضي 600 |
| `upsert.duplicates_first` | لا تكرار مفاتيح بعد Upsert |
| `upsert.insert_samples` | صفوف Insert الجديدة موجودة وحقولها سليمة |
| `upsert.update_samples` | صفوف Update غيّرت السجل القديم إلى القيمة الصحيحة |
| `upsert.unchanged_samples` | الصفوف غير المتغيرة بقيت كما هي دلاليًا |
| `upsert_rerun.command` | إعادة تنفيذ Test03 |
| `idempotency.validated_stable` | عدم تغير عدد validated على rerun ناجح؛ صفر→صفر غير حاسم |
| `idempotency.duplicates` | rerun لا ينشئ duplicate business keys |

### (د) Incremental / Plan B — 6 معايير

| المفتاح | الشرط |
|---|---|
| `incremental_first.command` | تشغيل ملف Test04 |
| `incremental.final_validated` | زيادة السجلات الجديدة فقط، الافتراضي 500 |
| `incremental.duplicates_first` | لا duplicate keys بعد delta |
| `incremental_rerun.command` | إعادة نفس ملف Delta |
| `incremental.rerun_validated_stable` | العدد بعد rerun مطابق لـقبل rerun، مع بيانات ناجحة موجبة |
| `incremental.rerun_duplicates` | لا تكرار بعد إعادة Delta |

**توضيح التعداد:** 11 + 6 + 12 + 6 = **35 معيارًا** عندما تكتمل جميع المراحل وتُفعّل `--plan-b`؛ المشروع الذي يتعطل بدءه قد يسجل معايير blocked بدل جميع المعايير، فلا تتعامل مع 35 على أنها عدد ثابت لكل مشروع.

### حدود عينات التنظيف/الفحص

في `grader/tests_midterm.py`: إذا وُجدت عينات، فإن دالة ratio تعمل عادة بـ`PASS≥80%` و`FAIL<50%` وبينهما `INCONCLUSIVE`؛ مع بعض معايير Quarantine بـ`PASS≥75%` و`FAIL<30%`. الحالات التي لا توجد لها عينات كافية تصبح `INCONCLUSIVE`، وليست 0 نجاح ولا 0 درجة تلقائيًا.

---

## 9. سياسة الأعداد والتصحيح النسبي — لماذا غيّرنا المقارنة؟

النسخ المبكرة قارنت عدة أعداد بـ**رقم ثابت للمعلم** حتى عندما كان baseline للطالب مختلفًا؛ فتسبب ذلك في تسجيل إخفاقات تابعة مكررة. الإصلاح الحالي في `grader/count_policy.py`:

- `compare_count(actual, expected)`: حتى **1%** اختلاف للأعداد الإجمالية = `PASS`؛ أكثر من 1% وحتى **5%** = `INCONCLUSIVE` لمراجعة دلالية؛ أكثر من 5% = `FAIL` إذا القياس صحيح والمقدمة صحيحة؛ `expected=0` يتطلب صفرًا بالضبط.
- `compare_new_inserts(after, before, expected_inserts)`: قياس **عدد الزيادة** بدل مقارنة الرصيد النهائي بمرجع مطلق، ويعتبر انخفاض العدد أثناء إدراج متوقع مشكلة.
- `compare_stability(after, before)`: الاستقرار مقارنة قبل/بعد نفس الإعادة؛ **0→0 لا يثبت وظيفة**، وفرق العدد هو دليل إخفاق استقرار إذا اكتملت المقدمة.
- `compare_baseline_replay(actual_baseline, original_batch)`: لا يُخصم Upsert ثانية بسبب خلل Batch baseline فقط.
- تنظيف العينات، صحة الحقول، Quarantine codes، وجود فهارس، وUpdate payload **ليست لها سماحية 1% تلقائية**.

**مثال مهم:** الطالب بدأ Batch بـ18,000 Validated بدل 17,000. عندما يعيد نفس baseline وينتج 18,000 مجددًا، فهذا **استقرار baseline**، رغم أن درجة تنظيف Batch قد تكون متأثرة. لا تجعل `upsert.baseline_validated` FAIL لمجرد أنه ليس 17,000. وفي Test03 يجب النظر إلى `after−before≈600`، ثم فحص عينات Insert/Update/Unchanged.

**لا تُعدّل العتبات قبل مراجعة معيار المقرر**؛ أي تعديل لسماحية العد يجب أن يكون عامًا وموثقًا مع اختبارات regression.

---

## 10. متطلبات النهائي: واجهة API والأدلة الحية

النهائي مرحلة فوق نظام النصفي. ينفذ الخادم في Sandbox ويُفحص Swagger/OpenAPI والـMongoDB. العقود الأساسية في `grader/final_runtime.py`:

| Method | Endpoint | الغاية |
|---|---|---|
| GET | `/health` | حالة الخدمة |
| POST | `/ingest` | تشغيل خط الإدخال نفسه على ملف مخفي |
| POST | `/indexes` | إنشاء الفهارس |
| GET | `/queries` | سرد الاستعلامات |
| GET | `/queries/{name}` | تنفيذ استعلام بعينه |
| GET | `/aggregations` | سرد التقارير التجميعية |
| GET | `/aggregations/{name}` | تنفيذ تقرير تجميعي |
| POST | `/refresh-mv` | تحديث Materialized Views |
| GET | `/jobs` | تعريف الوظائف المجدولة |
| POST | `/jobs/{name}/run` | تشغيل Job يدويًا |
| GET | `/docs` و`/openapi.json` | أدوات فحص وتوثيق FastAPI |

### جميع مفاتيح التحقق المهمة في النهائي

| المفتاح | آلية التقييم |
|---|---|
| `final.api.discovered` | اكتشاف FastAPI حقيقي من README/الشيفرة المجمدة |
| `final.environment.build` | بيئة الاعتماديات قابلة للبناء |
| `final.api.server` | الخادم يبدأ ويمكن فحصه |
| `final.api.contract` | المسارات المطلوبة موجودة في OpenAPI |
| `final.api.health` | `/health` 2xx |
| `final.api.docs` | `/docs` متاح |
| `final.api.json` | الاستجابات التشغيلية الصحيحة بتنسيق JSON |
| `final.api.ingest` | استجابة 2xx **مع أثر إدخال حقيقي في MongoDB** |
| `final.queries.count` | ≥5 استعلامات عملية معرفة |
| `final.queries.runtime` | ≥5 استدعاءات ناجحة للاستعلامات |
| `final.aggregations.count` | ≥5 تقارير Aggregation |
| `final.aggregations.runtime` | ≥5 استدعاءات ناجحة مع نتائج ذات دلالة |
| `final.indexes.count` | ≥3 فهارس غير `_id` |
| `final.indexes.compound` | ≥1 Compound Index |
| `final.indexes.explain` | أدلة `explain/executionStats` والجدوى وظهور `IXSCAN` حيث يلزم |
| `final.mv.refresh` | طلب تحديث صحيح 2xx بعد تهيئة البيانات المطلوبة |
| `final.mv.collections` | ≥2 Materialized Views مأهولة |
| `final.mv.incremental` | التحديث الثاني incremental/idempotent أو no-change موثَّق |
| `final.mv.aggregation_basis` | الـMVs مبنية على تجميعات ذات معنى |
| `final.jobs.count` | ≥2 وظائف مجدولة |
| `final.jobs.manual_run` | يمكن تشغيل وظيفتين بنجاح يدويًا |
| `final.jobs.schedule` | Cron/interval/schedule واضح |
| `final.jobs.logging` | Logs البداية والنهاية والحالة والنتيجة |
| `final.github_readme` | README يغطي التثبيت والتشغيل وAPI وQueries وIndexes/Explain وMVs وJobs |
| `final.dependencies` | وجود FastAPI/Uvicorn وrequirements وبيئة موثقة |
| `final.discussion` | **مناقشة/فهم يدوي**، لا يُستنتج من الاختبار الآلي |
| `final.runtime.exception` | استثناء المقيّم/البيئة عند وجوده؛ **ليس افتراضيًا خطأ طالب** |

**فرق بالغ الأهمية:** إثبات نجاح `POST /ingest` لا يعني تلقائيًا أن كل صف وصل `Validated` بشكل مطابق للـOracle. الاختبار يثبت أن الـAPI شغّل الخط وأحدث أثرًا؛ تنظيف الملف يُقيّم باختبارات مستقلة.

### معالجة اختلاف عقود الـAPI

يدعم المصحح إرسال file path عبر `query` أو `application/json` أو `form`، وإرسال **محتوى CSV الفعلي** داخل `multipart/form-data` عندما يتطلب `UploadFile`. لا تفسّر `422` على أنه فشل الطالب قبل التأكد أن المصحح أرسل الحقول المطلوبة الصحيحة.

في `/refresh-mv` قد يتطلب المشروع `name=city_sales` أو `mode=full` أو غيرهما؛ استخرج المطلوب من OpenAPI/مصدر الطالب ولا تُخترع قيمة. إن تعذر بناء الطلب الصحيح فسجله `INCONCLUSIVE`؛ إذا أُرسل طلب صحيح وأعاد 500 مع traceback من كود الطالب، فهذا دليل مختلف.

انتهاء مهلة اتصال grader دون status ليس HTTP 500 طالبًا، ولا يصح الخصم على استعلام تابع لم يُنفّذ بسبب تهيئة ناقصة.

---

## 11. الدرجات والمعايير — الوضع الرسمي لا التخمين

### النصفي — 18 درجة **غير مفعلة**

الملف `rubrics/midterm_18.json` يوزع **تجريبيًا فقط**:

| البند التجريبي | النقاط |
|---|---:|
| Architecture + Router | 1.5 |
| Python Batch | 2.0 |
| PySpark | 3.0 |
| ELT + Raw | 2.0 |
| Cleaning + Audit Trail | 2.5 |
| Quarantine | 1.5 |
| Upsert + Idempotency | 2.0 |
| Metrics + Consistency | 1.0 |
| Code + Tests + README | 1.0 |
| Advanced Track | 1.5 |
| **الإجمالي** | **18.0** |

**حالة هذا الملف `DRAFT_DISABLED`.** عدم اعتماد توزيعه يعني عدم استحقاق حساب درجات نهائية آلية منه حتى يُوثَّق المعيار الذي سُلِّم للطلاب ويُعتمد. `grader/scoring.py` يرفض Rubric غير ACTIVE، و`evaluate_project.py` يصرح `scoring_status=RUBRIC_DISABLED`.

### النهائي — 7 درجات ACTIVE

| البند المعتمد في الملف الحالي | النقاط |
|---|---:|
| Queries + Indexes + Explain | 1.50 |
| Aggregations | 1.50 |
| Materialized Views | 1.50 |
| Scheduled Jobs | 1.00 |
| Unified API / Testing Interface | 0.75 |
| GitHub + README / Organization | 0.50 |
| Discussion / Understanding | 0.25 |
| **الإجمالي** | **7.00** |

**المناقشة 0.25 نقطة لا تدخل في التقييم الآلي ويجب إدخالها بشريًا.** قد تحتوي بعض الفئات على FAIL/INCONCLUSIVE متداخل؛ لا تحوّلها إلى كسر تلقائي دون مراجعة منطق `evaluate_final.py` وأدلة الفئة.

### علاقة Assertions بالدرجات

- الـ35 Assertions ليست 35 درجة.
- شروط PASS الفردية هي **أدلة** على تحقق مخرجات تعلم؛ توزّع وفق Rubric.
- FAIL طالب مثبت + معيار تعليمي معتمد = قد يبرر خصمًا.
- INCONCLUSIVE بسبب مصحح/مقدمة/بيئة = **لا خصم آلي**؛ وضع مراجعته ظاهر حتى الحسم.
- GitHub Action `success` يعني نجاح Job ورفع Artifacts غالبًا، لا «الطالب 18/18».
- الأرقام المقدرة أو النطاقات في Excel ليست كشفًا أكاديميًا موقعًا ومعتمدًا.

---

## 12. دورة حياة التقييم الصحيحة وأوامر الاستكمال

### أ. تشغيل Freeze جديد — **لا تفعله للدفعة الحالية دون تفويض**

```bash
python freeze_submissions.py --project P05 --output-dir frozen
python freeze_submissions.py --build-manifest \
  --artifacts-dir frozen_downloads --output frozen_submissions.csv
```

الـworkflow الرسمي `.github/workflows/freeze.yml` هو **Freeze & Prepare Submissions**. الدفعة الحالية مجمدة بالفعل من run `37390623044`؛ لا تطلق Freeze جديدًا وتستبدل المرجع.

### ب. تشغيل آمن لمشروع واحد إذا اضطررت

```bash
python evaluate_project.py \
  --project P05 \
  --submissions frozen_submissions.csv \
  --workspace workspaces/P05/repo \
  --mode midterm \
  --network-profile isolated \
  --plan-b
```

**تحذير:** هذا يعيد مجموعة اختبارات النصفي للمشروع، وليس اختبارًا منفردًا؛ لا تستخدمه إذا كانت لديه نجاحات قديمة لا تحتاج تكرارها. للمشكلة المحددة استخدم الـtargeted runner أو saved-evidence overlay.

### ج. تحليل بيانات محفوظة دون تشغيل الطالب

```bash
python regrade_saved_evidence.py \
  --input saved_reports \
  --out reports_cached_midterm \
  --source-run-id 37874152827 \
  --expected-projects 68
```

يجب أن تكون `saved_reports` مجلدًا حقيقيًا يحوي التقارير الأصلية بالتركيب المتوقع. المخرجات **Review overlays**؛ لا تُبدّل التقرير الأصلي تلقائيًا.

### د. فحص المعايير والمصحح

```bash
python -m pip install -r requirements.txt
pytest -q
python -m py_compile evaluate.py evaluate_final.py evaluate_project.py \
    freeze_submissions.py grader/*.py datasets/*.py
```

إذا فشل اختبار CI، أصلح المصحح واختبره **قبل** تشغيل أي مشروع طالب. لا تفسّر فشل CI على أنه فشل أكاديمي.

---

## 13. كتالوج GitHub Actions — متى تستخدم كل Workflow؟

| Workflow | الغاية | كيف تستخدمه الآن؟ |
|---|---|---|
| `ci.yml` — CI | Unit tests + compile | أول خيار بعد أي تغيير |
| `freeze.yml` — Freeze & Prepare Submissions | تجميد دفعة ومستودعات وmanifest | **لا تعِد Freeze للدفعة الحالية** |
| `grade-project.yml` — Grade Project Unified | Midterm/Final/All لمشاريع تختارها | لا تستخدم اختيار «الكل» الآن؛ يمكن مشروعًا **بموافقة ومبرر** |
| `batch.yml` — Grade Batch | تشغيل قديم/مساعد للنصفي | تجنب الإعادة الجماعية |
| `final.yml` — Grade Final | تشغيل النهائي الكامل | لا تستخدمه لاستعادة اختبار نهائي فاشل واحد |
| `evidence-regrade.yml` | تصحيح من تقارير محفوظة دون تشغيل الطلاب | **مفضّل أولًا** لكل غلط يقبل التحليل من Evidence |
| `static-spark-audit.yml` | فحص 19 مشروعًا لمشاكل Spark/Maven دون تنفيذ | لتوثيق سبب الاعتمادية |
| `targeted-spark-p05.yml` | إثبات إصلاح Ivy على P05 | تجربة تاريخية، انتهت بإثبات نجاح Spark |
| `targeted-spark-cohort.yml` | اختبار Spark المحجوب فقط لمجموعة منتقاة | تحقق من نتائج كل artifact ولا تعِد التشغيل بلا مانع جديد |
| `targeted-spark-threshold.yml` و`targeted-spark-p26.yml` و`targeted-spark-p55-p64.yml` | إصلاح قيمة threshold ومرحلة Spark فقط | تشغيلات مركزة تاريخية |
| `targeted-spark-p60.yml` | مشروع داخل مجلد nested | استخدم Frozen workspace مطابقًا |
| `targeted-midterm-recovery.yml` | استرجاع P08 قليل الثقة | تاريخي ومحصور بـP08 |
| `targeted-midterm-p23.yml` | تنفيذ P23 مع `--backend mongo` الموثق | تاريخي ومحصور بـP23 |
| `targeted-archive-midterm.yml` | ZIP/RAR المجمدان P24/P52 | اكتمل run `38015912512` |
| `targeted-final-ingest.yml` | P62 `UploadFile` فقط | إثبات تاريخي |
| `targeted-final-json-ingest.yml` | P32/P42 `/ingest` بصيغة JSON الصحيحة فقط | اكتمل run `38016947468` |
| `targeted-final-refresh.yml` | P59 `/refresh-mv` فقط | إثبات تاريخي |
| `static-final-api-p24.yml` | قراءة الشيفرة المجمدة لـP24 لتشخيص اكتشاف FastAPI | لا ينفذ طالبًا |
| `regression-*` و`pilot.yml` | تجارب Regression/طليعة تاريخية | لا تفعّلها بلا فحص نطاقها |

**ملاحظة:** بعض الـworkflows تستخدم `push` على ملفات `.grader/trigger-*.txt` بدل زر تشغيل. **لا تغيّر trigger عشوائيًا لمجرد «الفحص»**؛ فالكتابة فيه قد تطلق اختبار طالب وتستهلك موارد أو تكرر أحكامه. ثبّت أولًا `project_id` و`phase` و`failed keys` و`expected artifact`.

---

## 14. أخطاء المصحح التي اكتشفناها وأصلحناها ولماذا

| المشكلة الجذرية | العلاج/مكان الكود | دليل أو مشاريع مثال |
|---|---|---|
| مقارنة Stability/Upsert بعدد Teacher absolute، بما يكرر معاقبة عيب Batch | `count_policy.py` و`evidence_regrade.py`: مقارنة Before/After وفرق Inserts، و`0→0` غير حاسم | أحكام Idempotency/Incremental القديمة |
| المصحح لم يرسل stdin إلى CLI تفاعلي | `interactive_detection.py` وأمر ingestion stdin موثق؛ منع اختيار قائمة حذف | P46 وP49: بعد الإصلاح قرآ البيانات |
| الثقة المنخفضة عطلت مشروعًا يُمكن تشغيله | إعادة مستهدفة تحت بوابة مراجعة، لا خصم على عدم الفهم | P08؛ أعاد 25 PASS و7 FAIL و3 INCONCLUSIVE |
| CLI افتراضي في ذاكرة بدلاً من Mongo حقيقي | `discovery.py` يختار `--backend mongo` **فقط إذا وثقه README وargparse** | P23؛ أصبح له اختبار فعلي |
| Maven معزول عن الشبكة | `sandbox.py`: prewarm لإحداثيات الطالب، ثم Ivy offline local resolver؛ عدم تغيير كود الطالب | P05 وP22 ومشاريع أخرى |
| بعض إصدارات Connector/Spark/Scala غير متوافقة من مصدر الطالب | `spark_dependency_audit.py`، مصدر الطالب وتقرير الاعتماديات | لا تحوّل كل مشكلة Maven إلى مسؤولية المعلم |
| ملف كبير يستعمل Dynamic Spark probe | `spark_probe.py` و`targeted_spark_only.py`، استعمال نفس المدخل الأصلي | P26 |
| المصحح أرسل Threshold كنص `20.0` بينما CLI يستعمل `int()` | `_format_threshold_env` في `sandbox_runtime.py` وإعادة Spark للمتأثرين فقط | P09/P19/P55/P64 ونحوها |
| مشروع داخل Nested directory | استخدم root الأصلي من خطة التجميد، لا تفترض root المستودع | P60 |
| Log يقول `python_batch` لكن التفسير النصي يذكر Spark | `runtime_evidence.py` يقرأ token المحرك الصحيح أولاً | فئة P23 Router |
| Spark أنهى المعالجة ثم ظل خادم FastAPI يعمل حتى timeout | راجع marker نجاح المعالجة وMongo snapshots؛ لا تحسب Timeout خادم ويب فشل PySpark تلقائيًا | P09 |
| Mongo Connector يعمل لكن كل الصفوف ذهبت Quarantine | فصل نجاح `spark_pipeline.command` عن فشل `spark.validated_count` و`quarantine_count` | P48؛ فشل تنظيف حقيقي |
| فشل `POST /ingest` لأن المصحح أرسل path بدلاً من محتوى UploadFile | `final_runtime.py` و`targeted_final_ingest.py`: multipart CSV حقيقي | P62: HTTP 200 وأثر MongoDB |
| فشل `/ingest` لعدم إرسال JSON field المطلوب من عقد الطالب | `targeted_final_json_ingest.py`: path JSON صحيح وأثر Mongo | P32/P42: run `38016947468` أثبت 2xx وإدخالًا |
| فشل `/refresh-mv` لأن المصحح لم يرسل `name` الإلزامي | `final_runtime.py` و`targeted_final_refresh.py`: معلمة مُثبتة من مصدر الطالب | P59: refresh وincremental HTTP 200 |
| انتهى زمن HTTP دون status لكن المصحح أصدر FAIL | `final_runtime.py`: النقل غير المكتمل `INCONCLUSIVE` بدل فشل طالب | P50 ingest، P54 MV transport class |
| طلاب رفعوا ZIP/RAR فتجاهل المصحح شيفرتهم | `safe_archive_submission.py` واستخراج آمن في workspace منفصل | P24/P52 في run `38015912512` |
| اختلاف بنية مستودع أو نقص فعلي في Final | `frozen_api_source_audit.py` وقراءة Frozen source؛ لا تعتمد على HEAD الأحدث | بعض مشاريع Final missing FastAPI |

### أمثلة نتائج تم إثباتها بعد الإصلاح

- [P05 Spark offline resolver](https://github.com/Prideidea/bigdata-grader/actions/runs/38003977105): 100,000 Raw وValidated، اختبار المحرك نجح. كان مانع Ivy من المصحح.
- [Spark cohort recovery](https://github.com/Prideidea/bigdata-grader/actions/runs/38004329576): أنجز عدة مراحل Spark منتقاة؛ **راجع كل artifact منفردًا**، لا تجعل نجاح run إذنًا بترقية الجميع.
- [P59 MV](https://github.com/Prideidea/bigdata-grader/actions/runs/38000458514): `/refresh-mv` + incremental نجحا بعد إرسال المعامل الصحيح.
- [P62 ingestion](https://github.com/Prideidea/bigdata-grader/actions/runs/37986423624): HTTP 200، 20,000 Raw و17,000 Validated؛ إثبات طلب multipart الصحيح.
- [P32/P42 JSON ingestion](https://github.com/Prideidea/bigdata-grader/actions/runs/38016947468): `/ingest` 2xx مع أثر DB، **ولا يلغي فحص جودة التنظيف بصورة مستقلة**.
- [P24/P52 archive recovery](https://github.com/Prideidea/bigdata-grader/actions/runs/38015912512): بعد استخراج المصدر المجمد بأمان، **P24 = 25 PASS/7 FAIL/3 INCONCLUSIVE**، و**P52 = 26 PASS/6 FAIL/3 INCONCLUSIVE**. كانت اختبارات النصفي عندهما غير منفذة قبل الإصلاح.
- [Frozen P24 Final source audit](https://github.com/Prideidea/bigdata-grader/actions/runs/38016811474): مراجعة مصدر Final ثابتة دون تشغيل الطالب.

---

## 15. كيف نصنف المسؤولية؟ (هذه أهم قاعدة أكاديمية)

### أكواد التصنيف الرسمية في العمل

| الرمز | معناه | ماذا تفعل؟ |
|---|---|---|
| `STUDENT_CODE_FAILURE` | SyntaxError/منطق خوارزمية مثبت | وثِّق السطر والنتيجة، لا تعد بلا إصلاح مُجاز |
| `STUDENT_DEPENDENCY_FAILURE` | مكتبة مستوردة وغير معلنة في متطلبات التسليم | راجع جميع manifest وREADME قبل الحكم |
| `STUDENT_CONFIGURATION_FAILURE` | path/import/config خاطئ في نسخة الطالب | تحقق أن أمر التشغيل المختار صحيح |
| `GRADER_DISCOVERY_FAILURE` | اختار المصحح CLI/working dir/stdin خاطئًا | أصلح الاكتشاف ثم أعد الاختبار الذي لم ينفذ فقط |
| `GRADER_PROBE_FAILURE` | طلب HTTP/CSV/JSON/threshold غلط من المصحح | أصلح العقد وأعد probe المعني فقط |
| `GRADER_FIXTURE_FAILURE` | ملف/حزمة/بيانات اختبار معيبة أو غير مركّبة | أصلح Fixture مع ثبات oracle والعدالة |
| `GRADER_INFRA_FAILURE` | Docker/Mongo/Maven/Runner/Network خاص بالمصحح | لا خصم، عالج البيئة ثم اختبر المتأثر |
| `PRECONDITION_NOT_SATISFIED` | خطوة أولية لازمة لم تنجح أو لم تنفذ | لا تصدر FAIL لاختبار تابع على بيانات مفقودة |
| `INCONCLUSIVE` | لا تكفي الأدلة للقرار | احتفظ بمبرر قابل للفحص وخطوة حسم واضحة |

قد تظهر حالات مكملة مثل `STUDENT_PORTABILITY_FAILURE` و`TIMEOUT` و`STUDENT_CODE_OR_CONFIGURATION_FAILURE`. لا تخلط رمز سبب التنفيذ مع حكم اختبار الأعمال `PASS/FAIL`.

### قواعد التعامل مع أمثلة متكررة

- `ModuleNotFoundError: psutil/tqdm`: افحص manifests؛ إذا غير معلنة فهذا نقص اعتماديات طالب. لا تثبت المكتبة سرًا ثم تمنح PASS تلقائيًا.
- `SyntaxError` أو import ثابت في كود الطالب: يمكن إثباته من المصدر والسجل؛ لا تنتظر إعادة كاملة.
- `mongodb.DefaultSource`/Maven offline: افحص الإحداثيات المعلنة، توافق Spark/Scala، وجود JAR، وإمكانية تهيئة البيئة؛ **لا تفترض خطأ طالب لمجرد عدم وجود JAR في requirements.txt**، لأن Maven packages قد تُذكر في إعدادات PySpark بدلاً منه.
- `java.exe/python.exe` على Linux: قد يكون رمز قابلية النقل أو مسار تشغيل خاطئًا؛ يعتمد استحقاق الخصم على تكليف المقرر، فلا تحوله تلقائيًا إلى صفر شامل.
- `422` API: هل أرسل المصحح الـfield المطلوب فعلًا؟ افحص `openapi.json` وcommand/body_keys.
- `HTTP 500` بعد الطلب الصحيح مع traceback طالب: مرشح لفشل طالب محدد، لا تلغِه لتجميل الدرجة.
- `timeout` HTTP دون status: `INCONCLUSIVE` لا `FAIL`. مهلة خادم بقي يعمل بعد pipeline مكتمل تختلف عن timeout قبل إتمام المعالجة.
- `0 Validated و0 Quarantine`: لا تعتبر الاستقرار أو غياب duplicates نجاحًا لدالة لم تعالج السجلات.
- اختلاف baseline: افصل عطل Batch الأساسي عن Upsert deltas وابحث عن بيانات حقيقية.

---

## 16. الحالة المرجعية الحالية للدفعة — لا تخلط الإصدارات

**أرقام الدفعة الـ68 تاريخية ومتغيرة بالـoverlays؛ لا يوجد في GitHub حتى الآن كشف درجات أكاديمي معتمد لكل طالب.**

كان **آخر كشف تراكمي صرّحنا به قبل إضافات P24/P52 وP32/P42**: `PASS=2245`، `FAIL=411`، `INCONCLUSIVE=895`، بإجمالي `3551` حكمًا، بعد P09/P23 ومراحل Spark. هذه الأرقام **لقطة تقنية وقتية وليست نتيجة اليوم النهائية**.

**نتائج أحدث يجب إدماجها في الكشف الموحّد من الأدلة نفسها:**

1. P24: `25/7/3` على الترتيب `PASS/FAIL/INCONCLUSIVE` — نصفي بعد فك RAR.
2. P52: `26/6/3` — نصفي بعد فك ZIP.
3. P32: `final.api.ingest` أثبت `PASS` في probe المستهدف فقط، مع محتوى خط المعالجة الذي يحتاج مقارنة Oracle مستقلة.
4. P42: `final.api.ingest` أثبت `PASS` في probe المستهدف فقط، مع تحقق أثر Mongo مستقل عن جودة كل سجل.
5. بعض أحكام Final التي فشلت بسبب Timeout بدون HTTP status تحتاج **تصحيح مسؤولية من الأدلة**، لا منح PASS.
6. أعداد الأحكام قد تزيد حين يُختبر مشروع كان غير منفذ سابقًا (كما حصل في P23 وP24 وP52)؛ هذه زيادة معلومات وليست تدهورًا في مستوى الطلاب.
7. لا تجمع نتائج run مختلفة عدًّا بلا المفتاح `(project, phase, key, frozen SHA)`؛ وإلا عدّدت الحكم مرتين.

**المطلوب أولًا من المستلم:** إنتاج ملف **Master Adjudication Ledger** واحد من baseline + جميع narrow-run overlays، مع invariants: كل PASS سابق محفوظ، لا duplicate key، كل changed verdict له دليل، مجموع Counts = عدد المفاتيح الفريدة في كشف كل مشروع، و`INCONCLUSIVE` لا يصير FAIL تلقائيًا.

---

## 17. القضايا المتبقية التي ينبغي إغلاقها فعليًا

1. **توحيد الأحكام الحديثة:** دمج P24/P52/P32/P42 ونتائج Spark/Final الأخرى في دفتر واحد، والتمييز بين إثبات تشغيل الأمر وإثبات صحة البيانات. لا تعيد تشغيلهم لأجل جمع ملف.
2. **الأخطاء ذات السبب المشترك:** راجع أحكام Batch cleaning وUpsert/Delta التي ثبت أنها تبعية baseline أو Fixture، ثم احسمها من عينات وسجلات محفوظة. لا تخفف فحص بيانات الأعمال اعتباطًا.
3. **مشاريع حُجبت قبل التنفيذ:** قرر لكل مشروع ما إذا كان نقص ملفات الطالب، ZIP/RAR، README غير واضح، أو خلل اكتشاف قابل للإصلاح. إذا أصلحت grader discovery، اختبر المشروع الذي **لم تكن لديه PASS في النطاق المتأثر** فقط.
4. **عزل/تهيئة MongoDB:** افحص مشاريع مثل P34 حيث بدأت مرحلة Upsert ببيانات غير متوقعة. إذا ثبت أن DB reset لم يحدث، اعتبر الاختبار غير صالح وأعد مرحلته فقط.
5. **توافق Spark:** فصل قيود الشبكة عن تعارض Spark/Scala/Connector من الطالب؛ لا تعد المشاريع ذات تعارض صريح كما لو كانت محجوبة بمشكلة المصحح.
6. **Final API الأوامر ومعلماتها:** استخدم source-grounded contracts؛ بعض مشاريع النهائي لا تحتوي FastAPI أصلًا في اللقطة المجمدة، وبعضها يستخدم UploadFile/JSON paths.
7. **Gemini 429:** حصص النموذج مجانية ومحدودة؛ اعتمد الأدلة الثابتة والتخزين المؤقت، واستدعِ النموذج فقط عند غموض حقيقي، ولا تكرر طلبات دون داع.
8. **Rubric النصفي:** الحصول على النسخة الرسمية التي سُلمت للطلاب، مقارنة متطلبات Track A/B وتوزيع الـ18، اعتمادها، ثم تفعيلها **بمراجعة أكاديمية صريحة**.
9. **المناقشة النهائية:** إدخال 0.25/7 يدويًا مع سجل واضح؛ لا تعوض غياب المناقشة بأصفار صامتة.
10. **الدرجات والتوثيق:** لكل مشروع تقرير مرتب: معايير نجح فيها، أخطاء طالب مثبتة، أخطاء مصحح أصلحت، أسباب غير حاسمة، أدلة RUN/SHA، نقاط آلية مؤكدة، نقاط مراجعة، ونقاط مناقشة. لا تنشر كشفًا نهائيًا قبل تحقق الجودة.

### جدول الأولويات — ما الذي تنجزه دون تحليل جديد طويل؟

| أولوية | عمل محدد | شرط الإغلاق |
|---|---|---|
| P0 | دمج آخر artifacts في دفتر واحد | 68 مشروعًا، كل Test Key فريد، وسجل من أين جاءت آخر نتيجة |
| P0 | مطابقة جميع FAIL مع سجل دليل صالح/مقدمة اختبار | كل خصم سببه طالب مثبت أو أعيد تصنيفه غير حاسم |
| P1 | معالجة أخطاء مصحح مشتركة لا تزال قائمة | Regression أخضر + retest واحد/فئة + إعادة منتقاة فقط |
| P1 | توثيق أخطاء الطالب التي لا تحتاج rerun | سطر/traceback أو snapshot أصل + وصف سهل للطلاب |
| P1 | اعتماد Rubric النصفي | مراجعة المدرس وتوقيع النسخة ثم تفعيل scoring |
| P2 | إكمال 0.25 مناقشة Final | إدخال بشري بأدلة |
| P2 | إخراج كشف درجات نهائي + سجل اعتراضات | درجات قابلة للتدقيق ونسخة لا تمحى من المدخلات والأدلة |

---

## 18. منهج تصحيح تراكمي يوقف دوامة «نصلح مشروعًا فنكسر آخر»

### سجل تبديل واحد لا يمحو الأصل

لكل إصلاح جديد اكتب:

```json
{
  "bug_id": "GRADER-MV-QUERY-REQUIRED",
  "root_cause": "grader called POST /refresh-mv without required name",
  "affected_projects": ["P59"],
  "affected_keys": ["final.mv.refresh", "final.mv.incremental"],
  "grader_files": ["grader/final_runtime.py"],
  "regression_tests": ["tests/test_final_refresh_contract.py"],
  "ci_run": "number-of-green-CI",
  "proof_run": 38000458514,
  "old_values_preserved": true,
  "pass_tests_reexecuted": 0,
  "status": "verified"
}
```

### اتخاذ القرار

```text
هل هناك FAIL/INCONCLUSIVE؟
        |
        v
هل أصل الأمر نفّذ في ظروف صحيحة؟
   | لا                     | نعم
   v                        v
GRADER/PRECONDITION       افحص Mongo/HTTP/traceback
   |                        |
اعزل الاختبارات التابعة       هل السبب طالب مثبت؟
   |                       | نعم      | لا
أصلح السبب العام              وثّق      راجع العقد/البيئة
   |
هل snapshot القديمة كافية؟
   | نعم               | لا
Evidence overlay      narrow retest للمرحلة فقط
   |                        |
   +------------+-----------+
                v
       merge by frozen SHA + test key
                |
         PASS قديم محفوظ دائمًا
                |
         مراجعة Rubric واعتماد بشري
```

### آلية العمل العملية

1. افحص مجموعة الأسباب المشتركة في جميع المشاريع، لا تعتمد على P05 وحده.
2. اكتب minimal bug reproducer مستقل عن طلاب الدفعة.
3. أضف اختبار Regression يُظهر الخطأ القديم ويضمن سلوك الإصلاح.
4. شغّل CI واعرف SHA للإصلاح.
5. إذا يكفي إعادة قراءة Evidence، لا تشغل أي طالب.
6. إذا تحتاج تنفيذًا، اختر **فقط** المشاريع التي لديها `FAIL/INCONCLUSIVE` في المفاتيح المتأثرة، مع نفس frozen source.
7. تحقق من Artifact لكل مشروع وMongo Snapshots؛ الترقية إلى PASS مشروطة بأثر فعلي، ولا تُحوّل باقي اختبارات المشروع إلى PASS تلقائيًا.
8. أدخل overlay محكومًا وراجع Counts بعده؛ لا تحذف PASS قديم.
9. Freeze قرار هذا bug كـ`resolved`؛ لا تفتحه بسبب مشروع جديد غير مشابه دون دليل مختلف.
10. انتقل إلى فئة الجذر التالية.

---

## 19. كيف نميز بين إنهاء التقنية وإنهاء الدرجات؟

**الإغلاق التقني** يتحقق عندما يكون لكل `FAIL` أو `INCONCLUSIVE` سبب موثق يمكن إرجاعه إلى:
(أ) إخفاق طالب قابل للخصم وفق المطلوب، أو
(ب) مانع مصحح أصلح وحُسم/رُفع للمراجعة، أو
(ج) عدم كفاية أدلة لسبب محدد مع قرار أكاديمي واعٍ.
ليس مطلوبًا أن تصبح كل الاختبارات خضراء.

**الإغلاق الأكاديمي** يحتاج فوقه:
- Rubric النصفي المعتمد بدل `DRAFT_DISABLED`؛
- نقاط النهائي وفق الفئات المعتمدة؛
- تقدير المناقشة اليدوية `0.25`؛
- عدم خصم `INCONCLUSIVE` آليًا؛
- توثيق أسباب خصم كل طالب وربطها بمخرجات التعلم؛
- قبول مراجعة/اعتراض واعتماد الأستاذ المسؤول.

لا تكتب في تقرير «التصحيح انتهى بالكامل» إذا كانت هذه الشروط غير متحققة، حتى لو انتهت 68 Jobs باللون الأخضر.

---

## 20. حماية وأمان وخصوصية البيانات

- المستودع يحتوي أسماء/أرقام طلاب في CSV؛ يجب أن يبقى الوصول مقصورًا على المخولين.
- ملفات الـteacher oracle و`GRADER_HIDDEN_SEED` سرية، و`GEMINI_API_KEY` و`STUDENT_REPOS_TOKEN` لا تدخل logs أو snippets أو تقارير الطالب.
- مستودعات الطلاب **غير موثوقة**: ممنوع تشغيلهم على host بشكل مباشر، أو نسخ أوامر من README دون فحص.
- Sandbox يستخدم حد CPU/RAM/PIDs و`cap-drop ALL` و`no-new-privileges` وشبكة معزولة وMongo مستقلة.
- استخراج الأرشيفات يخضع لمنع `../`/symlink والحدود على الأحجام وعدد الملفات، ولا يجوز استخراج RAR/ZIP بأمر عشوائي على host غير معزول.
- LLM لا يُنفّذ أوامر من README، ولا يُسمح لـPrompt Injection بتعديل سياسة التقييم.
- احفظ evidence كاملة للمدرس فقط؛ عند إعطاء الطالب Feedback يكفي شرح الخطأ وشواهده ولا ترسل Teacher Key أو بيانات طلاب آخرين.
- Docker عزل مفيد لكنه ليس VM محصنة كاملة؛ يفضل Runner مؤقت لا يحتوي أسرار إنتاج.

---

## 21. مشاكل شائعة وكيف نتحقق منها خلال دقائق

| العرض | أول مكان تبحث فيه | القرار |
|---|---|---|
| GitHub Action أخضر والطالب `FAIL` | `reports/Pxx/result.json → runtime.assertions` | لا تناقض: Job انتهى؛ اقرأ اختبار الطالب |
| مشروع مستودعه يحوي ZIP/RAR فقط | Freeze archive + `safe_archive_submission.py` | استخراج آمن أو عائق تسليم موثق |
| Gemini `429` | `repository_analysis` و`agent_analyzer.py` | cache/Heuristic، لا خصم ولا تكرار طلبات |
| Batch خزن بيانات في DB غير المتوقعة | `execution_plan.database_name` و`mongo_checker.locate_active_database` | تأكد عدم التباس أكثر من DB |
| Spark `unresolved dependencies` | `spark_dependency_audit.py` والإحداثيات وIvy cache | فصل Maven grader عن تعارض الطالب |
| Spark اختار `python_batch` | stdout + metadata و`runtime_evidence.detect_engine` | إن كان الملف صغيرًا أو العتبة مختلفة، افحص عقد router |
| Upsert baseline رقم مختلف لكن ثابت | snapshots قبل/بعد و`compare_baseline_replay` | لا تكرر خصم Batch baseline |
| `0→0` بعد rerun | `count_policy.compare_stability` | غير حاسم دون إثبات معالجة بيانات |
| `/ingest` أعاد 422 | OpenAPI `requestBody`/`parameters` وما أرسله المصحح | قد يكون Probe فاسدًا |
| `/ingest` 200 وMongo فارغة | `final.api.ingest` host-side DB counts | HTTP وحده لا يساوي PASS |
| `/refresh-mv` أعاد 422 | هل معلمة name/mode مطلوبة؟ | أصلح عقد الطلب، لا تخصم |
| `/refresh-mv` لم يعط status بسبب Timeout | `_refresh_transport_unproved` | INCONCLUSIVE |
| Final لا يجد FastAPI | Frozen source audit وREADME | لا تختزل الغياب إلى عيب اكتشاف دون فحص |
| تغيير اختبار Pxx غيّر PASS قديمًا | مقارنة Keys SHA وأصل Artifacts | ارفض merge وأعد إصلاح التراكبية |
| مشكلة Pxx فريدة | سجل السبب والمقدمة | لا تغير القانون العام بسببه |

---

## 22. قائمة تحقق نهائية لتسليم العمل للمصحح الجديد

- [ ] قرأت هذا الملف والكود والـRubrics والـCI.
- [ ] عرفت freeze run `37390623044` وbaseline `37874152827`؛ لم أستبدلهما.
- [ ] نزّلت كل Artifacts المرجعية والتكميلية الموثقة واحتفظت برقم run/SHA.
- [ ] بنيت دفترًا واحدًا للأحكام بمفتاح فريد `project_id/phase/test_key/frozen_sha`.
- [ ] لا يوجد PASS قديم مفقود أو اختبار ناجح أعيد بلا مبرر.
- [ ] كل FAIL مرتبط بمقدمة صحيحة وبفشل طالب مثبت أو أعيد تصنيفه.
- [ ] كل INCONCLUSIVE له سبب جذري وإجراء واحد قابل للحسم، وليس «غامض» فقط.
- [ ] تشغيل CI أخضر على إصدار المصحح النهائي المستخدم لتفسير الأحكام.
- [ ] لا توجد سلسلة إصلاحات per-repo تكسر سياسة التقييم العامة.
- [ ] Rubric النصفي الرسمي معتمد ومفعل **بإذن أكاديمي**.
- [ ] Rubric النهائي و0.25 مناقشة مكتملان.
- [ ] نسخة غير قابلة للمحو من تقرير كل مشروع ونقاطه وأدلته محفوظة.
- [ ] المخرجات النهائية موثقة وقابلة للمراجعة والاعتراض.

---

## 23. الروابط المرجعية السريعة

- [GitHub repository](https://github.com/Prideidea/bigdata-grader)
- [README](https://github.com/Prideidea/bigdata-grader/blob/main/README.md)
- [Architecture](https://github.com/Prideidea/bigdata-grader/blob/main/ARCHITECTURE.md)
- [Grader policy](https://github.com/Prideidea/bigdata-grader/blob/main/grader-policy.yaml)
- [Midterm draft rubric](https://github.com/Prideidea/bigdata-grader/blob/main/rubrics/midterm_18.json)
- [Final active rubric](https://github.com/Prideidea/bigdata-grader/blob/main/rubrics/final_7.json)
- [Freeze #37390623044](https://github.com/Prideidea/bigdata-grader/actions/runs/37390623044)
- [Original unified grading #37874152827](https://github.com/Prideidea/bigdata-grader/actions/runs/37874152827)
- [P05 Spark verified #38003977105](https://github.com/Prideidea/bigdata-grader/actions/runs/38003977105)
- [Spark cohort #38004329576](https://github.com/Prideidea/bigdata-grader/actions/runs/38004329576)
- [P59 MV verified #38000458514](https://github.com/Prideidea/bigdata-grader/actions/runs/38000458514)
- [P62 Ingest verified #37986423624](https://github.com/Prideidea/bigdata-grader/actions/runs/37986423624)
- [P24/P52 archive recovery #38015912512](https://github.com/Prideidea/bigdata-grader/actions/runs/38015912512)
- [P32/P42 Final ingest proof #38016947468](https://github.com/Prideidea/bigdata-grader/actions/runs/38016947468)
- [Latest reviewed CI before handover #38017078562](https://github.com/Prideidea/bigdata-grader/actions/runs/38017078562)

---

## 24. توصية البدء الفعلية للمستلم (لا تبدأ دورة تحليل جديدة)

**ابدأ من دمج الأدلة، لا من إعادة تشغيل الطلاب.** اسحب الأصل الـ68، ثم overlays وArtifacts المستهدفة، واصنع كشفًا حاسمًا لكل Test Key. بعد ذلك اجمع ما تبقى من مشكلات المصحح **حسب أصل واحد**، وتحقق منها باختبار Regression وعينة ثم إعادة انتقائية، لا تعيد الفصول والمشاريع كلها. اعزل نقاط الخصم الحقيقية عن أعطال الاختبار. عندما يصبح لكل خصم دليل، اطلب اعتماد Rubric النصفي والمناقشة، ثم أنشئ كشف الدرجات النهائي.

**رسالة لأي مهندس أو وكيل برمجي يحل محل السابق:** المطلوب ليس أن تجعل 68 مشروعًا ناجحة، ولا أن تختفي كلمة FAIL، بل أن تجعل **كل حكم عادلاً ومبررًا وقابلاً لإعادة التحقق، وأن يستلم الأستاذ كشفًا نهائيًا صحيحًا دون فقدان نجاح طالب واحد**.

**انتهى مرجع التسليم.**
