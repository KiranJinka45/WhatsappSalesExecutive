# Closely AI - Product Discovery Report

## 1. Executive Summary
Closely AI is a multi-tenant Conversational Commerce platform designed to empower independent clothing boutiques and retail brands to automate sales qualification, catalog recommendation, and order collection directly over WhatsApp. By integrating a deterministic decision engine with conversational large language models, Closely AI guarantees zero-hallucination accuracy on product details and inventory, resolving the primary trust barrier in automated retail commerce.

---

## 2. Customer Profile & Target User Persona
Conversational commerce on WhatsApp is a necessity for mobile-first markets (such as India and Latin America), where consumers bypass web search and buy directly through chat.

### Core User Persona: The Independent Boutique Owner (e.g., Somu Sekhar)
* **Demographics**: Owner of an independent retail boutique (e.g., *Pushpalatha Silks* or *Sri Siddi Vinayaka Silks* in Dharmavaram, India).
* **Core Business**: Sells high-quality sarees, kurtis, and custom apparel. Uses physical store traffic, Instagram showcases, and WhatsApp chat groups to drive sales.
* **Daily Workflow**: Receives 100–300 WhatsApp messages per day from customers asking: *"Do you have this saree in blue?"*, *"What is the price of this kurti?"*, or *"Can you send close-up photos of the fabric?"*
* **Primary Pain Points & Stress Triggers**:
  - **High Lead Drop-Off**: Customers shopping on WhatsApp expect replies within 1–2 minutes. If the owner is busy attending to in-store customers, reply delays stretch to hours, resulting in a **50%+ lead drop-off rate**.
  - **Manual Catalog Searching**: Searching through a CSV inventory sheet or phone gallery for matching designs, colors, and sizes while typing replies is tedious and slow.
  - **Bargaining and Negotiation Fatigue**: Customers constantly haggle over prices (e.g., *"Konchem thagginchandi"* in Telugu), requiring the owner to decide on discounts in real-time.
  - **Order Tracking Dissociation**: Payment verification and shipping detail collections are handled in disjointed threads, leading to bookkeeping errors.

---

## 3. The Pain-Point & Value Proposition Matrix
Closely AI addresses these pains with a targeted value proposition:

| Customer Pain | Closely AI Solution | Business Outcome |
|---|---|---|
| **Slow Response Times** | 24/7 automated instant greetings, size/color discovery, and catalog recommendation. | **95%+ decrease in response latency**, capturing impulse buyers. |
| **Inventory Fact Hallucination** | Deterministic catalog lookup (SQL + vector) overrides generative outputs. AI never invents a price or promises out-of-stock items. | **100% pricing accuracy**, maintaining brand trust and customer confidence. |
| **Bargaining and Policy Exceptions** | Deterministic Decision Engine intercepts bargaining and complaints, routing them to a Human Takeover Queue. | **Zero unauthorized discounts**, while preserving human focus for high-value negotiations. |
| **Sizing Disconnect** | Customer memory profile stores size/color history for hyper-personalized future drops. | **Higher customer lifetime value (LTV)** and reduced return rates. |

---

## 4. Competitive Moat & Apparel Specialization
Unlike generic conversational AI platforms (e.g., general-purpose support widgets), Closely AI is custom-engineered for retail boutique commerce:

1. **Fashion-Specific Taxonomy & Multilingual Script Recognition**:
   Recognizes localized clothing terminology (e.g., *Banarasi, Anarkali, Kurti, Zari border, Georgette*) in multiple languages (English, Telugu, Hindi) and formats (Latin transliteration vs. native scripts).
2. **Preference Profiling & Customer Memory**:
   Remembers customer history (e.g., *"Sita preferred M-size cotton sarees under 3000"*). When she returns, the system automatically skews recommendations to match.
3. **Visual & Multimodal Retrieval**:
   Apparel shopping is inherently visual. Customers can send an image of a dress they saw on Instagram, and the backend performs multimodal visual search (using Gemini embeddings) to find the closest matching SKU in the boutique's catalog.
4. **Deterministic Escalate-on-Exception**:
   Guarantees safety-first commerce. Any deviation from stored store policies immediately locks the conversation under a `WAITING_APPROVAL` status, alerting the owner to intervene.

---

## 5. Commercial Viability & SaaS Strategy
Closely AI operates on a B2B SaaS model tailored for retail merchants:
- **Base Subscription Tier**: Fixed monthly subscription fee covering catalog management, dashboard access, and 500 automated conversations/month.
- **Usage-Based Inbound Credits**: Per-conversation usage charges on top of the base subscription to cover Meta Cloud API and LLM token costs.
- **Value-Added Premium Features**:
  - Outbound marketing campaign automation (broadcasting new drops to qualified customer profiles).
  - Advanced analytics on conversion rates and inventory demand forecasting.
  - Custom visual search integrations.
