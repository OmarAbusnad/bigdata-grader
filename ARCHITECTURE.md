# Architecture Decisions

## Why one central codebase?
The grader owns datasets, oracle, policy, reports and orchestration. Student repositories remain untouched and are cloned under `workspaces/<project>/repo`.

## Why AI is not the scorer?
Repository structures vary, so AI is useful for discovery. Numeric grading must remain reproducible. Therefore AI proposes an execution plan; deterministic runtime checks observe the result.

## Why a dedicated MongoDB container per project?
Some submissions hard-code database names. A dedicated server eliminates cross-project state even when DB names cannot be overridden.

## Why localhost proxy?
In Docker, `localhost:27017` normally points to the student container, not MongoDB. A local `socat` forwarder preserves compatibility while MongoDB remains a separate container.

## Why two network profiles?
`isolated` is safer. `compat` exists because Spark Ivy/Maven package resolution may need egress in legacy student projects. A compat retry is evidence of an infrastructure compatibility issue, not automatically a student failure.

## Why no automatic zero on environment failure?
A grader must separate:

- STUDENT_FUNCTIONAL_FAILURE
- STUDENT_PORTABILITY_FAILURE
- GRADER_INFRA_FAILURE
- DEPENDENCY_RESOLUTION_FAILURE
- PLAN_DISCOVERY_UNCERTAINTY

Only the first two can affect academic grading, and portability only if the rubric requires it.
