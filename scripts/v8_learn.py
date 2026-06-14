import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from academic_learning_database import AcademicLearningDatabase

print("\nLearning from papers...")

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

field = field_map.get(os.environ.get('INPUT_FIELD', '1 - Applied Linguistics'), '1. Applied Linguistics')

if not db.get_field_pattern(field):
    patterns = {
        '1. Applied Linguistics': {
            'common_methods': ['quantitative', 'qualitative', 'mixed_methods'],
            'key_concepts': ['language_acquisition', 'SLA', 'pragmatics'],
            'important_journals': ['TESOL Quarterly', 'Applied Linguistics'],
        },
        '2. Education': {
            'common_methods': ['quantitative', 'qualitative', 'action_research'],
            'key_concepts': ['pedagogy', 'curriculum', 'learning_outcomes'],
            'important_journals': ['Journal of Education', 'Educational Researcher'],
        },
    }

    if field in patterns:
        db.learn_field_pattern({
            'field_id': field,
            'field_name': field,
            **patterns[field],
            'structure_variations': [],
            'terminology': {},
            'style_notes': 'Empirical research preferred',
        })
        print(f"Learned pattern for: {field}")
    else:
        print(f"Pattern already exists or not in learning set: {field}")
else:
    print(f"Pattern already exists for: {field}")

stats = db.get_statistics()
print(f"\nDatabase stats:")
print(f"  Field patterns: {stats['field_patterns']}")
print(f"  Study types: {stats['study_types']}")

print("\nPhase 2 complete!")
