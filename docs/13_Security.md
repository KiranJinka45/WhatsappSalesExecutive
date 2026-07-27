# Closely AI - Security Specifications

This document defines the protocols for data protection, encryption, credential management, and signature verification within the Closely AI system.

---

## 1. Compliance & Data Sovereignty (GDPR / Local Laws)

As a platform handling customer messaging, Closely AI conforms to standard privacy guidelines:

* **Right to Be Forgotten**: Provide a dashboard control and secure API endpoint to delete a customer's history. The system permanently purges or cryptographically hashes PII fields within 48 hours of a merchant or shopper request. 
  * **Deletion Execution Pipeline**:
    ```
    Delete request received ──► Identity verified ──► Deletion job queued ──► Audit log written ──► Customer notified
    ```
    1. *Request Received*: Shopper asks merchant or triggers opt-out; merchant registers deletion request in Dashboard.
    2. *Identity Verified*: System checks phone number hashes to verify target record ownership.
    3. *Deletion Job Queued*: Asynchronous background job executes database purge of message contents and preferences.
    4. *Audit Log Written*: Cryptographically signed audit log registers a completed GDPR purge action (referencing only the hashed customer ID).
    5. *Customer Notified*: Auto-acknowledgment sent to customer confirming successful deletion of historical thread data.
* **Explicit Opt-out**: If a customer messages *"Stop"* or *"Opt out"*, the AI immediately transitions the conversation status to `resolved` and pauses automated message sequences.
* **Data Minimization**: Only store data required for recommendation and checkouts (phone number, name, shipping address, sizing/color preferences). Device fingerprints or unneeded network metrics are ignored.

---

## 2. Data Retention & Archiving Policy

To secure data, comply with regulatory requirements, and limit storage overhead, Closely AI enforces the following data lifecycle policy:

| Dataset | Retention Window (Active) | Archiving Action (Cold) | Deletion/Purge Action |
| :--- | :--- | :--- | :--- |
| **Conversations & Chat Logs** | 90 Days | Compress and move to AWS S3 Glacier (AES-256) | Permanent delete after **1 Year** |
| **Recommendation telemetry** | 180 Days (6 Months) | Anonymize / hash customer IDs; retain feature vectors | Aggregated analytics retained indefinitely |
| **Replay Exports (JSON/PDF)**| 30 Days | Purge local export volumes | Permanent delete after **30 Days** |
| **Customer PII Profiles** | 30 Days of inactivity | Archive contact structure without preferences | Purge upon merchant request / GDPR event |

---

## 3. Data Protection & Encryption at Rest

* **PII Encryption**: Customer phone numbers, names, and shipping addresses are encrypted in the PostgreSQL database using column-level encryption (`pgcrypto` or AES-GCM 256-bit keys).
* **Session Caching**: Session memory in Redis is configured with an explicit Time-To-Live (TTL) of 24 hours. Conversation states persist, but transient memory is regularly purged.


---

## 3. Webhook Signature Verification
To prevent malicious actors from spoofing mock WhatsApp payload requests and triggering LLM bills or fake orders, the system validates the cryptographic signature of all incoming webhooks:

### Meta X-Hub-Signature Verification
Meta Cloud API signs incoming webhook requests with an HMAC SHA256 signature in the `X-Hub-Signature-256` header, keyed with the brand's Webhook App Secret:

```python
import hmac
import hashlib

def verify_meta_signature(payload: bytes, signature: str, app_secret: str) -> bool:
    if not signature or not signature.startswith("sha256="):
        return False
    
    expected_sig = hmac.new(
        key=app_secret.encode('utf-8'),
        msg=payload,
        digestmod=hashlib.sha256
    ).hexdigest()
    
    received_sig = signature.split("sha256=")[1]
    return hmac.compare_digest(expected_sig, received_sig)
```

---

## 4. API Credential & JWT Handling
- **Dashboard Authorization**: Uses standard RS256 JWT tokens. Tokens expire after 60 minutes.
- **Key Store**: Private/Public keys and third-party APIs (Gemini API, Meta credentials) must be loaded from containerized environment secrets. They are never committed to the repository.
- **Rate Limiting**: Protect endpoints (e.g. `/api/webhooks/whatsapp`) with Redis-backed rate limiting per sender IP address and phone number to mitigate Denial of Service (DoS) attacks.
