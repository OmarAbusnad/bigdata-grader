import argparse
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input")
    parser.add_argument("--classify-run-id")
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--threshold-mb", type=float, default=None)
    parser.add_argument("--raw-only", action="store_true")
    args = parser.parse_args()
