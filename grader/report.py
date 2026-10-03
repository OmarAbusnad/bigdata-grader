from __future__ import annotations
import json
from pathlib import Path


def write_report(reports_root: Path, project_id: str, payload: dict):
    out = Path(reports_root) / project_id
    out.mkdir(parents=True, exist_ok=True)
    js = out / "result.json"
    md = out / "evaluation.md"
    js.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    plan_meta = payload.get("plan_resolution") or {}
    plan = payload.get("execution_plan") or {}
    runtime = payload.get("runtime") or {}
    lines = [
        f"# تقرير التقييم — {project_id}", "",
        f"- **Grader:** V{payload.get('grader_version', '?')}",
        f"- **Commit:** `{payload.get('commit_sha') or 'unknown'}`",
        f"- **Plan confidence:** `{plan_meta.get('confidence', 'n/a')}`",
        f"- **Manual review required:** `{plan_meta.get('requires_manual_review', False)}`",
        f"- **Runtime status:** `{runtime.get('status', 'NOT_RUN')}`", "",
        "## خطة التشغيل المكتشفة", "",
        "```json", json.dumps(plan, ensure_ascii=False, indent=2), "```", "",
        "## أدلة فهم المستودع", "",
    ]
    for item in plan_meta.get("evidence", []) or []:
        lines.append(f"- {item}")
    if not plan_meta.get("evidence"):
        lines.append("- لا توجد أدلة LLM؛ تم الاعتماد على الاكتشاف الحتمي أو لم يتوفر مزود الذكاء الاصطناعي.")

    warnings = plan_meta.get("warnings") or []
    if warnings:
        lines += ["", "## تحذيرات خطة التشغيل", ""] + [f"- {w}" for w in warnings]

    if runtime:
        lines += ["", "## الاختبارات الفعلية", ""]
        if runtime.get("error"):
            lines.append(f"**خطأ:** `{runtime['error']}`")
        for case in runtime.get("cases", []) or []:
            lines += ["", f"### {case.get('name')}", "", f"الأمر: `{case.get('command', '')}`", ""]
            run = case.get("run") or {}
            lines.append(f"- Return code: `{run.get('returncode')}`")
            lines.append(f"- Elapsed: `{run.get('elapsed_seconds')}` sec")
            for a in case.get("assertions", []) or []:
                icon = "✅" if a.get("verdict") == "PASS" else "❌" if a.get("verdict") == "FAIL" else "⚠️"
                lines.append(f"- {icon} `{a.get('key') or a.get('id')}` — expected=`{a.get('expected')}` actual=`{a.get('actual')}`")
        runtime_summary = runtime.get("assertion_counts") or runtime.get("summary")
        if runtime_summary:
            lines += ["", "## ملخص Runtime", "", "```json", json.dumps(runtime_summary, ensure_ascii=False, indent=2), "```"]

    lines += ["", "## Static checks (أدلة مساعدة فقط)", "", "```json",
              json.dumps(payload.get("static_checks", {}), ensure_ascii=False, indent=2), "```", "",
              "> لا تُمنح الدرجة من وجود أسماء ملفات أو كلمات في الكود وحدها؛ المرجع الأساسي هو السلوك الفعلي في الاختبارات المخفية."]
    md.write_text("\n".join(lines), encoding="utf-8")
    return js, md
