# Hybrid Data Pipeline for E-Commerce Orders
Core Stack: Python 3.12, Apache Spark 4.2.0, MongoDB 7.0.
Unified Entrypoint: src/main.py -> src/file_router.py
Small file <= 200 MB => Python Batch. Large file > 200 MB => PySpark.
Collections: orders_raw, orders_validated, orders_quarantine.
