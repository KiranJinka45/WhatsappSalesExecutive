# ADR 0006: Offline Meta API Emulator for Verification Testing

## Context
Developing and validating conversational pathways directly against Meta's live API introduces network latency, high API invocation costs, and rate limits. It also makes automated integration testing in CI pipelines slow and unreliable.

## Decision
Develop an **Offline Meta API Emulator** for local development and CI testing.
* Emulate incoming user messages, interactive button clicks, and media payloads in a mock HTTP server.
* Capture and assert outbound payloads sent to Meta to verify response correctness.
* Enable testing of chaos scenarios, drop-offs, and network retry errors deterministically.

## Alternatives Considered
* **Live Sandbox Verification**: Rejected due to speed, lack of mock state reproducibility, and rate limiting issues.

## Consequences
* Rapid, high-fidelity local developer loop.
* Automated CI pipeline execution takes seconds instead of minutes.
* Developers must keep the emulator mock schemas synchronized with Meta Cloud API updates.

## Status
Accepted
