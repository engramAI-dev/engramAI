# Contributing

Thanks for your interest in contributing to Engram AI.

## Development workflow

1. Fork the repository.
2. Create a feature branch.
3. Keep changes focused and small.
4. Add or update tests for behavior changes.
5. Run the relevant checks before opening a pull request.

## Backend checks

```bash
cd backend
ruff check .
pytest
```

## Frontend checks

```bash
cd frontend
npm run lint
npm test
```

## Pull requests

A good pull request includes:

- a clear description of the problem and solution
- screenshots for UI changes
- tests or a note explaining why tests were not added
- any setup or migration notes

## Security

Do not include secrets, tokens, private keys, customer data, or private repository content in issues, pull requests, tests, or screenshots.
