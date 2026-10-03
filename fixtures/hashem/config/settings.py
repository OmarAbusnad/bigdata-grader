import os
SMALL_FILE_THRESHOLD_MB = float(os.getenv("SMALL_FILE_THRESHOLD_MB", 200))
SPARK_MASTER_URL = os.getenv("SPARK_MASTER_URL", "local[*]")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "midterm_pipeline_db")
COLLECTION_RAW = "orders_raw"
COLLECTION_VALIDATED = "orders_validated"
COLLECTION_QUARANTINE = "orders_quarantine"
