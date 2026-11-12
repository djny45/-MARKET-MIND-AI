# Local AI-harness development

## Decision

MARKET-MIND-AI is to be developed and run locally through an AI coding harness (for example, Claude Code, Codex, or another compatible agent). A public website, hosted app, and hosted database are not part of the current target.

The existing React interface is a browser-rendered workstation UI that can be run on the developer's own machine. It is not a native ANSI terminal application. If the product requirement changes to a true terminal TUI, treat that as a separate UI implementation and use terminal-native components rather than browser animation libraries.

## Local-only operating model

- The coding harness edits the checked-out repository; it is not the application runtime.
- The app is started locally using the repository's documented development commands.
- Keep local development services bound to loopback. Do not expose the API to a public network.
- Do not provision or connect a hosted database. Existing local SQLite storage may remain for features that need persistence; it stays on the local machine and is not a cloud database.
- Do not add Vercel, Pages, or another public deployment as a required step.
- Keep credentials out of source control and use local environment files that are ignored by Git.
- Keep the product within the existing research-only scope. No brokerage connections, order routing, or automated transaction execution.

## Motion AI Kit

Motion AI Kit is an optional assistant for coding agents. It provides current Motion documentation/context and an agent skill/MCP integration. The free installer and skill are open source; the official installation command is:

```bash
npx motion-ai
```

Official guide: https://motion.dev/docs/ai-kit-install

Choose the project-local installation and the coding harness in use. Do not install Motion+ or add subscription credentials as part of the free setup.

Important distinction:

1. **Motion AI Kit** helps the coding agent author and review animation code.
2. **Motion runtime** is the JavaScript package used by a React/browser interface. If an approved UI task needs it, the package is named `motion` and is installed separately with the project's package manager.
3. **Native terminal UI** is not a browser DOM. Motion's React/browser animation runtime does not animate ANSI terminal widgets.

The current frontend is React-based, so Motion may be used for optional panel transitions, chart reveal states, and small interaction feedback. Keep animation subtle, preserve keyboard responsiveness, and honor `prefers-reduced-motion`. Do not animate numerical values in a way that changes their meaning or makes updates hard to inspect.

Free vs paid: the free AI Kit covers documentation/context search and the open-source `/motion` skill. Motion+ adds premium examples and additional tools. The project must remain usable without paid Motion+ features.

## Recommended harness task sequence

1. Read root `AGENTS.md` and this guide.
2. Inspect current branch, working tree, frontend structure, and existing test coverage.
3. Propose a short implementation plan before broad UI changes.
4. Implement one screen or component slice at a time.
5. Add tests for keyboard navigation, loading/error/empty states, and reduced-motion behavior where relevant.
6. Run frontend tests and production build, plus relevant backend tests for API changes.
7. Verify the application starts locally and that no public deployment or remote database is required.
8. Report the exact commit, files changed, commands run, test results, and unresolved issues.

## Local verification

From the repository root:

```bash
cd frontend
npm install
npm test
npm run build
```

Backend checks should follow the current repository instructions and use the configured local environment. Do not invent test results when the required runtime is unavailable.
