import sys, os, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from academic_learning_database import AcademicLearningDatabase, WorkflowConfig

parser = argparse.ArgumentParser()
parser.add_argument('--fallback', action='store_true')
args = parser.parse_args()

print("\nInitializing Academic Learning System...")

db = AcademicLearningDatabase()
db.init_study_types()

field_map = {
    '1 - Applied Linguistics': '1. Applied Linguistics',
    '2 - Education': '2. Education',
    '3 - Psychology': '3. Psychology',
    '4 - Computer Science': '4. Computer Science',
    '5 - Medicine': '5. Medicine',
    '6 - Sociology': '6. Sociology',
    '7 - Economics': '7. Economics',
    '8 - Political Science': '8. Political Science',
    '9 - Engineering': '9. Engineering',
    '10 - History': '10. History',
}
paper_type_map = {
    '1 - Research Article': 'research_article',
    '2 - Systematic Review': 'systematic_review',
    '3 - Thesis Master': 'thesis_master',
    '4 - Thesis PhD': 'thesis_phd',
    '5 - Conference Paper': 'conference_paper',
    '6 - Literature Review': 'literature_review',
}
lang_map = {
    '1 - English': 'en',
    '2 - Arabic': 'ar',
    '3 - French': 'fr',
    '4 - Spanish': 'es',
    '5 - German': 'de',
}

config = WorkflowConfig(
    research_topic=os.environ.get('INPUT_TITLE', 'AI in Education'),
    academic_field=field_map.get(os.environ.get('INPUT_FIELD', '1 - Applied Linguistics'), '1. Applied Linguistics'),
    publication_type=paper_type_map.get(os.environ.get('INPUT_PAPER_TYPE', '1 - Research Article'), 'research_article'),
    study_level='any',
    methodology=os.environ.get('INPUT_METHODOLOGY', 'any'),
    language=lang_map.get(os.environ.get('INPUT_LANGUAGE', '1 - English'), 'en'),
    year_range=os.environ.get('INPUT_YEAR_RANGE', '2020-2026'),
    quartile_filter='all',
    search_mode='standard',
    output_format='all',
)

print(f"Configuration:")
print(f"  Topic: {config.research_topic}")
print(f"  Field: {config.academic_field}")
print(f"  Type: {config.publication_type}")
print(f"  Language: {config.language}")

template = (
    f"# {config.research_topic}\n\n"
    f"## Abstract\n\n[Generated based on workflow inputs]\n\n"
    f"## Introduction\n\n## Literature Review\n\n## Methodology\n\n"
    f"## Results\n\n## Discussion\n\n## Conclusion\n\n## References\n"
)

paper = None
if not db.ollama.available:
    if args.fallback:
        print("\nOllama not available - generating basic paper structure...")
        paper = template
    else:
        print("\nOllama not available - paper generation requires Ollama")
        sys.exit(1)
else:
    print("\nOllama connected - generating paper...")
    paper = db.generate_research_paper(config, reference_papers=None)

if paper is None:
    print(f"\nGeneration failed: no output")
    sys.exit(1)

if not args.fallback:
    if paper.startswith('Error'):
        print(f"\nGeneration failed: {paper}")
        sys.exit(1)

if args.fallback and paper.startswith('Error'):
    print(f"\nOllama error, using template: {paper}")
    paper = template

print(f"\nPaper generated ({len(paper)} characters)!")
with open('generated_paper.md', 'w', encoding='utf-8') as f:
    f.write(f"# {config.research_topic}\n\n")
    f.write(f"**Academic Field:** {config.academic_field}\n")
    f.write(f"**Paper Type:** {config.publication_type}\n")
    f.write(f"**Language:** {config.language}\n")
    f.write(f"**Generated:** {__import__('datetime').datetime.utcnow().isoformat()}Z\n\n")
    f.write("---\n\n")
    f.write(paper)

print("Saved to: generated_paper.md")
print("\n" + "="*60)
print("PREVIEW (first 1000 characters):")
print("="*60)
print(paper[:1000])
print("="*60)
