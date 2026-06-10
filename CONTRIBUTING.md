# Contributing to Research Hunter

Thank you for your interest in contributing to Research Hunter! This document provides guidelines and instructions for contributing.

---

## 🎯 Ways to Contribute

- 🐛 **Bug Reports** — Report bugs or issues
- ✨ **Feature Requests** — Suggest new features
- 📖 **Documentation** — Improve or expand docs
- 💻 **Code Contributions** — Submit pull requests
- 🧪 **Testing** — Help test new features
- 🌍 **Translations** — Help translate the tool

---

## 🚦 Before You Start

1. **Check existing issues** — Avoid duplicating work
2. **Fork the repository** — Create your own copy
3. **Create a branch** — Work on features separately
4. **Read the code style** — Follow our conventions

---

## 🛠️ Development Setup

### Prerequisites

- Python 3.12+
- Node.js 20+
- Git

### Setup Steps

```bash
# 1. Fork the repository on GitHub

# 2. Clone your fork
git clone https://github.com/YOUR_USERNAME/research-hunters.git
cd research-hunters

# 3. Add upstream remote
git remote add upstream https://github.com/waleedba19/research-hunters.git

# 4. Install dependencies
pip install -r requirements.txt
npm install

# 5. Create a branch
git checkout -b feature/your-feature-name
```

### Running Locally

```bash
# Test the main script
python research_hunter_v2-4.py --help

# Generate a test report
node generate_report.js test_data.json test_report.docx
```

---

## 📐 Code Style Guidelines

### Python

- Follow PEP 8 style guidelines
- Use type hints where appropriate
- Write docstrings for functions and classes
- Maximum line length: 100 characters
- Use meaningful variable names

### JavaScript

- Use ES6+ features
- Consistent indentation (2 spaces)
- Descriptive function names
- Comment complex logic

### General

- Keep functions focused and small
- Avoid deeply nested code
- Write self-documenting code
- Remove debug statements before committing

---

## 📝 Commit Messages

Follow this format:

```
type(scope): short description

[optional body with details]

[optional footer with issue references]
```

### Types

| Type | Description |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation changes |
| `style` | Formatting, no code change |
| `refactor` | Code restructuring |
| `test` | Adding tests |
| `chore` | Maintenance tasks |

### Examples

```bash
feat(platforms): add Semantic Scholar API integration
fix(download): handle timeout errors in PDF retrieval
docs(readme): update installation instructions
refactor(scopus): improve quartile matching algorithm
```

---

## 🔍 Pull Request Process

### 1. Before Submitting

- [ ] Code follows style guidelines
- [ ] Tests added/updated (if applicable)
- [ ] Documentation updated
- [ ] Commits are clean and descriptive
- [ ] Branch is up-to-date with main

### 2. Submitting

1. Push to your fork: `git push origin feature/your-feature`
2. Open a Pull Request on GitHub
3. Fill in the PR template:
   - **Description**: What does this change?
   - **Related Issues**: Link any issues
   - **Testing**: How was it tested?

### 3. Review Process

- Maintainers will review your PR
- Address feedback constructively
- Once approved, maintainers will merge

---

## 🐛 Reporting Bugs

Use the GitHub Issues template:

```markdown
## Bug Description
[Clear description of the bug]

## Steps to Reproduce
1. Go to '...'
2. Click on '...'
3. See error

## Expected Behavior
[What you expected to happen]

## Actual Behavior
[What actually happened]

## Environment
- OS: [e.g., Ubuntu 22.04]
- Python: [e.g., 3.12]
- Node.js: [e.g., 20.x]

## Additional Context
[Any other relevant information]
```

---

## 💡 Suggesting Features

Open a Feature Request issue with:

```markdown
## Feature Summary
[One paragraph summary]

## Problem Solved
[What problem does this solve?]

## Proposed Solution
[How should it work?]

## Alternatives Considered
[Other approaches considered]

## Use Cases
[Specific use cases for the feature]
```

---

## 🧪 Testing Guidelines

### What to Test

- ✅ New features
- ✅ Bug fixes
- ✅ Edge cases
- ✅ Error handling

### How to Test

```bash
# Run existing tests (when available)
python -m pytest tests/

# Manual testing
python research_hunter_v2-4.py --title "Test Topic" --mode sample
```

---

## 📋 Documentation Standards

- Use clear, concise language
- Include code examples
- Explain "why" not just "what"
- Keep docs up-to-date with code
- Add comments for complex logic

---

## 🔒 Security Considerations

- Never commit secrets or API keys
- Use environment variables for sensitive data
- Follow responsible disclosure for security issues
- Validate all user input

---

## 📜 License

By contributing, you agree that your contributions will be licensed 
under the MIT License. See [LICENSE](LICENSE) for details.

---

## 🙏 Thank You!

Your contributions make Research Hunter better for everyone. 
Every contribution, no matter how small, is valued.

---

**Questions?** Open an issue on GitHub for assistance.