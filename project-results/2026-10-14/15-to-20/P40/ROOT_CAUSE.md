# P40 — verified student CLI input-contract issue in late frozen snapshot

- Frozen SHA: `ce51dee3dff5a4abd589d1c5dcab88dfaae4020b`
- Grader command was `python main.py /grader-tests/test_01_small_batch_pipeline.csv`.
- Student root `main.py` calls `main()` without forwarding `sys.argv[1]`, and `src/main.py` uses `file_path or DATA_FILE`; the command-line dataset was ignored.
- Saved traceback:
```
File "/workspace/main.py", line 4, in <module>
  main()
File "/workspace/src/main.py", line 14, in main
  raise FileNotFoundError(f"CSV not found: {file_path}")
FileNotFoundError: CSV not found: data/orders_...
```
- Student sources: https://github.com/qusaiqaria-cmyk/-midterm-data-pipeline/blob/ce51dee3dff5a4abd589d1c5dcab88dfaae4020b/main.py and [src/main.py](https://github.com/qusaiqaria-cmyk/-midterm-data-pipeline/blob/ce51dee3dff5a4abd589d1c5dcab88dfaae4020b/src/main.py).
- Root is student entrypoint argument handling. Final API tests succeeded separately; preserve verified historical PASS. No new tests or score changes.