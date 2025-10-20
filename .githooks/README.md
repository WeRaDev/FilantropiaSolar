# Git Hooks for FilantropiaSolar

This directory contains Git hooks to ensure code quality before commits and pushes.

## Installation

To install the pre-push hook:

```bash
# From the project root directory
ln -sf ../../.githooks/pre-push .git/hooks/pre-push
```

## Available Hooks

### `pre-push`

Automatically runs before each `git push` to ensure:

- **Code formatting**: Runs `ruff format --check` and fixes issues if found
- **Lint checking**: Runs `ruff check` to catch code quality issues

If any check fails, the push is blocked until issues are resolved.

## Manual Usage

You can run the same checks manually:

```bash
# Format code
ruff format .

# Check for lint issues  
ruff check .

# Run both (recommended before committing)
ruff format . && ruff check .
```

## CI Integration

These same checks are also enforced in CI:

- `.github/workflows/ci-enhanced.yml` runs identical checks
- This ensures consistent code quality across all environments
- Local hooks prevent CI failures by catching issues early

## Bypassing Hooks (Not Recommended)

In emergencies, you can skip hooks with:

```bash
git push --no-verify
```

However, this is **strongly discouraged** as it bypasses quality gates that prevent CI failures.