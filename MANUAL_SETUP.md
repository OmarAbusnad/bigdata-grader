# Manual setup required after publishing to GitHub

Only the following steps require the instructor/account owner:

1. Keep the grader repository **Private**.
2. In **Settings → Secrets and variables → Actions**, add:
   - `OPENAI_API_KEY`
   - `GRADER_HIDDEN_SEED` — choose a long random integer/string representable as an integer seed and do not share it with students.
   - `STUDENT_REPOS_TOKEN` only if some student repositories are private; use a fine-grained read-only token scoped only to those repositories.
3. Optional Actions variable:
   - `GRADER_LLM_MODEL`
4. Enable GitHub Actions for the repository if the organization disables them by default.
5. Run **CI**, then **Grade Pilot Project** for one project before running the batch workflow.

Do not paste secrets into chat, source files, README, workflow inputs, or `submissions.csv`.
