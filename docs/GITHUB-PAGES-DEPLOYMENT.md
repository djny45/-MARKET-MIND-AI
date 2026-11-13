# Public GitHub Pages deployment — not approved

> **Do not use this workflow to publish MARKET-MIND-AI as a public application.** The project is currently scoped to a private, single-host deployment. A static public frontend would expose the interface and API configuration to anyone who can access the Pages site; it is not a substitute for a reviewed production architecture.

## Current security boundary

The current branch implements single-owner authentication, default-deny API session middleware, CSRF/Origin protections, and SQLite-backed sessions for the private deployment. This is a meaningful improvement over the earlier unauthenticated API, but it is **not** a production security approval.

The following work remains necessary before any public deployment is considered:

- Independent security review and penetration testing.
- A reviewed TLS ingress and reverse-proxy configuration, including trusted-proxy boundaries.
- Production-grade rate limiting and operational monitoring.
- Host-specific backup/restore drills, retention, incident response, and migration rollback procedures.
- A documented authorization model if the application ever supports multiple users.

## Supported deployment

Use the private Docker deployment described in [PRODUCTION-DEPLOYMENT.md](PRODUCTION-DEPLOYMENT.md). Keep the frontend bound to loopback and the backend/database private to the Compose network. Do not expose the service to the public internet or a shared LAN.

## Historical note

This file previously described a GitHub Pages workflow and incorrectly stated that the API had no authentication. That description is obsolete. Any existing Pages workflow is not evidence of an approved deployment, a successful security review, or permission to expose the application publicly.

The product remains a research terminal: market data and analysis are read-only, and brokerage execution/order routing are out of scope.
