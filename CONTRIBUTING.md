# Contributing to Ohmni Oracle Template

Thank you for considering contributing to the Ohmni Oracle Template project!

## Development Setup

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Install development dependencies:
   ```bash
   pip install pre-commit black ruff mypy
   ```
4. Install pre-commit hooks:
   ```bash
   pre-commit install
   ```

## Code Style

This project uses:
- Black for code formatting
- Ruff for linting
- MyPy for type checking

## Pull Request Process

1. Fork the repository
2. Create a feature branch
3. Add tests for your changes
4. Ensure all tests pass
5. Submit a pull request

## Commit Message Format

Please use clear and descriptive commit messages with the following prefixes:

```
[Component]: Brief description

Detailed description
```

Example:
```
[Extraction]: Add support for custom table detection

This change adds support for custom table detection in PDF files, improving
extraction accuracy for complex layouts.
```

## Adding New Features

### When adding new features, please follow these guidelines:

1. **Add proper type hints** to all functions and methods
2. **Document your code** with docstrings in the Google style
3. **Add tests** for new functionality
4. **Update documentation** including README.md if necessary
5. **Use structured exceptions** from utils.exceptions for error handling
6. **Implement structured logging** using the StructuredLogger class

## Working with AI Services

When modifying AI service code:

1. **Add retry logic** for all API calls
2. **Consider caching options** if applicable
3. **Implement proper error handling** with structured exceptions
4. **Add performance metrics** where appropriate

## Security Guidelines

When working with sensitive data:

1. **Use the security utilities** in utils.security
2. **Never log sensitive information** directly; use sanitize_log_data
3. **Encrypt sensitive data** when storing to disk

## Testing

Run tests before submitting a pull request:

```bash
python -m unittest discover -s tests
```

Test the new features:

```bash
python -m test.test_refactoring
``` 