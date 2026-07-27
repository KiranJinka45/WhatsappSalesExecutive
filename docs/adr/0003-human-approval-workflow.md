# ADR 0003: Human-in-the-Loop Approval Queue

## Context
Certain retail actions (discounts, refunds, complaint resolution) represent high financial risk or require human empathy. The AI cannot execute these workflows autonomously.

## Decision
Implement a **Human-in-the-Loop Approval Queue** integrated within the merchant dashboard console.
* Safe outputs go directly to WhatsApp.
* Risky outputs (L3/L4 tasks) are intercepted, paused, and placed in the Approval Queue.
* A notification is dispatched to the merchant.
* The merchant reviews, edits, approves, or rejects the message before it is sent to the customer.

## Alternatives Considered
* **Block Risky Requests Entirely**: Rejected as it hurts the customer experience (customer gets ignored).
* **Fully Autonomous Execution**: Rejected due to high risk of pricing or financial abuse.

## Consequences
* High merchant confidence and platform trust.
* Merchant actions act as training data to optimize conversational paths.
* Introduces message delay for flagged conversations while waiting in the queue.

## Status
Accepted
