# Changelog

## 4.0.0

- Added AI Repository Analyst with prompt-injection-resistant instructions.
- Added confidence gate and MANUAL_REVIEW behavior.
- Added per-project Docker sandbox.
- Added dedicated MongoDB container/network per project.
- Added localhost:27017 compatibility proxy.
- Added CPU/RAM/PID/time limits and restricted capabilities.
- Kept teacher oracle outside student container.
- Added isolated and compat network profiles.
- Added pyproject/setup.py dependency-install fallback.
- Added runtime image with Python, Java 17, PySpark, Mongo client dependencies and `py` compatibility alias.
- Reworked reporting around runtime evidence instead of static file presence.
- Added security/fairness policy and architecture documentation.
