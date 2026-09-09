# Closely AI — Master Live Stakeholder Demo Playbook

> **Purpose**: Field-tested operational runbook for executing live technical and commercial demos of Closely AI.  
> **Rule Zero**: A live demo is never a generic feature tour; it is a choreographed psychological narrative that eliminates the audience's deepest anxieties. You are selling **trust and deterministic control**, not just code.

---

## 🎭 The Two Demo Dialects

| Dimension | Track A: The Retail Boutique Merchant | Track B: The Engineering Hiring Manager |
| :--- | :--- | :--- |
| **Audience** | Boutique owners, retail GMs, sales directors | VP of Eng, Staff Engineers, Head of Applied AI |
| **Deepest Fear** | AI going rogue, hallucinating discounts, losing high-value sales | Race conditions, duplicate billing, silent data breaches |
| **Language** | Revenue, counter hours, wedding season, inventory control | Pessimistic locks, RLS, idempotency, drift revalidation |
| **Visual Focus** | WhatsApp chats, Approval Inbox, SQL Evidence, CSV errors | Webhook HMAC logs, DB transactions, Reconciliation Queue |
| **Duration** | 8 – 10 Minutes | 12 – 15 Minutes |

---

## 👗 Track A: The Boutique Owner Demo (Focus: Control & Revenue)

### The Psychology
Boutique owners do not care about PostgreSQL Row-Level Security or HMAC-SHA256 hashes. They care about losing a ₹25,000 bridal sale while serving in-store clients, or the nightmare of an AI promising a Kanjeevaram silk saree for ₹1,500.

---

### Step-by-Step Script & Choreography

#### 1. The Setup (0:00 – 1:30) — The Relatable Pain Point
> *"Picture this: It's 8:30 PM on a Saturday during peak wedding season. You have three customers in the showroom trying on bridal lehengas. At that exact moment, high-intent WhatsApp inquiries arrive from shoppers asking: 'Do you have the Crimson Kanjeevaram Silk Saree in stock, and what is your best price?'*  
> *Normally, you have two bad choices: leave paying in-store customers to check spreadsheets, or let the WhatsApp shopper wait hours until they buy from another boutique."*

#### 2. The Live Trigger (1:30 – 2:30) — Physical Proof
- Take out your smartphone in front of the merchant.
- Send a WhatsApp message to the Closely AI live sandbox number:
  > *"Hi! Do you have the Crimson Kanjeevaram Silk Saree in stock? Will you accept ₹10,000 for it?"*
- **Embrace the Silence**: Do not speak for 4 seconds. Let them watch the WhatsApp double blue-tick and the dashboard UI update autonomously via the Server-Sent Events (SSE) stream.

#### 3. The "Aha!" Moment (2:30 – 5:00) — The Merchant Approval Inbox
- **DO NOT show terminal logs**. Switch directly to the browser view: `http://localhost:3000` -> **Chats**.
- Click the notification badge: **Wait Approval (1)**.
- **Point to the SQL Evidence Panel (The Green Box)**:
  > *"Look at this green panel right here. Before the AI wrote a single syllable, it queried your live inventory. It verified that SKU SILK-KNJ-042 is ₹14,500 and you only have 2 units left in the showroom. The AI is strictly forbidden from guessing. It is anchored to your real stock."*
- **Point to the AI Draft**:
  > *"Notice how the AI politely declined the ₹10,000 lowball offer according to your store policy, while maintaining a warm, high-touch luxury tone."*

#### 4. The Control Handover (5:00 – 7:30) — The Merchant is the Boss
- Highlight the action buttons:
  > *"The AI drafted this in 800 milliseconds, but it cannot send it without you. You are in total control."*
- Click **"✏️ Edit & Send"**.
- Add a personal touch in real-time:
  > *"I cannot do ₹10,000, but if you order today, I'll include matching unstitched blouse fabric and complimentary express shipping."*
- Click **"✓ Approve & Send"**.
- Show your smartphone screen receiving the exact approved message instantly.

#### 5. The Bulk Upload Finale (7:30 – 10:00) — Defending Their Inventory
- Switch to the **Catalog** tab.
- Upload a sample CSV with 50 items. Deliberately include a row with `price = -500` and a duplicate SKU.
- Choose **"Partial Ingestion"** and click **Import CSV Catalog**.
- Show the Ingestion Summary Card:
  - 48 Created/Updated (Green)
  - 2 Invalid Rows (Red)
  - Clear Pydantic error breakdown pointing out the negative price on row 14.
  > *"Your inventory is your livelihood. Closely AI defends it against spreadsheet typos so bad data never reaches your customers."*

---

## 🛠️ Track B: The Hiring Manager Demo (Focus: Architecture & Resilience)

### The Psychology
Engineering managers for Forward-Deployed and Applied AI roles take for granted that you can call an OpenAI or Gemini endpoint. What they are aggressively screening for is **state management, concurrency control, failure isolation, and distributed systems discipline**.

---

### Step-by-Step Script & Choreography

#### 1. The Setup (0:00 – 2:00) — The Architectural Thesis
> *"Generative AI is inherently non-deterministic. In commercial retail, deploying stochastic token predictors directly to customer-facing channels creates severe margin and legal liabilities. I architected Closely AI to sandbox the LLM strictly as an intent parser and conversational copywriter, while enforcing all business invariants at the database transaction layer."*

#### 2. Inbound Webhook Reception & Non-Blocking Ingress (2:00 – 4:30)
- Trigger an inbound WhatsApp message.
- Open the backend terminal running with structured correlation logs:
  ```text
  [INFO] [trace-7f89a] Webhook received: HMAC-SHA256 signature verified.
  [INFO] [trace-7f89a] Dispatched background task. Returned HTTP 200 to Meta in 18ms.
  ```
- Explain the engineering choice:
  > *"Meta requires an HTTP 200 within 15 seconds, or it begins exponential backoff retries that flood the webhook. We authenticate the HMAC signature, parse the payload, enqueue the task, and return 200 in under 25 milliseconds."*

#### 3. Deterministic Grounding & Pessimistic Lock (4:30 – 8:00)
- Open the **Approval Inbox** on the frontend.
- Show the `stock_snapshot` and `price_snapshot` in the inspect panel.
- Walk through the concurrency scenario:
  > *"What happens if two customers inquire about the last saree in stock simultaneously? In a naive system, both get promised the item."*
- Walk through the code in `backend/app/approval_service.py`:
  > *"When the merchant clicks Approve, we open an atomic transaction and acquire a pessimistic row lock via `SELECT ... FOR UPDATE`. We re-evaluate live database stock against the draft's immutable snapshot. If stock dropped to zero during the human review window, drift revalidation aborts the dispatch, preventing overselling."*

#### 4. The Closer: Simulated Network Failure & Reconciliation (8:00 – 12:00)
- **This is the scene that wins the job.**
- Simulate a network timeout during dispatch (mock a 504 Gateway Timeout or transient connection drop).
- Show the backend log:
  ```text
  [WARNING] Meta API dispatch timed out. Status transitioned to UNKNOWN_PROVIDER_OUTCOME.
  ```
- Address the Two Generals Problem directly:
  > *"In distributed systems, networks fail. If you blind-retry this timeout, you risk double-messaging the customer and charging the merchant twice if Meta actually received the packet. Instead, we isolate the message."*
- Switch to the **⚖️ Outbox Queue** (`ReconciliationQueue.jsx`).
- Point out the stuck message with attempt count and provider timeout trace.
- Demonstrate:
  1. **Passive resolution**: Meta delivery receipt webhook resolves the state to `DELIVERED` automatically.
  2. **Active resolution**: The merchant clicks **"Close Loop"** or **"Allow Resend"**, which executes under a cryptographically hashed SHA-256 audit trail in `approval_audit_logs`.

#### 5. Multi-Tenant RLS Defense-in-Depth (12:00 – 15:00)
- Open a PostgreSQL terminal or test snippet.
- Demonstrate:
  ```sql
  -- Without tenant context:
  SELECT count(*) FROM products; -- Returns 0 rows (Fail-Closed)
  
  -- Inside transaction context:
  SET LOCAL app.current_tenant = 'tenant-uuid';
  SELECT count(*) FROM products; -- Returns only this boutique's catalog
  ```
- Explain:
  > *"We use `SET LOCAL` so session variables are bound strictly to the transaction, eliminating connection pool poisoning in PgBouncer or SQLAlchemy."*

---

## 📋 Pre-Demo Environment Checklist

Run this 5 minutes before every live presentation:

- [ ] **Docker Stack Healthy**: Run `docker-compose ps` to ensure `db`, `redis`, `backend`, `worker`, and `frontend` are up.
- [ ] **PostgreSQL Migrations Up-to-Date**: Verify tables exist and `pgvector` extension is active.
- [ ] **Realistic Data Loaded**: Verify boutique name is a real brand (e.g. *"Closely Luxury Sarees"*), with real SKUs and INR pricing (no "Test Product 123").
- [ ] **SSE Stream Connected**: Look at the top-right header in the frontend; ensure the green dot is glowing **"Live"**.
- [ ] **Ngrok / Webhook Tunnel Active**: If demoing live mobile WhatsApp, ensure the public tunnel matches Meta's Developer Dashboard callback URL.

---

## 🚨 Live Bug Triage: The FDE Pivot

If an unexpected error occurs during a live stakeholder demo:

1. **Never panic or apologize profusely**. High-level engineers expect distributed systems to encounter edge cases.
2. **State the fact calmly**: *"We encountered an unhandled response state here. Let's inspect the telemetry."*
3. **Open Developer Tools / Terminal**: Open the Network tab or FastAPI log stream.
4. **Narrate your debugging thought process**:
   - *"The backend returned a 422. Notice the payload structure—the SKU validator received an unstripped space."*
5. **State the fix clearly**:
   - *"In a production hotfix, we would wrap that field in a pre-validator. Let's retry with trimmed input."*

> **FDE Reality**: Hiring managers hire Forward-Deployed Engineers because they remain calm, analytical, and structured when client systems break down in the field.
