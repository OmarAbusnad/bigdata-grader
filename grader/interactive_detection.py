"""Conservative static analysis of simple interactive Python ingest CLIs.

Only generates stdin when a single file prompt is proven, and if a menu is
present, the pipeline option itself is proven in the AST. Never executes code.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path


def infer_ingest_stdin(path: Path) -> str | None:
    try:
        source = path.read_text(encoding="utf-8-sig", errors="replace")
        tree = ast.parse(source)
    except (OSError, SyntaxError):
        return None

    mains = [n for n in tree.body
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
             and n.name == "main"]
    if len(mains) != 1:
        return None
    main = mains[0]
    input_calls = [
        n for n in ast.walk(main)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "input"
    ]
    if not input_calls:
        return None

    file_calls = []
    for n in input_calls:
        parent_names = []
        for node in ast.walk(main):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                value = node.value
                if value is not None and n in list(ast.walk(value)):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    parent_names += [t.id.lower() for t in targets if isinstance(t, ast.Name)]
        prompts = [a.value.lower() for a in n.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
        if any(re.search(r"file|path|csv|مسار|ملف", x) for x in parent_names + prompts):
            file_calls.append(n)

    if len(file_calls) != 1:
        return None
    file_call = file_calls[0]
    if len(input_calls) == 1:
        return "{file}\n"

    # A multi-prompt CLI is supported only if the file prompt belongs to a
    # proven menu branch that explicitly selects data ingestion, never an API.
    menu_present = bool(re.search(r"(?im)2\s*[.)]\s*.*(?:ingest|pipeline|data|رفع|بيانات)", source))
    menu_branch = any(
        isinstance(n, ast.If)
        and any(isinstance(k, ast.Constant) and str(k.value) == "2" for k in ast.walk(n.test))
        and file_call in list(ast.walk(n))
        for n in ast.walk(main)
    )
    if not menu_present or not menu_branch:
        return None

    # Another input() after ingestion can be an Enter-to-continue prompt;
    # feed Enter only for explicitly documented prompts.
    continue_prompt = any(
        n is not file_call
        and n.args and isinstance(n.args[0], ast.Constant)
        and isinstance(n.args[0].value, str)
        and re.search(r"اضغط\s*enter|press\s*enter|العودة للقائمة", n.args[0].value, re.I)
        for n in input_calls
    )
    exit_present = bool(re.search(r"(?im)3\s*[.)]\s*.*(?:exit|exet|خروج|إغلاق)", source))
    # End-of-file is never relied upon to shut down a loop.
    if not exit_present:
        return None
    return "2\n{file}\n" + ("\n" if continue_prompt else "") + "3\n"
