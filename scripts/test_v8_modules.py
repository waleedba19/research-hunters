import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from academic_learning_database import AcademicLearningDatabase
    db = AcademicLearningDatabase()
    db.init_study_types()
    stats = db.get_statistics()
    print(f"Learning Database: {stats['study_types']} study types")
except Exception as e:
    print(f"Learning DB: {e}")

try:
    from universal_document_processor import UniversalDocumentProcessor
    dp = UniversalDocumentProcessor()
    print(f"Document Processor: Available")
except Exception as e:
    print(f"Doc Processor: {e}")
