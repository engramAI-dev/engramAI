# Contributing

Thanks for your interest in contributing to Engram AI.

## Development Workflow

1. Fork the repository.
2. Create a focused branch from the latest `main`.
3. Keep changes small and scoped to one concern.
4. Add or update tests for behavior changes.
5. Run the relevant checks before opening a pull request.
6. Fill out the pull request template.

## Pull Request Titles

Use a short bracketed prefix so maintainers can scan the PR list quickly.

Recommended prefixes:

- `[DOCS]` for documentation-only changes
- `[BUGFIX]` for bug fixes
- `[FEATURE]` for new functionality
- `[REFACTOR]` for code changes with no intended behavior change
- `[TEST]` for test-only changes
- `[INFRA]` for CI, packaging, dependency, or developer-experience changes

Format:

```text
[PREFIX] Short imperative summary (#issue-number)
```

Examples:

```text
[DOCS] Improve open-source onboarding (#12)
[BUGFIX] Handle empty retrieval results (#34)
[FEATURE] Add MCP document lookup filters (#56)
```

If there is no tracking issue, omit the issue number from the title. If there is a tracking issue, also link it in the PR body with `Closes #123` or `Fixes #123` so GitHub can close it automatically when the PR merges.

## Pull Requests

A good pull request includes:

- a clear description of the problem and solution
- the related issue number, discussion, or context
- screenshots for UI changes
- tests or a note explaining why tests were not added
- any setup, migration, or compatibility notes

## Backend Checks

```bash
cd backend
ruff check .
pytest
```

## Frontend Checks

```bash
cd frontend
npm run lint
npm run test:run
```

## Security

Do not include secrets, tokens, private keys, customer data, or private repository content in issues, pull requests, tests, or screenshots.