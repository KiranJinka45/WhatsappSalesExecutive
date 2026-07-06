# Closely AI - API Specification

All REST APIs communicate using JSON payloads. JWT Bearer authorization is required for dashboard and management routes.

---

## 1. Authentication Endpoints

### Register Organization & Owner
- **Endpoint**: `POST /api/auth/register`
- **Request Body**:
  ```json
  {
    "org_name": "FabIndia",
    "email": "owner@fabindia.com",
    "password": "SecurePassword123",
    "name": "Kiran Dev"
  }
  ```
- **Response (201 Created)**:
  ```json
  {
    "status": "success",
    "organization_id": "8e390c5d-2831-4c12-9c1c-c76b91176b9f",
    "user_id": "1a234b56-cd78-9e12-3456-7890abcdef12"
  }
  ```

---

## 2. Catalog Management Endpoints

### Upload Catalog File
- **Endpoint**: `POST /api/catalog/upload`
- **Headers**: `Authorization: Bearer <token>`, `Content-Type: multipart/form-data`
- **Form Data**: `file: catalog.csv`
- **Response (200 OK - Passed)**:
  ```json
  {
    "status": "success",
    "created": 142,
    "updated": 12,
    "validation_report_id": "c1a2f3b4-5678-9abc-def0-123456789abc"
  }
  ```
- **Response (422 Unprocessable Entity - Validation Failed)**:
  ```json
  {
    "status": "failed",
    "errors": [
      { "row": 12, "field": "price", "message": "Price is missing or invalid" },
      { "row": 45, "field": "sku", "message": "Duplicate SKU detected in upload" }
    ],
    "validation_report_id": "c1a2f3b4-5678-9abc-def0-123456789abc"
  }
  ```

---

## 3. Conversations & Control Endpoints

### List Active Conversations
- **Endpoint**: `GET /api/conversations`
- **Query Params**: `status` (active/human_takeover/resolved), `stage` (funnel stage filter), `limit`, `offset`
- **Response (200 OK)**:
  ```json
  [
    {
      "id": "e2b3c4d5-6789-0abc-def1-234567890ab1",
      "customer_phone": "+919876543210",
      "customer_name": "Anya Sharma",
      "status": "ai_active",
      "sales_funnel_stage": "CART_INTENT",
      "lead_score": {
        "purchase_probability": 0.85,
        "interest_score": 90,
        "sentiment_score": 0.65,
        "urgency": "HIGH"
      },
      "updated_at": "2026-07-05T08:40:43Z"
    }
  ]
  ```

### Escalation Control
- **Endpoint**: `POST /api/conversations/{id}/takeover`
- **Response (200 OK)**:
  ```json
  {
    "status": "success",
    "conversation_id": "e2b3c4d5-6789-0abc-def1-234567890ab1",
    "assigned_agent_id": "1a234b56-cd78-9e12-3456-7890abcdef12"
  }
  ```

---

## 4. Webhook Gateways

### WhatsApp Webhook Listener
- **Endpoint**: `POST /api/webhooks/whatsapp`
- **Request Body (Twilio / Meta Payload Format)**:
  ```json
  {
    "object": "whatsapp_business_account",
    "entry": [
      {
        "id": "WHATSAPP_BUSINESS_ACCOUNT_ID",
        "changes": [
          {
            "value": {
              "messaging_product": "whatsapp",
              "metadata": { "display_phone_number": "15555555555" },
              "contacts": [{ "profile": { "name": "Anya Sharma" }, "wa_id": "919876543210" }],
              "messages": [{
                "from": "919876543210",
                "id": "wamid.HBgLOTE5ODc2NTQzMjEwFQIAERgSQjE0RkFGQ...",
                "timestamp": "1783478901",
                "text": { "body": "Do you have the pink Anarkali in size M?" },
                "type": "text"
              }]
            },
            "field": "messages"
          }
        ]
      }
    ]
  }
  ```
- **Response (200 OK)**:
  ```json
  { "status": "processed", "message_id": "wamid..." }
  ```

### Payment Webhook Listener
- **Endpoint**: `POST /api/webhooks/payments`
- **Headers**: `X-Razorpay-Signature: <signature>`
- **Request Body**:
  ```json
  {
    "entity": "event",
    "account_id": "acc_BF12345",
    "event": "payment.captured",
    "payload": {
      "payment": {
        "entity": {
          "id": "pay_FN12345",
          "amount": 450000, -- INR 4500.00
          "status": "captured",
          "notes": { "conversation_id": "e2b3c4d5-6789-0abc-def1-234567890ab1" }
        }
      }
    }
  }
  ```
- **Response (200 OK)**:
  ```json
  { "status": "payment_captured", "order_id": "ord_1a2b3c" }
  ```
