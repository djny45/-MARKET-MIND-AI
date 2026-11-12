# Claude Code instructions

Read `AGENTS.md` before working. It is the repository-wide source of truth for scope, safety, provenance, and permissions.

## Product direction
- Develop and run the product locally through Claude Code, Codex, or another compatible coding harness.
- A public website, hosted app, and hosted database are not part of the current target.
- The existing React interface is a browser-rendered workstation UI intended to run locally; it is not a native ANSI terminal application.
- Do not provision or connect a third-party database. Existing local SQLite persistence may remain only where existing features require it.
- Keep development services bound to loopback. Do not deploy, publish, or expose services publicly without explicit authorization.
- Treat worker profiles as reusable modules sharing one intelligence core, not hundreds of independent models.
- Preserve the repository's research-only boundary. Do not add brokerage integrations, order routing, automated execution, or live trade instructions.

## Agent workflow
1. Inspect git status, current branch, and recent commits.
2. Read `AGENTS.md` and only the task-specific playbook under `.agents/skills/rea/`.
3. Trace existing interfaces and tests before designing new abstractions.
4. Make the smallest coherent change; avoid unrelated rewrites.
5. Add regression tests for behavior changes and update relevant docs.
6. Run focused tests first, then required full checks when practical.
7. Report exact commands, results, skipped checks, and limitations. Never claim a test or deployment ran unless its output was observed.
8. Do not merge, publish, deploy, or alter secrets without explicit authorization.

## Motion guidance
- Motion AI Kit is an optional coding-agent aid for React/browser animation. The free skill/MCP installer is documented at https://motion.dev/docs/ai-kit-install and uses `npx motion-ai`.
- Motion AI Kit is not the Motion runtime and does not animate native terminal widgets.
- For React UI animation, consult current Motion docs and add the `motion` runtime dependency only when an approved UI task requires it.
- Keep the free setup optional. Do not add paid Motion+ dependencies or credentials.
- Prefer restrained motion, preserve keyboard responsiveness, and honor `prefers-reduced-motion`.
- If the product requirement becomes a native TUI, use terminal-native components rather than React Motion.

## Local verification
Follow the commands in `docs/DEVELOPMENT.md` and the task-specific testing instructions. Local reproducibility and tests—not cloud deployment—are the acceptance baseline.
