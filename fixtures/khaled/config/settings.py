from pathlib import Path
PROJECT_ROOT = Path(r"D:\\midterm-data-pipeline")
DATA_DIR = Path(r"D:\\Big data")
SMALL_FILE_THRESHOLD_MB = 200
MONGO_URI = "mongodb://127.0.0.1:27017"
MONGO_DATABASE = "midterm_data_pipeline"
RAW_COLLECTION = "orders_raw"
VALIDATED_COLLECTION = "orders_validated"
QUARANTINE_COLLECTION = "orders_quarantine"
