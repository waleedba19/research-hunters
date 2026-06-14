"""Unit tests for telegram_ui module + v6.7 hunt-review flow (14 steps)."""
import os
import sys
import json
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import telegram_ui
import rq_packages


class TestMainMenu(unittest.TestCase):
    def test_main_menu_text_has_capabilities(self):
        text = telegram_ui.MAIN_MENU_TEXT.lower()
        for phrase in ("welcome", "81+", "ollama", "drive", "pdf",
                       "verify", "future research", "research", "3 rq packages"):
            self.assertIn(phrase, text)

    def test_main_menu_keyboard_has_buttons(self):
        kb = telegram_ui.main_menu_keyboard()
        self.assertIn("inline_keyboard", kb)
        rows = kb["inline_keyboard"]
        # 6 rows: New Hunt, Verify Refs, My Reports, Help, Settings, What's New
        self.assertEqual(len(rows), 6)
        callbacks = [c["callback_data"] for r in rows for c in r]
        for expected in ("main:newhunt", "main:verifyrefs", "main:myreports",
                         "main:help", "main:settings", "main:changelog"):
            self.assertIn(expected, callbacks)


class TestReviewScreen(unittest.TestCase):
    def test_review_has_all_14_steps(self):
        answers = {
            "research_type": "PhD",
            "title": "ML in education",
            "field": "education",
            "rq_angle": "empirical",
            "research_questions": ["RQ1", "RQ2"],
            "year_range": "2020-2024",
            "language": "en",
            "country": "world",
            "paper_type": "all",
            "quartile_filter": "any",
            "open_access": "no",
            "platforms": "all",
            "max_papers": "1000",
            "download_pdfs": "yes",
        }
        text, kb = telegram_ui.build_review_screen(answers)
        for label in telegram_ui.STEP_LABELS.values():
            self.assertIn(label, text)
        # Should have all 14 edit buttons + 1 start/cancel row
        cbds = [c["callback_data"] for r in kb["inline_keyboard"] for c in r]
        self.assertIn("hunt:start", cbds)
        self.assertIn("hunt:cancel", cbds)
        for key in telegram_ui.STEP_LABELS:
            self.assertIn(f"hunt:edit:{key}", cbds,
                          f"Missing edit button for {key}")

    def test_review_renders_all_14_step_labels(self):
        labels = set(telegram_ui.STEP_LABELS.keys())
        expected = {
            "research_type", "title", "field", "rq_angle", "research_questions",
            "year_range", "language", "country", "paper_type", "quartile_filter",
            "open_access", "platforms", "max_papers", "download_pdfs",
        }
        self.assertEqual(labels, expected,
                         f"Expected 14 step labels, got {labels}")

    def test_review_includes_total_count(self):
        answers = {k: "x" for k in telegram_ui.STEP_LABELS}
        text, _ = telegram_ui.build_review_screen(answers)
        self.assertIn("14 choices recorded", text)

    def test_review_handles_missing_answers(self):
        # Should not crash if any answer is None
        answers = {"title": "only title"}
        text, kb = telegram_ui.build_review_screen(answers)
        self.assertIn("_(not set)_", text)

    def test_format_field_value(self):
        # Each new field should have a friendly label
        for key, sample in [
            ("field", "education"),
            ("rq_angle", "empirical"),
            ("language", "ar"),
            ("country", "libya"),
            ("paper_type", "preprint"),
            ("quartile_filter", "q1"),
            ("open_access", "yes"),
        ]:
            out = telegram_ui._format_answer_value(key, sample)
            self.assertNotIn("not set", out,
                             f"{key}={sample} should have a label, got {out!r}")


class TestEditPanel(unittest.TestCase):
    def test_edit_panel_for_all_new_keys(self):
        for key in ("field", "rq_angle", "language", "country",
                    "paper_type", "quartile_filter", "open_access"):
            text, kb = telegram_ui.build_edit_panel(key, "any")
            self.assertIn("EDIT", text)
            cbds = [c["callback_data"] for r in kb["inline_keyboard"] for c in r]
            self.assertIn("hunt:back_to_review", cbds)
            self.assertIn("hunt:cancel", cbds)
            # Should have at least one set option
            set_opts = [c for c in cbds if c.startswith(f"hunt:set:{key}:")]
            self.assertGreater(len(set_opts), 0,
                               f"No set options for {key}")

    def test_edit_panel_research_questions(self):
        text, kb = telegram_ui.build_edit_panel("research_questions", "auto")
        cbds = [c["callback_data"] for r in kb["inline_keyboard"] for c in r]
        self.assertIn("hunt:set:research_questions:auto", cbds)


class TestHuntIntake14Steps(unittest.TestCase):
    def test_hunt_steps_count_is_14(self):
        import hunt_intake
        self.assertEqual(len(hunt_intake.HUNT_STEPS), 14)

    def test_all_hunt_steps_have_required_fields(self):
        import hunt_intake
        for step in hunt_intake.HUNT_STEPS:
            self.assertIn("key", step)
            self.assertIn("prompt", step)
            self.assertIn("allow_skip", step)
            # If options, must have at least 2
            if step.get("options"):
                self.assertGreaterEqual(len(step["options"]), 2)
                # All option tuples should be (value, label)
                for opt in step["options"]:
                    self.assertEqual(len(opt), 2)
            # key must be in STEP_LABELS
            self.assertIn(step["key"], telegram_ui.STEP_LABELS)

    def test_required_step_title_cannot_be_skipped(self):
        import hunt_intake
        for step in hunt_intake.HUNT_STEPS:
            if step["key"] == "title":
                self.assertFalse(step.get("allow_skip"),
                                 "Title is required and cannot be skipped")


class TestRQPackages(unittest.TestCase):
    def test_rq_packages_have_3_angles(self):
        self.assertEqual(len(rq_packages.PACKAGE_ANGLES), 3)
        ids = [a["id"] for a in rq_packages.PACKAGE_ANGLES]
        self.assertIn("theoretical", ids)
        self.assertIn("empirical", ids)
        self.assertIn("applied", ids)

    def test_generate_rq_packages_without_ollama(self):
        # With ollama_fn=None, should return 3 fallback packages
        pkgs = rq_packages.generate_rq_packages("machine learning in education",
                                                 ollama_fn=None,
                                                 max_total_seconds=10)
        self.assertEqual(len(pkgs), 3)
        for pkg in pkgs:
            self.assertIn("label", pkg)
            self.assertIn("focus", pkg)
            self.assertIn("rqs", pkg)
            self.assertIn("why", pkg)
            self.assertGreaterEqual(len(pkg["rqs"]), 2)
            self.assertLessEqual(len(pkg["rqs"]), 3)

    def test_format_packages_picker_includes_all_3(self):
        pkgs = rq_packages.generate_rq_packages("AI in education",
                                                 ollama_fn=None, max_total_seconds=10)
        text = rq_packages.format_packages_picker(pkgs)
        self.assertIn("Package 1", text)
        self.assertIn("Package 2", text)
        self.assertIn("Package 3", text)

    def test_packages_picker_keyboard_has_buttons(self):
        kb = rq_packages.packages_picker_keyboard()
        cbds = [c["callback_data"] for r in kb["inline_keyboard"] for c in r]
        for angle in rq_packages.PACKAGE_ANGLES:
            self.assertIn(f"hunt:rq:{angle['id']}", cbds)
        self.assertIn("hunt:rq:all", cbds)
        self.assertIn("hunt:rq:custom", cbds)
        self.assertIn("hunt:cancel", cbds)

    def test_parse_ai_package_response_valid_json(self):
        raw = '{"focus": "test", "rqs": ["q1", "q2"], "why": "good"}'
        out = rq_packages._parse_ai_package_response(raw)
        self.assertIsNotNone(out)
        self.assertEqual(out["focus"], "test")

    def test_parse_ai_package_response_with_fences(self):
        raw = '```json\n{"focus": "test", "rqs": ["q1"], "why": "x"}\n```'
        out = rq_packages._parse_ai_package_response(raw)
        self.assertIsNotNone(out)

    def test_parse_ai_package_response_garbage(self):
        out = rq_packages._parse_ai_package_response("not json at all")
        self.assertIsNone(out)

    def test_extract_keywords_strips_articles(self):
        kw = rq_packages._extract_keywords("An investigation of machine learning")
        self.assertFalse(kw.lower().startswith("an investigation"))

    def test_extract_keywords_handles_empty(self):
        kw = rq_packages._extract_keywords("")
        self.assertEqual(kw, "this topic")


class TestStepLabels(unittest.TestCase):
    def test_all_step_labels_have_emoji(self):
        import unicodedata
        for key, label in telegram_ui.STEP_LABELS.items():
            # First char should be a symbol/pictograph (not letter/digit)
            cat = unicodedata.category(label[0])
            self.assertTrue(
                cat.startswith("S") or ord(label[0]) > 0x2000,
                f"{key} label missing emoji: {label!r} (first char category={cat})"
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
