# AI Evaluation Framework

## Purpose
This document defines the quantitative and qualitative evaluation methodology for the Closely AI product. We cannot rely solely on synthetic "happy paths" or engineering latency to prove Product-Market Fit (PMF). We must prove that the AI successfully drives revenue without hallucinating or damaging merchant trust.

## 1. Business Metrics (The Scorecard)
Every merchant pilot must be evaluated against the following scorecard, stored in `pilot/{merchant_id}/evaluation.md`.

**Quantitative Impact:**
- **Revenue Influenced (INR):** Total value of orders generated in conversations where the AI participated.
- **Orders Started:** Number of shopping carts initiated.
- **Orders Completed:** Number of successful payments.
- **Containment Rate (%):** Percentage of conversations resolved entirely by AI without human takeover.
- **Time Saved:** (Total AI messages * 2 minutes) = Estimated hours saved per employee.

**Qualitative AI Quality:**
- **Hallucination Rate:** Frequency of the AI offering non-existent products, incorrect prices, or impossible promises.
- **Recommendation Accuracy:** Did the retrieved products accurately match the user's intent, budget, and size?
- **Human Takeovers:** Number of times the customer requested a human or the AI triggered an escalation.

## 2. Conversation Goldens
To prevent regressions during engineering sprints, we maintain a suite of **Benchmark Conversations** (Goldens) in the `goldens/` directory.

### Golden Categories
1. `budget_search.json`: Enforces strict numerical filtering (e.g., "Under 2000").
2. `failure_out_of_stock.json`: Enforces graceful failure when inventory is zero. AI must NOT recommend out-of-stock items.
3. `angry_customer.json`: Enforces immediate escalation and empathetic tone matching.
4. `human_takeover.json`: Validates that specific trigger phrases halt the AI.

### Execution Process
Before any new backend release, the `tests/test_goldens.py` suite must run.
- **Input:** Customer message sequence.
- **Expected Output:** The exact Intent, Entity payload, and a bounded set of expected SKUs.
- **Threshold:** 100% pass rate is required for Intent, Entity Extraction, and Policy validation.

## 3. Explainability (Merchant Trust)
Merchants will only trust the AI if they understand *why* it made a recommendation.

The AI Pipeline now includes a **Recommendation Ranker**, and the final output must log:
- **Confidence Score**
- **Retrieved Products (Raw Semantic Matches)**
- **Rejected Products (Filtered by Validator due to price/stock)**
- **Final Recommended Products (Ranked by margin/relevance)**

This metadata is stored in the `Message.metadata_` column and will eventually be surfaced in the Merchant Dashboard UI.
