بيانات التدريب العامة - مقرر البيانات الضخمة
==========================================

هذه الملفات مخصصة للتجربة قبل المناقشة.

مهم:
المشاريع في هذا المقرر مبنية على CSV، لذلك ملفات البيانات بصيغة CSV
ويمكن فتحها أيضًا في Excel. لا تستخدم XLSX كمدخل إذا كان مشروعك لا يدعمه.

1) الملف الصغير:
01_student_test_small.csv
الحجم: 8.61 MB
المحرك المتوقع عند Threshold=200MB: Python Batch

النتائج بعد Transform/ELT:
- Input / orders_raw: 20,000
- Clean Valid: 12,000
- Corrected: 5,000
- orders_validated: 17,000
- orders_quarantine: 3,000

2) الملف الكبير:
02_student_test_large_spark.csv
الحجم: 257.57 MB
المحرك المتوقع عند Threshold=200MB: PySpark

النتائج بعد Transform/ELT:
- Input / orders_raw: 600,000
- Clean Valid: 360,000
- Corrected: 150,000
- orders_validated: 510,000
- orders_quarantine: 90,000

تفاصيل أنواع التصحيح وأسباب العزل موجودة داخل:
EXPECTED_RESULTS.xlsx

ملاحظة:
عند إعادة تشغيل نفس الملف، قد تختلف سياسة orders_raw حسب التصميم
(Append-only أو fingerprint skip). الحكم الأساسي يكون على الحالة النهائية
في orders_validated وعدم وجود Duplicate Business Keys.
