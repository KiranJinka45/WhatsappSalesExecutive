# Closely AI - Product Principles

*Status: **FROZEN** (Stable; changes require formal company-level review).*

---

## Core Values

These core values guide our product, engineering, and hiring practices:

* **Truth over Marketing**: We build on verifiable capability and actual metrics, not AI hype.
* **Customer Evidence over Assumptions**: Strategy and product roadmaps are guided strictly by real merchant usage.
* **Security by Default**: Multi-tenancy and data isolation are non-negotiable architectural requirements.
* **Human Trust First**: AI is a coworker, meaning safety, explanation, and reversibility override speed.
* **Operational Excellence**: High uptime, low latency, and robust observability are engineering baselines.
* **Continuous Learning**: We optimize the system continuously based on developer, merchant, and user feedback loops.
* **Long-term Thinking**: We make decisions that keep the codebase maintainable and the architecture scalable over years.

---

## Decision-Making Framework

When goals conflict, teams must evaluate options using this strict prioritization list:

### Decision Hierarchy

1. **Customer Safety**: Prevent hallucinated pricing, data leaks, or policy violations above all else.
2. **Customer Trust**: Ensure explainability, clarity of AI status, and consistent behaviour.
3. **Merchant Value**: Build features that directly save time or grow revenue for the boutique.
4. **Product Simplicity**: Keep the merchant dashboard and customer interactions clean and focused.
5. **Operational Reliability**: Maintain high service availability, monitoring, and error containment.
6. **Engineering Elegance**: Clean, well-tested code that adheres to standard layers.
7. **Speed of Delivery**: Fast shipping is important, but must not compromise safety or architecture.

*Example*: If shipping a feature faster requires skipping safety/emulation verification, the safety check wins.

---

## Product Principles

1. **AI First**
   The AI performs the work whenever it is safe.
2. **Human Always Has Final Authority**
   Business-critical actions remain merchant controlled.
3. **Evidence Over Assumptions**
   Roadmap decisions come from production evidence.
4. **Deterministic Before Generative**
   Business policies are enforced with deterministic rules.
5. **Multi-Tenant By Default**
   Every merchant is isolated.
6. **Observability Everywhere**
   Every decision must be traceable.
7. **Safe Automation**
   Automation must always be reversible.

---

## Product Positioning

Instead of describing the product as an:
> AI WhatsApp Chatbot

We communicate business value:
> **An AI Sales Employee that sells, assists customers, and works 24×7 for your clothing business.**

---

## Competitive Moat

Our moat is not LLM model selection or simple RAG. Defensibility comes from:

* **Merchant-Specific Knowledge**: Rich, highly structured business contexts and proprietary merchant data.
* **Deterministic Decision Engine**: Strict compliance with business policies paired with conversational flexibility.
* **Human Approval Workflow**: A seamless merchant handoff loop that functions as an interactive training pipeline.
* **Continuous Learning**: System performance improvements driven by merchant edits and overrides.
* **Multi-Tenant Governance**: Ironclad isolation, data compliance, and enterprise-grade policy controls.
* **Operational Evidence & Auditability**: Deeply traceable logic, logs, and decision trees for every customer message.
* **Commerce-Specific Workflows**: Native integrations with inventory, cart state, recommendations, and checkout lifecycles.
* **Data Network Effects**: Shared learnings (e.g., general intent models, catalog schemas) that benefit all tenants while keeping individual merchant data completely private.
