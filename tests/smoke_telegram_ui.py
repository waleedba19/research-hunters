"""Smoke test the new rich UI builders."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import telegram_ui


def main():
    print("=== MAIN MENU ===")
    print(f"  text length: {len(telegram_ui.MAIN_MENU_TEXT)} chars")
    print(f"  keyboard rows: {len(telegram_ui.main_menu_keyboard()['inline_keyboard'])}")
    print()

    print("=== REVIEW SCREEN (full answers) ===")
    answers = {
        "research_type": "PhD",
        "title": "Machine learning in higher education assessment",
        "research_questions": [
            "How does ML improve formative assessment?",
            "What ethical concerns arise from ML-based grading?",
            "How do students perceive AI feedback?",
        ],
        "year_range": "2020-2024",
        "platforms": "all",
        "max_papers": "500",
        "download_pdfs": "yes",
    }
    text, kb = telegram_ui.build_review_screen(answers)
    print(f"  text length: {len(text)} chars")
    print(f"  keyboard rows: {len(kb['inline_keyboard'])}")
    print(f"  keyboard buttons: {sum(len(r) for r in kb['inline_keyboard'])}")
    print()

    print("=== EDIT PANEL (download_pdfs) ===")
    text, kb = telegram_ui.build_edit_panel("download_pdfs", "yes")
    print(f"  text length: {len(text)}")
    print(f"  keyboard rows: {len(kb['inline_keyboard'])}")
    print()

    print("=== EDIT PANEL (max_papers) ===")
    text, kb = telegram_ui.build_edit_panel("max_papers", "1000")
    print(f"  text length: {len(text)}")
    print(f"  keyboard rows: {len(kb['inline_keyboard'])}")
    print()

    print("=== EDIT PANEL (title) ===")
    text, kb = telegram_ui.build_edit_panel("title", "old title")
    print(f"  text length: {len(text)}")
    print(f"  keyboard rows: {len(kb['inline_keyboard'])}")
    print()

    print("=== REPORTS (empty) ===")
    text, kb = telegram_ui.build_reports_list([])
    print(f"  text length: {len(text)}")
    print(f"  keyboard rows: {len(kb['inline_keyboard'])}")
    print()

    print("=== REPORTS (with data) ===")
    reports = [
        {"title": "ML in education", "date": "2026-06-07",
         "total_papers": 321, "downloaded": 158,
         "drive_url": "https://drive.google.com/folder/abc"},
        {"title": "Sustainable tourism", "date": "2026-06-05",
         "total_papers": 187, "downloaded": 90,
         "drive_url": ""},
    ]
    text, kb = telegram_ui.build_reports_list(reports)
    print(f"  text length: {len(text)}")
    print(f"  keyboard rows: {len(kb['inline_keyboard'])}")
    print()

    print("=== STEP LABELS ===")
    print(f"  {list(telegram_ui.STEP_LABELS.keys())}")
    print()

    print("=== HUNT SUMMARY ===")
    summary = telegram_ui.build_hunt_summary_text(
        {"title": "Test title", "research_type": "PhD", "year_from": 2020,
         "year_to": 2024, "platforms_key": "all", "max_papers": 500,
         "download_pdfs": True,
         "research_questions": ["RQ1?", "RQ2?", "RQ3?"]},
        {"total_papers": 321, "downloaded": 158, "red_list_count": 12,
         "elapsed_min": 23, "drive_folder_url": "https://drive.google.com/x",
         "results": {"run_stats": {"q_distribution": {"Q1": 50, "Q2": 100, "Q3": 120, "Q4": 51}},
                     "future_studies": ["s1", "s2", "s3"]}},
    )
    print(f"  text length: {len(summary)}")
    print()

    print("[OK] All UI builders work.")


if __name__ == "__main__":
    main()
