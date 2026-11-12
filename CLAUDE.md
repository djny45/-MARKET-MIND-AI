# Claude Code instructions

This repository is developed locally through an AI coding harness such as Claude Code, Codex, or another compatible agent. Read `AGENTS.md` first; it is the repository-wide source of truth for scope, safety, provenance, and permissions.

## Product direction

- Build and run the product locally. Do not create or deploy a public website, hosted application, or hosted database unless the owner explicitly changes this requirement.
- Treat the current React interface as a local-only workstation UI, not a public website. Bind development services to loopback where practical.
- Do not add a third-party database service. Preserve local persistence only where an existing feature requires it; do not transmit user data to a cloud database.
- Keep the user-facing experience focused on a professional, keyboard-friendly research workstation.
- Keep the 550 worker profiles as configurations/modules sharing one intelligence core. Do not represent them as 550 independent models or claim they are continuously running.
- Preserve the repository's research-only boundary. Do not add brokerage integrations, order submission, automated execution, or live trade instructions.

## Agent workflow

1. Inspect `git status`, current branch, and recent commits before editing.
2. Read `AGENTS.md` and only the task-specific playbook under `.agents/skills/rea/` that matches the work.
3. Trace existing interfaces and tests before designing new abstractions.
4. Make the smallest coherent change. Do not rewrite unrelated modules or replace working components without evidence.
5. Add regression tests for behavior changes and update the relevant documentation.
6. Run the focused test suite first, then the repository's full required checks when practical.
7. Report exact commands, pass/fail outcomes, skipped checks, and remaining limitations. Never claim a test or deployment ran unless its output was observed.
8. Do not merge, publish, deploy, or alter secrets without explicit authorization.

## UI and Motion guidance

- Motion AI Kit is an optional coding-agent aid for React/browser animation. Its free skill/MCP installation is documented at https://motion.dev/docs/ai-kit-install and uses `npx motion-ai`.
- The AI Kit is not the Motion runtime and does not turn a native terminal into an animated UI. For React UI animation, consult current Motion docs and add the `motion` runtime dependency only when an approved UI task actually needs it.
- Keep Motion AI Kit optional; do not add paid Motion+ dependencies or credentials.
- Prefer restrained, purposeful motion: short transitions, reduced-motion support, no continuous decorative animation, and no animation that delays access to data or keyboard controls.
- If the product requirement is a native terminal/TUI (ANSI terminal), use a terminal-native UI stack; do not add React Motion to that layer.

## Local development

Use the commands in `docs/DEVELOPMENT.md` and the relevant test instructions in the repository. Do not assume a cloud deployment is part of acceptance. The expected acceptance path is a reproducible local run, tests, and documented setup.
