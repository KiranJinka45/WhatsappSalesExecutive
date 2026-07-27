# docs/42_Dashboard_UI_Spec.md

## Merchant Dashboard & Explainability UI Specification

The purpose of the Merchant Dashboard is to provide complete explainability of the AI's actions. This builds merchant trust and allows them to audit decisions objectively.

### 1. Main Layout & Sidebar
- **Navigation:** Top navigation bar supporting Inbox (💬), Catalog (👗), Settings (⚙️), and Analytics (📊).
- **Active Threads (Left):** Real-time list of customer chats. Displays name/phone, a status badge (`AI Active` / `Human Takeover`), lead score (e.g., `Score: 85`), and budget cap (if extracted).

### 2. Message Thread (Middle)
- Standard chat interface differentiating customer, AI, and manual human messages.
- AI messages feature a subtle **"🔍 Inspect Decision"** action button.
- Typing in the input box or manually overriding a chat will call `/takeover` and immediately silence the AI automation.

### 3. Explainability Panel (Right/Slide-out)
When "Inspect Decision" is clicked on an AI message, a slide-out drawer appears displaying:
- **Pipeline Stages Checklist:**
  - `Intent Classify` (Green Check) -> e.g., `product_discovery`
  - `Entity Extraction` (Green Check) -> e.g., `color: red, max_price: 3000`
  - `Retrieval Validation` (Green Check) -> e.g., Passed Retrieval Quality Layer
- **Products Breakdown:**
  - **Retrieved & Recommended (Ranked):** List of products retrieved and ranked. Shows SKU, name, price, stock count, and calculated `ranking_score`.
  - **Rejected Products:** List of products retrieved but discarded. Explicitly displays the rejection reason (e.g. `Price (4500) > Budget Cap (3000)` or `Stock Count = 0`).
- **Policy Compliance Logs:**
  - Shows verified policies (e.g., `refund_policy: checked`, `shipping_cost: free`).

### 4. Interactive Simulation Sandbox (Right)
- Allows merchants to simulate arbitrary customer queries, immediately see the AI's internal state (retrieval & policy decisions), and watch the conversation progress without needing a physical phone connected.
