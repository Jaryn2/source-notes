# Verification notes

On September 24, 2026, [GitHub Actions run 36030739505](https://github.com/Jaryn2/source-notes/actions/runs/36030739505) passed: **22 tests**, zero failures, zero errors, and zero skips. The run built the frontend and backend Docker image and ran the checks against PostgreSQL on Ubuntu. Open [the workflow](https://github.com/Jaryn2/source-notes/actions/workflows/check.yml) for later commits.

The 22 checks cover local retrieval, missing answers, exact citations, repeated request keys, note review, invalid provider responses, and sample prompt-injection attempts. All eight fixed local evaluation questions passed.

The first local checks ran with Windows, Java 21, Python 3.12, PostgreSQL 17.11, and pgvector 0.8.6. Across the three apps, 57 tests passed. All three databases passed a dump/restore check. The original Windows Docker engine was unavailable; the successful container checks above ran on GitHub.

The screenshots show the local app with fictional records. Jaryn reviewed the screens, and the Source Notes heading display was corrected. No outside usability study, public backend deployment, or paid model call has been completed.
