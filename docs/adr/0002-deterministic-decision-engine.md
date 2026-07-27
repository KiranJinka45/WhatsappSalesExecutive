# ADR 0002: Deterministic Decision Engine Before Generative Model

## Context
Generative models (such as Gemini or OpenAI APIs) are highly conversational but prone to hallucinating factual errors like price discounts, return policies, or inventory availability. In commerce, these errors violate merchant policies and erode trust.

## Decision
Route conversational AI responses through a **Deterministic Decision Engine** prior to dispatching messages to the customer. If the intent dictates a transaction, shipping rule, or pricing check:
1. Query Postgres database.
2. Evaluate rules deterministically.
3. Reject or modify the generative prompt/output if it deviates from verified data.
4. Escalates out-of-policy intents to the Human Approval Queue.

## Alternatives Considered
* **Generative RAG Only**: Rejected because context parsing can still fail, allowing the LLM to invent numbers.
* **Fine-Tuning**: Rejected because model weights cannot update in real-time as prices and stock fluctuate.

## Consequences
* High safety and trust bounds.
* 0% hallucination rate on inventory numbers and product prices.
* Slightly higher code complexity to verify rules before generation.

## Status
Accepted
