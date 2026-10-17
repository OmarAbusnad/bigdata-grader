# P01 — freeze mismatch: old source cannot be used for later named-query verdict

- Student: رحاب بشير عبدالرحمن الخطيب
- Earlier frozen artifact: `frozen-P01-37390623044` [run 37390623044](https://github.com/omrbosnd/bigdata-grader/actions/runs/37390623044).
- Earlier frozen metadata SHA: `f1a440a4a07b8b8bd8c9bf9818de59e5046eeab3`.
- Latest submitted frozen metadata and corresponding `reports_final/P01/result.json` in [later diagnostic run 38424927615](https://github.com/omrbosnd/bigdata-grader/actions/runs/38424927615) both say source SHA `c43aae3d5e9c0d96731640206752f886f2618497`, freeze status READY.
- The later diagnostic artifact includes frozen metadata, ledger and reports **but not the actual matching source tar**.
- The old archived tar **must not** be executed and matched with newer student's current results; that would misattribute results to a different version.

## Safe next step

Fetch/freeze the **exact** later SHA `c43aae3d5e9c0d96731640206752f886f2618497` into a new isolated archive; compare its hash/commit with the accepted later report; then retry only `orders_in_period` with the student-declared `start/end` query params, preserving any already PASS query on that same later SHA. Never use current HEAD if different.

No P01 retest has been run, and no academic grade has been edited.
