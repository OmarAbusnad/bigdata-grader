# Hidden grading datasets

`midterm_hidden_tests_v2.zip` is the instructor-only hidden test pack.

Run:

```bash
python datasets/prepare_hidden_tests.py
```

This extracts the hidden files locally into `datasets/hidden/` and creates `datasets/expected.json`.

Do not share `teacher_key.json` or `teacher_manifest.csv` with students.

The evaluator uses the teacher manifest as an oracle for sampled Cleaning / Upsert behavior, not merely for record counts.
