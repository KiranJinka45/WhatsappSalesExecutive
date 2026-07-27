# ADR 0001: Modular Strategic Governance

## Context
As Closely AI transitioned from a product vision to a broader operational platform, a single strategic file (`00_Vision_and_Strategy.md`) grew to 600+ lines. Maintaining engineering, business, and AI constraints in a single file created heavy editing overhead and raised the risk of strategic drift.

## Decision
Decompose the monolithic strategic file into ten modular files (`00` to `09`) grouped by function:
* Frozen documents: `00_Mission_Vision_Strategy.md` (Vision & Mission), `01_Product_Principles.md`, `02_AI_Constitution.md`, `03_Architecture_Principles.md`, `04_Engineering_Guardrails.md`.
* Evolving documents: `05_Product_Roadmap.md`, `06_AI_Quality_Framework.md`, `07_Evidence_Maturity_Model.md`, `08_Operational_Governance.md`, `09_Glossary.md`.
* A meta-rule document `10_Governance_Charter.md` controls access.

## Alternatives Considered
* **Keep monolithic file**: Rejected due to maintenance friction and poor readability.
* **Remove strategy docs entirely**: Rejected as it leaves no guardrails against scope creep.

## Consequences
* Clear separation of frozen principles vs. evolving roadmap.
* Drastically reduced document edit churn.
* Standardized links allow developers to query specific constraints easily.

## Status
Accepted
