# P07 — verified student Windows-only Java configuration

- Frozen SHA: `a7beeeaa76024f8ba3e13714afcfb75125d6b6d8`
- Original case `spark_pipeline`: `returncode=1`, stderr:
```
RuntimeError: Configured Java was not found at
C:\Program Files\Eclipse Adoptium\jdk-21.0.11.10-hotspot/bin/java.exe
```
- Traceback points to `src/main.py`, `build_spark_environment()`, line 178 in frozen code.
- Root attribution: student repository hard-codes a Windows Java path and does not provide a portable fallback for the Linux grader runtime. **Not** a grader Maven/network defect.
- Other successful frozen tests remain valid; no rerun or grade update.