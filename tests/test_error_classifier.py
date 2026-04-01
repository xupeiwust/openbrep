"""
Tests for openbrep.error_classifier.

Covers all 7 error categories + UNKNOWN fallback.
Each test uses a representative LP_XMLConverter / Archicad-style stderr string.
No compiler or LLM mocks needed — classifier is pure regex logic.
"""

import unittest
from openbrep.error_classifier import ErrorCategory, ErrorClassifier


class TestErrorClassifier(unittest.TestCase):

    def setUp(self):
        self.clf = ErrorClassifier()

    # ── XML_PARSE_ERROR ────────────────────────────────────────────────────

    def test_xml_parse_error_paramlist(self):
        stderr = "Error: paramlist.xml: not well-formed (invalid token) at line 12"
        case = self.clf.classify(stderr)
        self.assertEqual(case.category, ErrorCategory.XML_PARSE_ERROR)
        self.assertIn("paramlist.xml", case.matched_pattern.lower())
        self.assertIsNotNone(case.hint)

    def test_xml_parse_error_generic(self):
        stderr = "XMLSyntaxError: malformed XML in libpartdata.xml"
        case = self.clf.classify(stderr)
        self.assertEqual(case.category, ErrorCategory.XML_PARSE_ERROR)

    # ── MISSING_ENDIF ──────────────────────────────────────────────────────

    def test_missing_endif_expected(self):
        stderr = "Syntax error: ENDIF expected at line 45 in 3d.gdl"
        case = self.clf.classify(stderr)
        self.assertEqual(case.category, ErrorCategory.MISSING_ENDIF)
        self.assertEqual(case.target_file, "scripts/3d.gdl")

    def test_missing_endif_unexpected(self):
        stderr = "Error: Unexpected ENDIF on line 17"
        case = self.clf.classify(stderr)
        self.assertEqual(case.category, ErrorCategory.MISSING_ENDIF)

    # ── MISSING_NEXT ───────────────────────────────────────────────────────

    def test_missing_next_expected(self):
        stderr = "GDL compile error: NEXT expected after FOR loop at line 33"
        case = self.clf.classify(stderr)
        self.assertEqual(case.category, ErrorCategory.MISSING_NEXT)

    def test_missing_next_without_for(self):
        stderr = "Runtime error: NEXT without FOR at line 58"
        case = self.clf.classify(stderr)
        self.assertEqual(case.category, ErrorCategory.MISSING_NEXT)

    # ── MISSING_END ────────────────────────────────────────────────────────

    def test_missing_end_expected(self):
        stderr = "Compile failed: END expected, reached end of script"
        case = self.clf.classify(stderr)
        self.assertEqual(case.category, ErrorCategory.MISSING_END)
        self.assertIn("END", case.hint)

    def test_missing_end_of_file(self):
        stderr = "Error: unexpected end of file while parsing script"
        case = self.clf.classify(stderr)
        self.assertEqual(case.category, ErrorCategory.MISSING_END)

    # ── UNDEFINED_VAR ──────────────────────────────────────────────────────

    def test_undefined_variable(self):
        stderr = "GDL error: Undefined variable 'seat_h' at line 22"
        case = self.clf.classify(stderr)
        self.assertEqual(case.category, ErrorCategory.UNDEFINED_VAR)
        self.assertIn("参数名", case.hint)

    def test_undefined_identifier(self):
        stderr = "Error: Unknown identifier 'nShelves' in 3d.gdl line 10"
        case = self.clf.classify(stderr)
        self.assertEqual(case.category, ErrorCategory.UNDEFINED_VAR)

    # ── WRONG_ARG_COUNT ────────────────────────────────────────────────────

    def test_wrong_arg_count(self):
        stderr = "Error: Wrong number of arguments for PRISM_ at line 7"
        case = self.clf.classify(stderr)
        self.assertEqual(case.category, ErrorCategory.WRONG_ARG_COUNT)
        self.assertIn("PRISM_", case.hint)

    def test_parameter_count_mismatch(self):
        stderr = "Compile error: parameter count mismatch in PRISM call at line 15"
        case = self.clf.classify(stderr)
        self.assertEqual(case.category, ErrorCategory.WRONG_ARG_COUNT)

    # ── ADD_DEL_MISMATCH ───────────────────────────────────────────────────

    def test_add_del_mismatch(self):
        stderr = "Error: transformation stack unbalanced at end of script"
        case = self.clf.classify(stderr)
        self.assertEqual(case.category, ErrorCategory.ADD_DEL_MISMATCH)
        self.assertIn("ADD", case.hint)

    def test_del_without_add(self):
        stderr = "Stack underflow: DEL without matching ADD at line 40"
        case = self.clf.classify(stderr)
        self.assertEqual(case.category, ErrorCategory.ADD_DEL_MISMATCH)

    # ── UNKNOWN fallback ───────────────────────────────────────────────────

    def test_unknown_fallback_empty(self):
        case = self.clf.classify("")
        self.assertEqual(case.category, ErrorCategory.UNKNOWN)
        self.assertEqual(case.matched_pattern, "")
        self.assertEqual(case.hint, "")
        self.assertIsNone(case.target_file)

    def test_unknown_fallback_unrecognized(self):
        stderr = "Some completely unrecognized tool output with no GDL keywords"
        case = self.clf.classify(stderr)
        self.assertEqual(case.category, ErrorCategory.UNKNOWN)

    # ── raw_stderr preserved ───────────────────────────────────────────────

    def test_raw_stderr_preserved(self):
        raw = "NEXT expected at line 99"
        case = self.clf.classify(raw)
        self.assertEqual(case.raw_stderr, raw)

    # ── file inference ─────────────────────────────────────────────────────

    def test_file_inference_from_stderr(self):
        """If stderr mentions a filename, target_file should reflect it."""
        stderr = "Error in file '2d.gdl': ENDIF expected at line 5"
        case = self.clf.classify(stderr)
        self.assertEqual(case.category, ErrorCategory.MISSING_ENDIF)
        self.assertEqual(case.target_file, "scripts/2d.gdl")


if __name__ == "__main__":
    unittest.main()
