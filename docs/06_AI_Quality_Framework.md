# Closely AI - AI Quality Framework

*Status: **EVOLVING** (Refined as measurement tools and evaluation metrics mature).*
*Version: **v1.1.0-draft***

---

## Balanced Operational Scorecard

To ensure we optimize for safety, quality, and merchant value in equilibrium (rather than focusing single-mindedly on a single metric), our primary scorecard tracks the following nine dimensions:

| Metric | Measurement Goal | Why it Matters | Target / SLA |
|---|---|---|---|
| **PCAR** | Policy-Compliant Autonomous Resolution rate. | Measures safe autonomous resolution of customer queries within defined rules. | Maximize within configured merchant policy |
| **Merchant Override Rate** | Number of AI drafts edited/rejected by the merchant in the approval queue. | Detects excessive AI confidence, incorrect suggestions, or poor recommendations. | ≤ 5% of queued messages |
| **False Escalation Rate** | Percentage of approval requests that the merchant immediately approves without modification. | Tunes safety thresholds. High rate means engine is too conservative (creates spam). Low rate means bot is under-escalating or generating poor drafts. | Should trend downward while maintaining zero policy violations and stable merchant satisfaction. Initial pilot baselines will determine the long-term target range. |
| **Approval Turnaround Time**| Time between message isolation to final merchant approval action. | Ensures the approval queue does not become a bottleneck that delays customer chats. | Median < 10 minutes |
| **Customer Satisfaction** | User-rated CSAT after a conversation completes. | Direct indicator of chat helpfulness and style relevance. | CSAT ≥ 4.7 / 5 |
| **Conversion Rate** | Clicks-to-purchase and conversation-to-order funnel. | Ultimate business outcome and revenue driver for the boutique. | Track and optimize per pilot wave |
| **Hallucination Incidents** | Real-world pricing, discount, policy, or inventory details invented by the LLM. | Non-negotiable safety guardrail; represents brand damage. | **0 incidents** (Zero tolerance) |
| **Production Uptime** | Platform API availability. | General engineering reliability. | ≥ 99.9% uptime |
| **p95 Latency** | Time from incoming user webhook to outgoing API message dispatch. | Conversational responsiveness. | < 2 seconds p95 |

---

## Target Operational Metrics

| Metric | Target | Verification Source |
|---|---|---|
| **Webhook Success Rate** | ≥99.9% | Server gateway log traces |
| **AI Hallucination Rate** | Zero-tolerance on core policies | Automated evaluator LLM sweeps against chat logs |
| **Merchant Retention** | ≥95% after initial pilot wave | Stripe/SaaS database subscription logs |

---

## Strategic Business KPIs (Year 1)

These KPIs map execution directly to investor and operational milestones:

| Business KPI | Year 1 Target | Current Status (Pre-Pilot) |
|---|---|---|
| **Pilot Merchants** | 20 | 0 active |
| **Paying Merchants** | 10 | 0 active |
| **Autonomy Metric** | Maximize PCAR | Framework ready, tracking enabled |
| **Merchant Satisfaction** | CSAT ≥ 4.7 / 5 | Pre-survey baselines prepared |
| **Monthly Uptime** | ≥99.9% | Real-time monitoring metrics defined |
| **Average Response Latency** | <2 seconds (p95) | Emulator validated |
| **Customer Retention** | ≥90% | N/A (Pre-launch) |
