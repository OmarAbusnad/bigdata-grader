# Security & Fairness Model

## Threat model
Student repositories are untrusted code. They may intentionally or accidentally:

- delete files,
- read host secrets,
- fork processes,
- consume all memory/CPU/disk,
- contact external services,
- hard-code localhost MongoDB,
- include prompt-injection text targeting the repository-analysis model.

## Controls

- Student execution occurs only in Docker.
- Per-project MongoDB and Docker network.
- Default network is `--internal`.
- `cap-drop=ALL` and `no-new-privileges`.
- CPU, RAM, PID and timeout limits.
- Hidden inputs mounted read-only.
- Teacher answer key remains on host.
- Repository text passed to LLM is explicitly marked untrusted.
- LLM commands are validated and shell chaining is rejected.
- Low-confidence plans stop for manual review.

## Known residual risks

Docker is isolation, not a perfect security boundary. For hostile-code threat models use a dedicated VM/ephemeral cloud runner around Docker as a second boundary. Do not run this grader on a workstation containing sensitive production credentials.
