## What changed

<!-- One or two sentences. Link the issue if there is one: Closes #123 -->

## Why

<!-- The failure or gap this addresses. If it is a bug, describe the reproduction. -->

## Evidence

<!-- Paste the command output that proves this works. "It should work" is not evidence. -->

```
$ 
```

- [ ] Backend tests pass: `PYTHONPATH=backend .venvs/backend/bin/python -m unittest discover -s backend/tests -q`
- [ ] Frontend tests pass: `cd frontend && npm test && npx vitest run`
- [ ] Typecheck / build clean: `cd frontend && npm run build`
- [ ] New behaviour has a test that fails without the change

## Boundary check

- [ ] This does not add broker execution, wallet keys, transaction signing, order routing or market making
- [ ] Any user-visible number is computed by deterministic code, not generated prose
- [ ] No secrets, credentials or private data are included in code, logs or fixtures

## Risk and rollback

<!-- What can this break, and how does an operator revert it? -->
