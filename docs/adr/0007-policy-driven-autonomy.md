# ADR 0007: Policy-Driven Autonomy and PCAR Optimization

## Context
Targeting a universal "99% autonomous resolution rate" as a hard metric for all merchants forces the AI to handle risky situations (high-value orders, custom return claims) autonomously, which compromises safety. Different boutique stores have different risk profiles.

## Decision
Transition to a **Policy-Driven Autonomy** model where success is evaluated via **Policy-Compliant Autonomous Resolution (PCAR)**.
* Define our system objective as: *"The AI should autonomously handle every conversation that can be completed safely under merchant policy."*
* Handoff to human operators for out-of-policy requests is classified as a correct and safe system operation, rather than a failure of autonomy.

## Alternatives Considered
* **Hard Autonomy Targets (e.g. 99%)**: Rejected because it incentivizes developers to weaken safety rules to satisfy numeric quotas.

## Consequences
* Safe and predictable system behavior that matches individual merchant risk tolerances.
* The system dashboard measures PCAR directly from live telemetry, validating policy alignment.

## Status
Accepted
