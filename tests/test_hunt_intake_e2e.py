"""
tests/test_hunt_intake_e2e.py — End-to-end test of the /hunt2 Telegram flow.

Simulates the user typing /hunt2 with a prefill, then clicking through the 5
inline keyboard buttons (or skipping), and verifies the intake reaches
completion and returns a properly-filled answers dict ready for the v2 pipeline.

Does NOT call the actual pipeline (no Ollama). Only the state machine.
"""
import os
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

# Use a temp STATE_DIR for isolation
TMP_DIR = tempfile.mkdtemp(prefix="hunt_intake_e2e_")
os.environ["STATE_DIR"] = TMP_DIR

import importlib
import telegram_bot  # noqa: E402
importlib.reload(telegram_bot)
import hunt_intake  # noqa: E402
importlib.reload(hunt_intake)


def test_e2e_hunt2_command():
    """Simulate: user types /hunt2 ML in education -> answers all 14 -> complete (v6.7)."""
    chat_id = 88001

    # Step A: /hunt2 command with prefill
    hunt_intake.start_hunt_intake(chat_id, prefill={"title": "ML in education"})
    assert hunt_intake.is_intake_active(chat_id)
    first_step = hunt_intake.get_current_intake_step(chat_id)
    assert first_step["key"] == "research_type", f"Expected research_type, got {first_step['key']}"
    print(f"[test] /hunt2 started; prefill applied; first step: {first_step['key']}")

    # Step 1: research_type
    hunt_intake.record_intake_answer(chat_id, "PhD", via="button")
    assert hunt_intake.get_current_intake_step(chat_id)["key"] == "title"

    # Step 2: title
    hunt_intake.record_intake_answer(chat_id, "ML in education", via="text")
    assert hunt_intake.get_current_intake_step(chat_id)["key"] == "field"

    # Step 3: field
    hunt_intake.record_intake_answer(chat_id, "education", via="button")
    assert hunt_intake.get_current_intake_step(chat_id)["key"] == "rq_angle"

    # Step 4: rq_angle
    hunt_intake.record_intake_answer(chat_id, "empirical", via="button")
    assert hunt_intake.get_current_intake_step(chat_id)["key"] == "research_questions"

    # Step 5: research_questions
    hunt_intake.record_intake_answer(chat_id, "auto", via="button")
    assert hunt_intake.get_current_intake_step(chat_id)["key"] == "year_range"

    # Step 6: year_range
    hunt_intake.record_intake_answer(chat_id, "any", via="button")
    assert hunt_intake.get_current_intake_step(chat_id)["key"] == "language"

    # Step 7: language
    hunt_intake.record_intake_answer(chat_id, "en", via="button")
    assert hunt_intake.get_current_intake_step(chat_id)["key"] == "country"

    # Step 8: country
    hunt_intake.record_intake_answer(chat_id, "world", via="button")
    assert hunt_intake.get_current_intake_step(chat_id)["key"] == "paper_type"

    # Step 9: paper_type
    hunt_intake.record_intake_answer(chat_id, "all", via="button")
    assert hunt_intake.get_current_intake_step(chat_id)["key"] == "quartile_filter"

    # Step 10: quartile_filter
    hunt_intake.record_intake_answer(chat_id, "any", via="button")
    assert hunt_intake.get_current_intake_step(chat_id)["key"] == "open_access"

    # Step 11: open_access
    hunt_intake.record_intake_answer(chat_id, "no", via="button")
    assert hunt_intake.get_current_intake_step(chat_id)["key"] == "platforms"

    # Step 12: platforms
    hunt_intake.record_intake_answer(chat_id, "tier1", via="button")
    assert hunt_intake.get_current_intake_step(chat_id)["key"] == "max_papers"

    # Step 13: max_papers
    hunt_intake.record_intake_answer(chat_id, "50", via="text")
    assert hunt_intake.get_current_intake_step(chat_id)["key"] == "download_pdfs"

    # Step 14: download_pdfs
    hunt_intake.record_intake_answer(chat_id, "yes", via="button")
    assert hunt_intake.is_intake_complete(chat_id)
    print(f"[test] Clicked yes -> intake COMPLETE (14/14)")

    # Verify all answers recorded correctly
    answers = hunt_intake.get_intake_answers(chat_id)
    assert answers["research_type"] == "PhD"
    assert answers["title"] == "ML in education"
    assert answers["field"] == "education"
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
    print(f"[test] Final answers: {answers}")
    return answers


def test_e2e_hunt2_via_skip():
    """Simulate: /hunt2 -> user clicks 'Skip' 13 times then types title -> complete (v6.7)."""
    chat_id = 88002

    hunt_intake.start_hunt_intake(chat_id)
    # Skip 1: research_type (default 'general')
    hunt_intake.skip_intake_step(chat_id, via="button")
    # Type title
    hunt_intake.record_intake_answer(chat_id, "Quantum computing", via="text")
    # Skip the remaining 12 steps (all have defaults)
    for _ in range(12):
        hunt_intake.skip_intake_step(chat_id, via="button")
    assert hunt_intake.is_intake_complete(chat_id)
    answers = hunt_intake.get_intake_answers(chat_id)
    expected = {
        "research_type": "general",
        "title": "Quantum computing",
        "field": "general",
        "rq_angle": "empirical",
        "research_questions": "auto",
        "year_range": "any",
        "language": "en",
        "country": "world",
        "paper_type": "all",
        "quartile_filter": "any",
        "open_access": "no",
        "platforms": "all",
        "max_papers": "1000",
        "download_pdfs": "yes",
    }
    assert answers == expected
    print(f"[test] Skip-only flow: PASS (12 skips + 1 type, all defaults filled)")


def test_e2e_hunt2_cancel_midway():
    """User starts intake, then /cancel — should clear state."""
    chat_id = 88003
    hunt_intake.start_hunt_intake(chat_id, prefill={"title": "Astrophysics"})
    hunt_intake.record_intake_answer(chat_id, "PhD")
    assert hunt_intake.is_intake_active(chat_id)
    # User cancels
    hunt_intake.cancel_intake(chat_id)
    assert not hunt_intake.is_intake_active(chat_id)
    # Restart with different topic
    hunt_intake.start_hunt_intake(chat_id, prefill={"title": "Renewable energy"})
    step = hunt_intake.get_current_intake_step(chat_id)
    assert step["key"] == "research_type"  # fresh start
    print(f"[test] Cancel + restart: PASS (state cleared, fresh intake started)")


def test_intake_progress_text_format():
    """Verify progress text shows step number and current state (v6.7: 14 steps)."""
    chat_id = 88004
    hunt_intake.start_hunt_intake(chat_id, prefill={"title": "Climate change"})
    progress = hunt_intake.intake_progress_text(chat_id)
    assert "Step 1/14" in progress
    assert "research_type" in progress
    # Answer one and verify step 2
    hunt_intake.record_intake_answer(chat_id, "PhD")
    progress = hunt_intake.intake_progress_text(chat_id)
    assert "Step 2/14" in progress
    assert "title" in progress
    print(f"[test] Progress text format: PASS (Step N/14 visible)")
    print()
    print("Sample progress text (no emoji, ASCII-safe):")
    print("-" * 40)
    print(progress.encode("ascii", "replace").decode("ascii"))


if __name__ == "__main__":
    print("=" * 60)
    print("  hunt_intake E2E (state machine only, no Ollama)")
    print("=" * 60)
    print()
    test_e2e_hunt2_command()
    print()
    test_e2e_hunt2_via_skip()
    print()
    test_e2e_hunt2_cancel_midway()
    print()
    test_intake_progress_text_format()
    print()
    print("=" * 60)
    print("  ALL E2E TESTS PASSED")
    print("=" * 60)
