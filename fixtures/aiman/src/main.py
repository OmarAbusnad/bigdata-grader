import argparse
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", "-i", default="data/orders_sample_100k.csv")
    parser.add_argument("--run-id")
    parser.add_argument("--db-name", default="midterm_ecommerce")
    parser.add_argument("--batch-size", type=int, default=10000)
    parser.add_argument("--reset-db", action="store_true")
    args = parser.parse_args()
