"""
GDL compile error classifier.

Maps LP_XMLConverter/Archicad stderr patterns to known error categories,
returning a structured ErrorCase with a targeted fix hint for prompt injection.

All logic is deterministic (regex-based). No LLM calls.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ErrorCategory(Enum):
    MISSING_ENDIF      = "missing_endif"
    MISSING_NEXT       = "missing_next"
    MISSING_END        = "missing_end"
    UNDEFINED_VAR      = "undefined_var"
    WRONG_ARG_COUNT    = "wrong_arg_count"
    ADD_DEL_MISMATCH   = "add_del_mismatch"
    XML_PARSE_ERROR    = "xml_parse_error"
    UNKNOWN            = "unknown"


@dataclass
class ErrorCase:
    category: ErrorCategory
    matched_pattern: str        # 匹配到的原始错误片段
    target_file: Optional[str]  # 推断出的出错文件（如 "scripts/3d.gdl"）
    hint: str                   # 注入 prompt 的定向修复提示（一句话）
    raw_stderr: str             # 原始 stderr 全文


# Each rule: (category, compiled_regex, target_file_or_None, hint)
# Rules are evaluated in order; first match wins.
_RULES: list[tuple[ErrorCategory, re.Pattern, Optional[str], str]] = [
    # ── XML / paramlist parse errors ──────────────────────────────────────
    (
        ErrorCategory.XML_PARSE_ERROR,
        re.compile(
            r"(?:xml|parse|ParseError|XMLSyntaxError|malformed|not well-formed"
            r"|paramlist\.xml|libpartdata\.xml"
            # LP_XMLConverter: "(0) : error: Missing ParamSectHeader" / "Invalid XML"
            r"|\(\d+\)\s*:\s*error:.*(?:ParamSect|XML|param|parse))",
            re.IGNORECASE,
        ),
        "paramlist.xml",
        "paramlist.xml 无法解析：检查 XML 标签闭合、特殊字符转义（<>&）、UTF-8 编码是否正确。",
    ),
    # ── ENDIF / IF ────────────────────────────────────────────────────────
    (
        ErrorCategory.MISSING_ENDIF,
        re.compile(
            r"(?:ENDIF\s+expected|ENDIF\s+missing|unexpected\s+ENDIF"
            r"|syntax\s+error.*\bIF\b|\bIF\b.*block.*not\s+closed"
            # LP_XMLConverter: "(0) : error: ENDIF expected at line N"
            r"|\(\d+\)\s*:\s*error:.*ENDIF)",
            re.IGNORECASE,
        ),
        "scripts/3d.gdl",
        "IF/ENDIF 不配对：每个多行 IF ... THEN 必须有对应 ENDIF，单行 IF 不需要 ENDIF。",
    ),
    # ── NEXT / FOR ────────────────────────────────────────────────────────
    (
        ErrorCategory.MISSING_NEXT,
        re.compile(
            r"(?:NEXT\s+expected|NEXT\s+without\s+FOR|FOR.*not\s+closed"
            r"|missing\s+NEXT|\bFOR\b.*unclosed"
            # LP_XMLConverter: "(0) : error: NEXT expected"
            r"|\(\d+\)\s*:\s*error:.*NEXT)",
            re.IGNORECASE,
        ),
        "scripts/3d.gdl",
        "FOR/NEXT 不配对：每个 FOR 必须有对应 NEXT，检查嵌套循环是否都有闭合。",
    ),
    # ── END (3D script terminator) ────────────────────────────────────────
    (
        ErrorCategory.MISSING_END,
        re.compile(
            r"(?:END\s+expected|END\s+missing|script.*not\s+terminated"
            r"|unexpected\s+end\s+of\s+(?:file|script)|missing\s+END\b"
            # LP_XMLConverter: "(0) : error: END expected" / "unexpected end of script"
            r"|\(\d+\)\s*:\s*error:.*\bEND\b)",
            re.IGNORECASE,
        ),
        "scripts/3d.gdl",
        "3D 脚本末尾缺少 END：确保主流程最后一行是 END，子程序用 RETURN 不用 END。",
    ),
    # ── Undefined variable ────────────────────────────────────────────────
    (
        ErrorCategory.UNDEFINED_VAR,
        re.compile(
            r"(?:undefined\s+(?:variable|identifier|label|parameter)"
            r"|undeclared\s+variable|unknown\s+(?:variable|identifier)"
            r"|variable\s+not\s+(?:found|defined)"
            # LP_XMLConverter: "(0) : error: Undefined variable 'x'"
            r"|\(\d+\)\s*:\s*error:.*(?:undefined|undeclared|unknown\s+variable|unknown\s+identifier))",
            re.IGNORECASE,
        ),
        None,  # 可能在任意脚本，不锁定
        "未定义变量：检查 paramlist.xml 中参数名与脚本中使用的变量名是否完全一致（区分大小写）。",
    ),
    # ── Wrong argument count ──────────────────────────────────────────────
    (
        ErrorCategory.WRONG_ARG_COUNT,
        re.compile(
            r"(?:wrong\s+number\s+of\s+(?:arguments|parameters)"
            r"|parameter\s+count\s+mismatch|too\s+(?:few|many)\s+(?:arguments|parameters)"
            r"|invalid\s+(?:argument|parameter)\s+count"
            # LP_XMLConverter: "(0) : error: Wrong number of arguments for PRISM_"
            r"|\(\d+\)\s*:\s*error:.*(?:wrong\s+number|argument\s+count|parameter\s+count))",
            re.IGNORECASE,
        ),
        "scripts/3d.gdl",
        "参数数量错误：最常见于 PRISM_ 缺少高度参数（PRISM_ n, h, ...），或顶点数与 n 不一致。",
    ),
    # ── ADD/DEL mismatch (runtime geometry shift, detected via stderr msg) ─
    (
        ErrorCategory.ADD_DEL_MISMATCH,
        re.compile(
            r"(?:add.*del.*(?:mismatch|unbalanced|imbalance)"
            r"|del.*add.*(?:mismatch|unbalanced|imbalance)"
            r"|transformation\s+stack.*(?:unbalanced|overflow|underflow)"
            r"|stack\s+(?:overflow|underflow|unbalanced)"
            r"|DEL\s+without\s+(?:ADD|matching)"
            r"|ADD\s+without\s+(?:DEL|matching)"
            # LP_XMLConverter: "(0) : error: Transformation stack unbalanced"
            r"|\(\d+\)\s*:\s*error:.*(?:stack\s+(?:unbalanced|overflow|underflow)|ADD|DEL))",
            re.IGNORECASE,
        ),
        "scripts/3d.gdl",
        "ADD/DEL 不配平：每条执行路径（含 IF 分支）的变换层数必须配平，ADD/ADDX/ADDY/ADDZ 与 DEL 需一一对应。",
    ),
]


def _infer_file_from_stderr(stderr: str) -> Optional[str]:
    """Try to extract a script filename from the stderr text."""
    m = re.search(
        r"(?:in\s+|file\s+|script\s+)['\"]?(\w+\.gdl|paramlist\.xml|libpartdata\.xml)['\"]?",
        stderr,
        re.IGNORECASE,
    )
    if m:
        stem = m.group(1).lower()
        if stem == "paramlist.xml":
            return "paramlist.xml"
        if stem in ("3d.gdl", "2d.gdl", "1d.gdl", "vl.gdl", "ui.gdl", "pr.gdl"):
            return f"scripts/{stem}"
    return None


class ErrorClassifier:
    """
    Deterministic classifier for LP_XMLConverter/Archicad stderr output.

    Usage:
        classifier = ErrorClassifier()
        case = classifier.classify(stderr_text)
        if case.category != ErrorCategory.UNKNOWN:
            # inject case.hint into the retry prompt
    """

    def classify(self, stderr: str) -> ErrorCase:
        text = (stderr or "").strip()

        for category, pattern, default_file, hint in _RULES:
            m = pattern.search(text)
            if m:
                matched = m.group(0)
                # Try to extract file from stderr; fall back to rule default
                inferred = _infer_file_from_stderr(text)
                target = inferred if inferred else default_file
                return ErrorCase(
                    category=category,
                    matched_pattern=matched,
                    target_file=target,
                    hint=hint,
                    raw_stderr=text,
                )

        return ErrorCase(
            category=ErrorCategory.UNKNOWN,
            matched_pattern="",
            target_file=None,
            hint="",
            raw_stderr=text,
        )
