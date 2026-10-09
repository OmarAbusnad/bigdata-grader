"""Read-only frozen Spark connector diagnostic.

Determines whether an isolated Maven dependency failure can be attributed to
the submitted source or whether the grading sandbox must provide dependency
resolution. It never executes untrusted student code or infers grades.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path

COORD = re.compile(
    r"org\.mongodb\.spark:mongo-spark-connector_(2\.(?:12|13)):([0-9]+(?:\.[0-9]+){1,3})"
)
REQ = re.compile(r"(?im)^\s*pyspark\s*(==|~=|>=|<=|>|<)\s*(\d+)\.(\d+)(?:\.(\d+))?")
JAR_PATTERN = re.compile(r"(?i)(?:spark\.jars|mongo-spark-connector|mongodb.*connector)")
MAVEN_NET = (
    "unresolved dependencies", "unknownhostexception",
    "repo1.maven.org not found", "repos.spark-packages.org not found",
    "host repo1.maven.org not found", "module not found: org.mongodb.spark",
)


def check_submission(repo: Path, *, runtime_error: str = "") -> dict:
    if not repo.is_dir():
        raise ValueError("Repository path not found")
    texts = []
    source_literals = []
    source_paths = []
    for p in repo.rglob("*.py"):
        if any(part in {".git", ".venv", "venv", "__pycache__"} for part in p.parts):
            continue
        if len(source_paths) >= 500:
            break
        try:
            if p.stat().st_size > 512_000:
                continue
            content = p.read_text(encoding="utf-8-sig", errors="replace")
            texts.append(content)
            # AST resolves adjacent string literals split over multiple lines.
            # No student code is executed.
            try:
                tree=ast.parse(content)
                source_literals.extend(node.value for node in ast.walk(tree)
                    if isinstance(node,ast.Constant) and isinstance(node.value,str))
            except SyntaxError:
                pass
            source_paths.append(str(p.relative_to(repo)))
        except OSError:
            continue
    source = "\n".join(texts)
    requirements = []
    for p in sorted(repo.rglob("requirements*.txt"))[:25]:
        try:
            requirements.append(p.read_text(encoding="utf-8-sig", errors="replace"))
        except OSError:
            pass
    declarations = sorted(set(COORD.findall(source + "\n" + "\n".join(source_literals))))
    packages = sorted({f"org.mongodb.spark:mongo-spark-connector_{scala}:{version}"
                       for scala, version in declarations})
    pyspark_versions = [
        {"operator": op, "major": int(major), "minor": int(minor), "patch": int(patch or 0)}
        for part in requirements for op, major, minor, patch in REQ.findall(part)
    ]
    # A declared minimum >=4 or pinned 4 is proof of an incompatible Spark v10
    # combination, not a reason to silently replace the student's version.
    spark4_required = any(
        x["major"] >= 4 and x["operator"] in {"==", "~=", ">=", ">"}
        for x in pyspark_versions
    )
    spark3_pinned = any(
        x["major"] == 3 and x["operator"] == "=="
        for x in pyspark_versions
    )
    legacy_connector = any(int(v.split(".")[0]) < 10 for _, v in declarations)
    modern_connector = any(int(v.split(".")[0]) >= 10 for _, v in declarations)
    source_uses_mongo_fmt = bool(re.search(r"""\.format\s*\(\s*["']mongodb["']\s*\)""", source))
    source_uses_legacy_fmt = bool(re.search(r"""\.format\s*\(\s*["']mongo["']\s*\)""", source))
    checked_jars = sorted(str(p.relative_to(repo)) for p in repo.rglob("*.jar"))[:50]
    network_failure = any(w in runtime_error.lower() for w in MAVEN_NET)

    source_errors = []
    if any(scala == "2.12" and int(v.split(".")[0]) >= 11 for scala, v in declarations):
        source_errors.append("MongoDB Spark connector 11.x is published for Scala 2.13, not 2.12; the submitted Maven coordinate cannot resolve.")
    if any(int(v.split(".")[0]) >= 11 for _, v in declarations) and spark3_pinned:
        source_errors.append("Spark 3.x is pinned, but MongoDB Spark connector 11.x targets Spark 4.x.")
    if spark4_required and modern_connector and any(int(v.split(".")[0]) < 11 for _, v in declarations):
        source_errors.append("Spark 4+ declared but MongoDB Spark connector 10.x targets Spark 3.x; do not silently replace student versions.")
    if legacy_connector and source_uses_mongo_fmt:
        source_errors.append("Legacy MongoDB connector 3.x uses format mongo, not mongodb.")
    if modern_connector and source_uses_legacy_fmt and not source_uses_mongo_fmt:
        source_errors.append("MongoDB connector 10.x uses format mongodb, not mongo.")

    if source_errors:
        verdict = "STUDENT_VERSION_OR_FORMAT_MISMATCH"
        owner = "STUDENT_CODE"
        next_step = "Record source-level configuration mismatch; do not retry unchanged source."
    elif network_failure and packages:
        verdict = "GRADER_NETWORK_DEPENDENCY_PRECONDITION"
        owner = "GRADER_ENVIRONMENT"
        next_step = "Resolve exact student-declared coordinates during controlled image build; retry affected Spark stage only and retain all prior PASS."
    elif network_failure and checked_jars:
        verdict = "MAVEN_REQUEST_DESPITE_BUNDLED_JAR"
        owner = "GRADER_ENVIRONMENT_OR_STUDENT_CONFIGURATION"
        next_step = "Check declared classpath and alternate package resolution; avoid zero for blocked tests."
    elif network_failure:
        verdict = "CONNECTOR_SOURCE_OR_GRADER_UNRESOLVED"
        owner = "UNPROVEN"
        next_step = "Inspect non-Python build/README/launch contract; do not attribute download failure automatically."
    else:
        verdict = "NO_CONFIRMED_MAVEN_BLOCK"
        owner = "UNDETERMINED"
        next_step = "Use separate assertion evidence."

    return {
        "status": verdict, "owner": owner, "source_errors": source_errors,
        "declared_coordinates": packages, "pyspark_constraints": pyspark_versions,
        "jars_committed": checked_jars, "network_failure_from_saved_logs": network_failure,
        "source_has_mongodb_format": source_uses_mongo_fmt,
        "source_has_legacy_mongo_format": source_uses_legacy_fmt,
        "source_files_checked": len(source_paths), "next_step": next_step,
        "runtime_tests_executed": 0, "official_grade_approved": False,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repository", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--saved-error", default="")
    args = ap.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    result = check_submission(args.repository, runtime_error=args.saved_error)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": result["status"], "owner": result["owner"],
                      "coordinates": result["declared_coordinates"]}))


if __name__ == "__main__":
    main()
