# Closely AI - Evidence Maturity Model

*Status: **EVOLVING** (Updated as new testing methods are added to the pipeline).*

---

## Evidence Maturity Model

To prevent overstating system maturity, we require all engineering claims to be backed by a specific level of verification. We grade evidence quality across seven distinct levels:

| Level | Grade | Verification Method & Artifact |
|---|---|---|
| **E0** | Design | Theoretical architecture, design specifications, RFCs, and code plans. |
| **E1** | Unit Tests | Code-level regression checks running automatically in CI pipelines. |
| **E2** | Integration Tests | Multi-module interaction flows running automatically in CI. |
| **E3** | Emulator Validation | Simulated traffic profiles and synthetic conversation replays. |
| **E4** | Pilot Validation | Direct feedback, logs, and trace telemetry from active design partner stores. |
| **E5** | Production Validation | Real-world usage data, cost telemetry, and performance metrics from live customers. |
| **E6** | Long-Term Evidence | Multi-month operational performance, cost stability, and system maintenance metrics. |

---

## Current Status Alignment (Pre-Pilot Gate)

As a team, we must maintain strict alignment on our current maturity level. 

Based on current engineering outputs, our evidence supports statements such as:
* ✓ Offline validation complete (E3).
* ✓ Emulator and replay testing complete (E3).
* ✓ Deterministic replay verified (E3).
* ✓ Chaos scenarios exercised (E3).
* ✓ Documentation and operational playbooks prepared (E0).

Our evidence does **NOT** currently support claims of:
* ✗ Production readiness (requires E5).
* ✗ Enterprise readiness (requires E5/E6).
* ✗ Market validation (requires E4/E5).
* ✗ Product-market fit (requires E6).

This taxonomy must be respected in all internal updates, dashboard metrics, and investor decks.
