# Big Data Grader V4

نظام تصحيح مركزي لمشاريع **Big Data – Midterm/Final**، مبني على أربعة مبادئ:

1. **AI-assisted repository understanding** لفهم طريقة تشغيل كل مشروع حتى لو اختلفت البنية.
2. **Behavior-first grading**: الدرجة لا تعتمد على وجود ملف أو كلمة في الكود، بل على تشغيل المشروع وقياس النتيجة الفعلية.
3. **Per-project Docker sandbox**: كود الطالب لا يعمل مباشرة على جهاز المصحح.
4. **Teacher oracle stays outside the student container**: الطالب يحصل على ملفات الإدخال فقط، ولا يرى الإجابات المتوقعة.

## Architecture

```text
GitHub Repository
      │
      ▼
Freeze Commit SHA
      │
      ▼
workspaces/<PROJECT>/repo
      │
      ├───────────────┐
      ▼               ▼
Heuristic Scanner   LLM Repository Analyst
      │               │
      └──────┬────────┘
             ▼
       Execution Plan
             │
             ▼
      Confidence Gate
      │             │
   HIGH           LOW
      │             └──> MANUAL_REVIEW (no penalty, no execution by default)
      ▼
Per-project Docker Sandbox
      │
      ├── Student code/image
      ├── Student Python dependencies
      ├── Java + PySpark runtime
      ├── CPU/RAM/PID/time limits
      ├── Dedicated Docker network
      └── Dedicated MongoDB container
             │
             ▼
      Hidden input datasets (read only)
             │
             ▼
       Runtime execution
             │
             ▼
   MongoDB direct verification
             │
             ├── counts
             ├── duplicates
             ├── indexes
             ├── schema validator
             └── state after rerun
             │
             ▼
        Expected vs Actual
             │
             ▼
        Evidence report
```

## أين تنزل المشاريع؟

كل مشروع في مسار منفصل:

```text
workspaces/
  P01/repo/
  P02/repo/
  P03/repo/
```

ولا يتم دمج كود الطلاب داخل Codebase المصحح.

## أين تثبت متطلبات الطالب؟

لا تُثبت على Python الخاص بالمصحح. يتم بناء Image خاصة بالمشروع:

```text
bigdata-grader/student-runtime:4.0
        ↓
student project image
        ↓
pip install -r requirements.txt
```

وإذا لا يوجد `requirements.txt` يدعم النظام `pyproject.toml` أو `setup.py`.

## MongoDB

لكل مشروع MongoDB Container مستقلة. هذا يسمح حتى للمشاريع التي hard-code اسم قاعدة البيانات أن تعمل بدون أن تتداخل مع مشروع طالب آخر.

كما يوجد `socat` داخل Student Container لعمل proxy من:

```text
localhost:27017 → mongo:27017
```

لذلك المشاريع التي كتبت:

```python
MongoClient("mongodb://localhost:27017")
```

تظل قابلة للاختبار داخل Sandbox.

## AI Repository Analyst

الـAI لا يعطي الدرجة. مهمته فقط فهم المشروع وتحويله إلى `ExecutionPlan`.

يقرأ ملفات منتقاة مثل:

- `README.md`
- `requirements.txt` / `pyproject.toml`
- `main.py`, `cli.py`, `run.py`
- `config/settings.py`
- Mongo/Spark/Batch/ELT loaders

ثم يرجع مثلًا:

```json
{
  "entrypoint": "src/main.py",
  "ingest_command": "python src/main.py --input {file} --db-name {db_name}",
  "database": "midterm_ecommerce",
  "collections": {
    "raw": "orders_raw",
    "validated": "orders_validated",
    "quarantine": "orders_quarantine"
  },
  "business_key": "order_id",
  "confidence": 0.96,
  "evidence": [
    "src/main.py: --input is defined with argparse",
    "config/settings.py: MONGO_DB_NAME is configurable"
  ]
}
```

### حماية من Prompt Injection

Repository الطالب تعامل كـ **Untrusted data**. Prompt النظام يمنع تنفيذ التعليمات الموجودة في README أو comments، والـExecutionPlan يمر بعد ذلك على Validator يمنع أوامر shell الخطرة مثل:

```text
&&  ||  ;  |  >  <  `  $(...)
```

ولا يسمح افتراضيًا إلا بأنماط تشغيل Python/Spark المعروفة.

## Confidence Gate

الافتراضي:

```text
confidence >= 0.80 → يسمح بالتشغيل
confidence < 0.80  → MANUAL_REVIEW_REQUIRED
```

ولا يخصم من الطالب بسبب أن الوكيل لم يفهم مشروعه.

## Sandbox Security

الوضع الافتراضي:

- `network_profile = isolated`
- `--cap-drop ALL`
- `no-new-privileges`
- CPU = 2 cores
- RAM = 6 GB
- PID limit = 512
- Timeout = 20 min
- `/tmp` محدود
- Student code لا يعمل على Host
- Teacher oracle لا يركب داخل Student Container

### وضع Compat

بعض مشاريع Spark تستخدم `spark.jars.packages` وتحتاج تنزيل Maven artifacts وقت التشغيل. الوضع الآمن `isolated` قد يمنع ذلك.

في هذه الحالات شغّل مشروعًا محددًا بـ:

```bash
python evaluate.py --project P01 --runtime --network-profile compat
```

هذا يعطي المشروع اتصال شبكة أثناء التشغيل، لذلك يستخدم فقط للحالات التي تحتاجه وبعد مراجعة المشروع. لا تجعل `compat` هو الافتراضي لكل الطلاب.

## الإعداد لأول مرة

### Windows PowerShell

```powershell
.\setup.ps1
```

### Linux

```bash
./setup.sh
```

هذا يقوم بـ:

1. إنشاء `.grader-system-venv` للمصحح.
2. تثبيت متطلبات المصحح.
3. بناء `bigdata-grader/student-runtime:4.0`.

ثم عرّف مفتاح مزود الـLLM:

```powershell
$env:OPENAI_API_KEY="..."
$env:GRADER_LLM_MODEL="gpt-5.6"
```

أو Linux:

```bash
export OPENAI_API_KEY="..."
export GRADER_LLM_MODEL="gpt-5.6"
```

يمكن تغيير `GRADER_OPENAI_BASE_URL` لاستخدام مزود OpenAI-compatible أو Gateway داخلي.

## فحص البيئة

```bash
python doctor.py
```

يجب خصوصًا أن تكون:

```text
Docker        OK
Git           OK
Hidden tests  OK
Runtime image OK
OPENAI_API_KEY configured
```

## تجميد المشاريع وقت التسليم

```bash
python freeze_submissions.py
```

ينتج:

```text
frozen_submissions.csv
```

وفيه Commit SHA لكل مشروع. التقييم بعد ذلك يكون على الـSHA المجمد، وليس `main` المتغير.

## تحليل مشروع بدون تشغيله

```bash
python evaluate.py --project P01
```

ينتج Execution Plan + confidence + static evidence فقط.

## تشغيل الاختبارات الفعلية

```bash
python evaluate.py --project P01 --runtime
```

إذا Confidence منخفضة لن يشغل المشروع ويعطي:

```text
MANUAL_REVIEW_REQUIRED
```

لتجاوز ذلك يدويًا فقط:

```bash
python evaluate.py --project P01 --runtime --allow-low-confidence
```

## تقييم جميع المشاريع

```bash
python evaluate_all.py \
  --submissions frozen_submissions.csv \
  --runtime \
  --continue-on-error
```

المشاريع تُشغل **Sequentially** افتراضيًا حتى لا يتعارض Spark/RAM/CPU. بعد استقرار البيئة يمكن إضافة Worker Pool محدود لاحقًا.

## الاختبارات السلوكية الموجودة

V4 يشغل حاليًا بصورة فعلية:

### Test 01 — Batch Pipeline

- تشغيل ملف hidden صغير.
- فحص `orders_raw`.
- فحص `orders_validated`.
- فحص `orders_quarantine`.
- فحص duplicate business keys.

### Test 02 — Spark Pipeline

- تشغيل hidden large dataset.
- فحص النتيجة من MongoDB.
- لا يعتمد على وجود ملف اسمه `spark_loader.py` لإعطاء النجاح.

### Test 03 — Upsert + Idempotency

```text
Baseline
  ↓
New + Updated + Unchanged + Invalid
  ↓
Verify database state
  ↓
Run same delta again
  ↓
Validated must remain stable
  ↓
Duplicates = 0
```

### Test 04 — Incremental / Plan B

اختياري:

```bash
python evaluate.py --project P01 --runtime --plan-b
```

## التقارير

```text
reports/P01/
  result.json
  evaluation.md
```

كل assertion يعرض:

```text
expected
actual
PASS / FAIL / INCONCLUSIVE
```

والـStatic checks تظهر في نهاية التقرير كأدلة مساعدة فقط، ولا تعتبر نجاحًا وظيفيًا بمفردها.

## حالات لا يجب خصم الدرجة فيها آليًا

النظام يوقف/يرفع للمراجعة اليدوية بدل الخصم عند:

- فشل فهم طريقة التشغيل بثقة كافية.
- تعطل Docker أو MongoDB لدى المصحح.
- عدم توفر Maven artifact بسبب Network policy.
- فشل بنية Sandbox نفسها.
- عدم قدرة الوكيل على تحديد Business Key أو DB بصورة موثوقة.

الفشل الوظيفي للطالب يجب أن يكون ناتجًا عن **اختبار يمكن إعادة إنتاجه مع Evidence**.

## ملفات مهمة

```text
grader/agent_analyzer.py    فهم المستودع بالـLLM
grader/plan_resolution.py   دمج Heuristic + AI + confidence gate
grader/sandbox.py           عزل Docker/Mongo/resources
grader/sandbox_runtime.py   الاختبارات الفعلية داخل Sandbox
grader/oracle.py            النتائج المتوقعة عند الأستاذ
grader/static_checks.py     أدلة ثابتة فقط
evaluate.py                 تقييم مشروع واحد
evaluate_all.py             تقييم كل المشاريع
freeze_submissions.py        تثبيت commit SHA
runtime-image/Dockerfile     بيئة تشغيل الطلاب
grader-policy.yaml           قواعد العدالة والأمان
```

## حدود V4 الحالية

هذه نسخة تشغيلية قوية، لكن توجد حالات يجب أن تظل `MANUAL_REVIEW` وليس أن نخمن نتيجتها:

- مشروع يحتاج خدمة خارجية غير Mongo/Spark.
- مشروع يعتمد على ملفات سرية/محلية لم يرفعها الطالب ولم تكن جزءًا من متطلبات المقرر.
- مشروع Spark يحتاج Cluster حقيقي بدل `local[*]` وكانت هذه نقطة تقييم منفصلة.
- مشروع مبني حصريًا لويندوز ويستخدم absolute Windows paths في وظائف إلزامية.
- Maven dependency غير مخزنة محليًا مع `network_profile=isolated`.

الفلسفة المتعمدة: **عدم اليقين لا يتحول إلى صفر آلي.**

## حزمة التدريب العامة للطلاب

لا نخزن ملفات CSV الكبيرة داخل Git. يتم توليد الحزمة العامة بصورة حتمية من الكود:

```bash
python datasets/generate_practice_data.py
```

أو من GitHub Actions عبر workflow باسم `Build Student Practice Pack` ثم تنزيل الـArtifact الناتج.

النتائج المرجعية للملف الصغير: Input=20,000، Clean=12,000، Corrected=5,000، Validated=17,000، Quarantine=3,000.

أما بيانات التصحيح السرية فلا تُرفع إلى GitHub؛ يتم توليدها وقت التشغيل من `GRADER_HIDDEN_SEED` المحفوظ كـRepository Secret.
