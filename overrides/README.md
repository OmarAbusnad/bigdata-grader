# Instructor Overrides

هذه الملفات **خاصة بالمصحح** وليست متطلبًا على الطالب.

استخدم ملفًا باسم `<project_id>.yaml` فقط عندما لا يستطيع الـAI/Heuristic اكتشاف طريقة تشغيل مشروع بعينه بثقة كافية.

مثال `P18.yaml`:

```yaml
ingest_command: "python src/main.py --input {file} --db-name {db_name}"
setup_command: "python src/mongo_setup.py"
database_name: "midterm_ecommerce"
database_configurable: true
mongo_uri: "mongodb://localhost:27017"
business_key: "id_order"
threshold_mb: 200
threshold_configurable: true
collections:
  raw: orders_raw
  validated: orders_validated
  quarantine: orders_quarantine
```

لا تضع `grader.yaml` داخل مستودعات الطلاب ولا تطلب منهم أي تعديل من أجل المصحح.
