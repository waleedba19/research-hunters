"""
Setup script for Research Hunter
Allows installation via: pip install research-hunter
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README for long description
readme_file = Path(__file__).parent / "README.md"
long_description = ""
if readme_file.exists():
    long_description = readme_file.read_text(encoding="utf-8")

# Read requirements
requirements_file = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_file.exists():
    requirements = [
        line.strip() 
        for line in requirements_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]

setup(
    name="research-hunter",
    version="6.0.0",
    author="Research Hunter Team",
    author_email="contact@researchhunter.dev",
    description="Academic research automation - search 70+ platforms for papers, download PDFs, and generate professional reports",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/waleedba19/research-hunters",
    project_urls={
        "Bug Reports": "https://github.com/waleedba19/research-hunters/issues",
        "Source": "https://github.com/waleedba19/research-hunters",
        "Documentation": "https://github.com/waleedba19/research-hunters#readme",
    },
    packages=find_packages(exclude=["tests", "tests.*", "docs"]),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: Information Analysis",
        "Topic :: Office/Business",
        "Topic :: Internet :: WWW/HTTP :: Indexing/Search",
        "Natural Language :: English",
        "Natural Language :: Arabic",
        "Natural Language :: French",
    ],
    python_requires=">=3.10",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "flake8>=6.0.0",
            "black>=23.0.0",
            "mypy>=1.0.0",
        ],
        "docs": [
            "sphinx>=6.0.0",
            "sphinx-rtd-theme>=1.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "research-hunter=research_hunter_v2-4:main",
        ],
        "gui_scripts": [
            "research-hunter-gui=generate_report:generate_report_gui",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.json", "*.txt"],
    },
    keywords=[
        "research",
        "academic",
        "papers",
        "pdf",
        "scopus",
        "quartile",
        "literature-review",
        "systematic-review",
        "search-engine",
        "bibliography",
        "citation",
        "scholar",
    ],
    license_files=["LICENSE"],
    zip_safe=False,
)