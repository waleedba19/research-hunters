"""
tests/test_hunt_intake.py — Unit tests for the hunt_intake module.

Tests the state machine end-to-end without Telegram:
  - All 5 steps can be recorded
  - Skipping optional steps uses defaults
  - get_intake_answers returns correct values
  - cancel_intake clears state
"""
import os
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

# Use a temp STATE_DIR for isolation
TMP_DIR = tempfile.mkdtemp(prefix="hunt_intake_test_")
os.environ["STATE_DIR"] = TMP_DIR

# Import after setting env
import importlib
import telegram_bot  # noqa: E402
importlib.reload(telegram_bot)
import hunt_intake  # noqa: E402
importlib.reload(hunt_intake)


def test_start_and_complete():
    """Full flow: start, answer all 14, check completion (v6.7)."""
    chat_id = 99001
    hunt_intake.cancel_intake(chat_id)
    hunt_intake.start_hunt_intake(chat_id, prefill={"title": "Attention is all you need"})
    assert hunt_intake.is_intake_active(chat_id)
    assert hunt_intake.get_current_intake_step(chat_id)["key"] == "research_type"
    # Step 1: research_type
    hunt_intake.record_intake_answer(chat_id, "PhD")
    assert hunt_intake.get_current_intake_step(chat_id)["key"] == "title"
    # Step 2: title (pre-filled, confirm)
    hunt_intake.record_intake_answer(chat_id, "Attention is all you need")
    # Step 3: field
    hunt_intake.record_intake_answer(chat_id, "computer_science")
    # Step 4: rq_angle
    hunt_intake.record_intake_answer(chat_id, "empirical")
    # Step 5: research_questions (auto-generate)
    hunt_intake.record_intake_answer(chat_id, "auto")
    # Step 6: year_range
    hunt_intake.record_intake_answer(chat_id, "any")
    # Step 7: language
    hunt_intake.record_intake_answer(chat_id, "en")
    # Step 8: country
    hunt_intake.record_intake_answer(chat_id, "world")
    # Step 9: paper_type
    hunt_intake.record_intake_answer(chat_id, "all")
    # Step 10: quartile_filter
    hunt_intake.record_intake_answer(chat_id, "any")
    # Step 11: open_access
    hunt_intake.record_intake_answer(chat_id, "no")
    # Step 12: platforms
    hunt_intake.record_intake_answer(chat_id, "tier1")
    # Step 13: max_papers
    hunt_intake.record_intake_answer(chat_id, "50")
    # Step 14: download_pdfs
    hunt_intake.record_intake_answer(chat_id, "yes")
    # Should be complete now
    assert hunt_intake.is_intake_complete(chat_id)
    assert not hunt_intake.is_intake_active(chat_id)
    answers = hunt_intake.get_intake_answers(chat_id)
    assert answers["research_type"] == "PhD"
    assert answers["title"] == "Attention is all you need"
    assert answers["field"] == "computer_science"
    assert answers["rq_angle"] == "empirical"
    assert answers["research_questions"] == "auto"
    assert answers["year_range"] == "any"
    assert answers["language"] == "en"
    assert answers["country"] == "world"
    assert answers["paper_type"] == "all"
    assert answers["quartile_filter"] == "any"
    assert answers["open_access"] == "no"
    assert answers["platforms"] == "tier1"
    assert answers["max_papers"] == "50"
    assert answers["download_pdfs"] == "yes"
    print(f"[test] start_and_complete: PASS (14 steps recorded, complete=True)")
    return True


def test_skip_uses_defaults():
    """Skipping optional steps should fill in defaults (v6.7: 14 steps)."""
    chat_id = 99002
    hunt_intake.cancel_intake(chat_id)
    hunt_intake.start_hunt_intake(chat_id)
    # Skip step 1 (research_type, default 'general')
    hunt_intake.skip_intake_step(chat_id)
    # Title is required, can't skip
    assert hunt_intake.get_current_intake_step(chat_id)["key"] == "title"
    hunt_intake.record_intake_answer(chat_id, "Topic")
    # Skip remaining 12 steps (all have defaults)
    for _ in range(12):
        hunt_intake.skip_intake_step(chat_id)
    assert hunt_intake.is_intake_complete(chat_id)
    answers = hunt_intake.get_intake_answers(chat_id)
    assert answers["research_type"] == "general"
    assert answers["title"] == "Topic"
    assert answers["field"] == "general"
    assert answers["rq_angle"] == "empirical"
    assert answers["research_questions"] == "auto"
    assert answers["year_range"] == "any"
    assert answers["language"] == "en"
    assert answers["country"] == "world"
    assert answers["paper_type"] == "all"
    assert answers["quartile_filter"] == "any"
    assert answers["open_access"] == "no"
    assert answers["platforms"] == "all"
    assert answers["max_papers"] == "1000"
    assert answers["download_pdfs"] == "yes"
    print(f"[test] skip_uses_defaults: PASS (all 12 skipped = defaults applied)")
    return True


def test_cannot_skip_required():
    """Trying to skip 'title' (required) should not advance."""
    chat_id = 99003
    hunt_intake.cancel_intake(chat_id)
    hunt_intake.start_hunt_intake(chat_id)
    # Skip step 1
    hunt_intake.skip_intake_step(chat_id)
    # Try to skip step 2 (title, required) - should not advance
    before_step = hunt_intake.get_current_intake_step(chat_id)["key"]
    hunt_intake.skip_intake_step(chat_id)
    after_step = hunt_intake.get_current_intake_step(chat_id)["key"]
    assert before_step == "title" and after_step == "title", \
        f"Should stay on title: {before_step!r} -> {after_step!r}"
    print(f"[test] cannot_skip_required: PASS (title not skipped)")
    return True


def test_cancel_clears_state():
    chat_id = 99004
    hunt_intake.cancel_intake(chat_id)
    hunt_intake.start_hunt_intake(chat_id)
    hunt_intake.record_intake_answer(chat_id, "PhD")
    assert hunt_intake.is_intake_active(chat_id)
    hunt_intake.cancel_intake(chat_id)
    assert not hunt_intake.is_intake_active(chat_id)
    assert not hunt_intake.is_intake_complete(chat_id)
    print(f"[test] cancel_clears_state: PASS")
    return True


def test_intake_progress_text():
    chat_id = 99005
    hunt_intake.cancel_intake(chat_id)
    hunt_intake.start_hunt_intake(chat_id, prefill={"title": "ML in education"})
    progress = hunt_intake.intake_progress_text(chat_id)
    assert "research_type" in progress
    assert "Step 1/14" in progress
    # Complete it (skip 13 optional, type title)
    hunt_intake.skip_intake_step(chat_id)
    hunt_intake.record_intake_answer(chat_id, "ML in education")
    for _ in range(12):
        hunt_intake.skip_intake_step(chat_id)
    progress = hunt_intake.intake_progress_text(chat_id)
    assert "complete" in progress
    print(f"[test] intake_progress_text: PASS")
    return True


def test_get_answers_fills_defaults():
    """Even mid-intake, get_intake_answers should return defaults for unanswered (v6.7)."""
    chat_id = 99006
    hunt_intake.cancel_intake(chat_id)
    hunt_intake.start_hunt_intake(chat_id, prefill={"title": "Test"})
    # Just record the title
    hunt_intake.skip_intake_step(chat_id)  # skip research_type
    hunt_intake.record_intake_answer(chat_id, "Test")
    # Don't answer the rest
    answers = hunt_intake.get_intake_answers(chat_id)
    # Should have defaults filled in for the v6.7 set
    assert answers.get("research_type") == "general"
    assert answers.get("title") == "Test"
    assert answers.get("field") == "general"
    assert answers.get("rq_angle") == "empirical"
    assert answers.get("research_questions") == "auto"
    assert answers.get("year_range") == "any"
    assert answers.get("language") == "en"
    assert answers.get("country") == "world"
    assert answers.get("paper_type") == "all"
    assert answers.get("quartile_filter") == "any"
    assert answers.get("open_access") == "no"
    assert answers.get("platforms") == "all"
    assert answers.get("max_papers") == "1000"
    assert answers.get("download_pdfs") == "yes"
    print(f"[test] get_answers_fills_defaults: PASS")
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("  hunt_intake unit tests")
    print("=" * 60)
    test_start_and_complete()
    test_skip_uses_defaults()
    test_cannot_skip_required()
    test_cancel_clears_state()
    test_intake_progress_text()
    test_get_answers_fills_defaults()
    print("=" * 60)
    print("  ALL TESTS PASSED")
    print("=" * 60)
