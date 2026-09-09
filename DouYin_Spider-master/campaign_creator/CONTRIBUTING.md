# Contributing to Multi-Agent Campaign Creator

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to the project.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/satyamshivam13/multi-agent-campaign-creator.git
   cd multi-agent-campaign-creator
   ```

3. **Create a virtual environment**:
   ```powershell
   py -3.11 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

4. **Install in development mode**:
   ```bash
   pip install -e ".[dev]"
   ```

## Making Changes

### Code Style
- Follow PEP 8 conventions
- Use type hints for function signatures
- Keep functions focused and well-documented

### Testing
- Write tests for new features
- Run the test suite before submitting:
  ```bash
  pytest tests/ -v
  ```
- Ensure tests pass on both Python 3.11 and 3.12

### Commits
- Use clear, descriptive commit messages
- Reference related issues when applicable
- Keep commits atomic (one feature/fix per commit)

## Submitting Changes

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** and commit them

3. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```

4. **Open a Pull Request** on GitHub with:
   - Clear description of changes
   - Reference to any related issues
   - Evidence that tests pass (GitHub Actions will run them)

## Areas for Contribution

We're looking for help with:

- **Retry logic** — Exponential backoff for Groq rate limits
- **LLM providers** — Support for Claude, OpenAI, Mistral, etc.
- **UI** — Web interface for campaign builder
- **Testing** — Additional test coverage and edge cases
- **Documentation** — Tutorials, examples, API docs
- **Integrations** — Canva, Figma, email platform connectors
- **Database** — Campaign history and analytics storage

## Questions or Issues?

- Open a GitHub issue for bugs
- Start a discussion for feature ideas
- Check existing issues before reporting duplicates

---

**Thank you for contributing!** 🚀
