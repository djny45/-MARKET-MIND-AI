# Local AI-harness development

## Product direction

MARKET-MIND-AI is to be developed and run locally through an AI coding harness such as Claude Code, Codex, or another compatible agent. A public website, hosted application, and hosted database are not part of the current target.

The existing interface is React-based and renders a browser workstation that can be run on the developer's own machine. It is not a native ANSI terminal UI. If a true terminal TUI is required later, treat it as a separate interface implementation and use terminal-native components.

## Local-only operating model

- The coding harness edits the checked-out repository; it is not the application runtime.
- Start the app locally using the repository's development commands.
- Bind development services to loopback and do not expose the API publicly.
- Do not provision or connect a hosted database. Existing SQLite storage may remain for features that require local persistence; it stays on the developer's machine.
- Do not make Vercel, Pages, or another public deployment a required step.
- Keep credentials out of source control and use ignored local environment files.
- Preserve the repository's research-only scope; no brokerage connection, order routing, or automated transaction execution.

## Motion AI Kit

Motion AI Kit is an optional assistant for coding agents. It provides current Motion documentation/context and an agent skill/MCP integration. The free installer and skill are open source. Install it from the repository root with:

```bash
npx motion-ai
```

Official guide: https://motion.dev/docs/ai-kit-install

Choose a project-local installation and the coding harness in use. Do not install Motion+ or add subscription credentials as part of the free setup.

Keep these three layers distinct:

1. **Motion AI Kit** helps the coding agent author and review animation code.
2. **Motion runtime** is a separate JavaScript package used by a React/browser interface. If a UI task actually needs it, the package is named `motion` and is installed separately.
3. **Native terminal UI** is not a browser DOM. Motion's React/browser runtime does not animate ANSI terminal widgets.

For the current React interface, Motion may be considered for subtle panel transitions and interaction feedback. Keep keyboard interaction immediate, respect `prefers-reduced-motion`, and avoid continuous decorative animation. The project must remain usable without paid Motion+ features.

## Recommended harness sequence

1. Read root `AGENTS.md` and this guide.
2. Inspect the current branch, working tree, frontend structure, and tests.
3. Propose a concise plan before broad UI changes.
4. Implement one screen/component slice at a time.
5. Add tests for keyboard navigation, loading/error/empty states, and reduced-motion behavior where applicable.
6. Run frontend tests and production build; run relevant backend tests for API changes.
7. Verify local startup and confirm no public deployment or remote database is required.
8. Report the exact commit, changed files, commands, test results, and unresolved issues.

## Frontend verification

From the repository root:

```bash
cd frontend
npm install
npm test
npm run build
```

Backend checks must follow current repository instructions and use the configured local environment. Do not invent results when the required runtime is unavailable.
