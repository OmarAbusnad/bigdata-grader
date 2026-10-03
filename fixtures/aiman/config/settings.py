import os
from pathlib import Path
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "midterm_ecommerce")
RAW_COLLECTION = "orders_raw"
VALIDATED_COLLECTION = "orders_validated"
QUARANTINE_COLLECTION = "orders_quarantine"
SMALL_FILE_THRESHOLD_MB = float(os.getenv("SMALL_FILE_THRESHOLD_MB", "200.0"))
JDK17_DEFAULT_PATH = r"C:\\Users\\MC\\AppData\\Local\\Programs\\Eclipse Adoptium\\jdk-17"
