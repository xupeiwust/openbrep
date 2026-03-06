from __future__ import annotations

import re

from openbrep.hsf_project import ScriptType
from openbrep.validator import ValidationIssue


class CrossScriptChecker:
    GDL_BUILTINS = {
        "ADD", "ADDX", "ADDY", "ADDZ", "BLOCK", "BRICK", "CYLIND", "SPHERE",
        "CONE", "ELLIPS", "PRISM", "PRISM_", "TUBE", "SWEEP", "RULED", "COONS",
        "FOR", "NEXT", "IF", "THEN", "ELSE", "ENDIF", "WHILE", "ENDWHILE",
        "GOTO", "GOSUB", "RETURN", "END", "DEL", "ROT", "ROTX", "ROTY", "ROTZ",
        "MUL", "MULX", "MULY", "MULZ", "PEN", "MATERIAL", "MODEL", "RESOL",
        "TOLER", "HOTSPOT", "HOTSPOT2", "LINE", "LINE2", "RECT", "RECT2",
        "POLY", "POLY2", "POLY2_", "ARC", "ARC2", "CIRCLE", "CIRCLE2",
        "TEXT", "TEXT2", "RICHTEXT2", "PROJECT2", "FRAGMENT2", "PICTURE2",
        "PRINT", "VARDIM1", "VARDIM2", "REQUEST", "IND", "INT", "ABS", "SQR",
        "SQRT", "SIN", "COS", "TAN", "ATN", "EXP", "LOG", "A", "B", "ZZYZX",
        "AND", "OR", "NOT", "MOD", "DIV", "TRUE", "FALSE", "PI",
    }

    def check(self, project) -> list[ValidationIssue]:
        issues = []
        script_3d = project.get_script(ScriptType.SCRIPT_3D)
        if script_3d and project.parameters:
            param_names = {p.name.upper() for p in project.parameters}
            used_vars = set(re.findall(r'\b([A-Za-z_][A-Za-z0-9_]*)\b', script_3d))
            used_vars_upper = {v.upper() for v in used_vars}
            missing = used_vars_upper - param_names - self.GDL_BUILTINS
            missing = {v for v in missing if len(v) > 1}
            if missing:
                issues.append(ValidationIssue(
                    level="warning",
                    category="cross_script",
                    file="3d.gdl",
                    message=f"使用了未在参数表定义的变量：{', '.join(sorted(missing)[:8])}",
                ))
        return issues
