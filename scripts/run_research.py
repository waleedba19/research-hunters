import sys, os, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from research_hunter_system import ResearchHunterSystem, WorkflowConfig

parser = argparse.ArgumentParser()
parser.add_argument('--title', default='Research Topic')
parser.add_argument('--field', default='auto')
parser.add_argument('--paper-type', default='article')
parser.add_argument('--language', default='1')
parser.add_argument('--save', action='store_true', help='Save generated paper to file')
args = parser.parse_args()

system = ResearchHunterSystem()
config = WorkflowConfig(
    research_topic=args.title,
    academic_field=args.field,
    publication_type=args.paper_type,
    study_level='any',
    methodology='any',
    language=args.language,
    year_range='2020-2026',
    quartile_filter='all',
    search_mode='standard',
    output_format='all'
)

print(f"\nGenerating paper: {config.research_topic}")
print(f"   Type: {config.publication_type}")
print(f"   Language: {config.language}")

paper = system.generate_paper(config)

if paper:
    print(f"\nPaper generated ({len(paper)} characters)")
    print("\n" + "="*60)
    print("PREVIEW (first 1000 chars):")
    print("="*60)
    print(paper[:1000])
    print("="*60)
    if args.save:
        with open('generated_paper.md', 'w') as f:
            f.write(f"# {config.research_topic}\n\n")
            f.write(f"**Type:** {config.publication_type}\n")
            f.write(f"**Field:** {config.academic_field}\n")
            f.write(f"**Language:** {config.language}\n\n")
            f.write("---\n\n")
            f.write(paper)
        print("Saved to: generated_paper.md")
else:
    print("Paper generation requires Ollama")
