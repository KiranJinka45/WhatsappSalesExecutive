# Closely AI - Environment Variables Specification

This document defines all configuration settings and secrets utilized by the Closely AI application.

---

## 1. System Variables Reference

| Variable Name | Description | Example / Default Value | Security Risk |
| :--- | :--- | :--- | :--- |
| **`ENVIRONMENT`** | Defines operational runtime boundaries. | `local` (or `staging`, `production`) | Low |
| **`DATABASE_URL`** | PostgreSQL connection URI. Must include asyncpg driver. | `postgresql://user:pass@localhost:5432/closely` | Critical (Secrets) |
| **`REDIS_URL`** | Redis cache and Celery broker connection string. | `redis://localhost:6379/0` | High (Secrets) |
| **`GEMINI_API_KEY`** | Google Gemini authentication key. | `AIzaSyD-12345...` | Critical (Secrets) |
| **`WHATSAPP_VERIFY_TOKEN`** | Handshake validation string matching Meta App settings. | `MyCustomVerificationToken123!` | Medium |
| **`WHATSAPP_API_TOKEN`** | Long-lived Meta Cloud API System User token. | `EAAG...` | Critical (Secrets) |
| **`WEBHOOK_APP_SECRET`** | Meta App Secret token used to verify X-Hub signature headers. | `4a2e...` | Critical (Secrets) |
| **`JWT_SECRET`** | Secret key used to sign and verify RS256 authorization tokens. | `some-highly-secure-jwt-signature-key-5000` | Critical (Secrets) |
| **`PORT`** | Defines local FastAPI listening port. | `8000` | Low |

---

## 2. Security Compliance Rules
- **No Repository Commits**: The `.env` file containing real values must *never* be committed to Git. Ensure `.env` is present in your project's `.gitignore` file.
- **Production Secrets**: In production, secrets must be loaded using an environment vault (e.g. AWS Secrets Manager, Doppler, or GitHub Actions secrets) rather than plaintext configuration files on servers.
- **API Rotations**: Generate fresh `JWT_SECRET` and `WEBHOOK_APP_SECRET` keys prior to every production release tags compilation.
