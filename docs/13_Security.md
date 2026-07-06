# Closely AI - Security Specifications

This document defines the protocols for data protection, encryption, credential management, and signature verification within the Closely AI system.

---

## 1. Compliance & Data Sovereignty (GDPR / Local Laws)
As a platform handling customer messaging, Closely AI conforms to standard privacy guidelines:

- **Right to Be Forgotten**: Provide an API endpoint and a dashboard button to delete a customer's history.
- **Explicit Opt-out**: If a customer messages *"Stop"* or *"Opt out"*, the AI immediately flags the conversation status to `resolved` and pauses further automatic notifications.
- **Data Minimization**: Only store customer data relevant to sales processing (phone number, name, shipping address, sizing/color preferences). Do not capture generic user device data.

---

## 2. Data Protection & Encryption at Rest
- **PII Encryption**: Customer phone numbers, names, and shipping addresses are encrypted in the PostgreSQL database using column-level encryption (`pgcrypto` or AES-GCM 256-bit keys).
- **Session Caching**: Session memory in Redis is configured with an explicit Time-To-Live (TTL) of 24 hours. Conversation states persist, but transient memory is regularly purged.

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
