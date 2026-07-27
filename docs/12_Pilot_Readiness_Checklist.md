# Closely AI - Pilot Readiness Checklist

*Status: **FROZEN** (Stable; the operational "go/no-go" checklist for every pilot launch).*
*Version: **v1.0.0***

This checklist defines the operational gate that must be completed and verified before any boutique merchant goes live with Closely AI in a production environment.

| Category | Verification Item | Check / Owner |
|---|---|---|
| **Infrastructure** | Database backups are verified and restorable. | [ ] |
| **Infrastructure** | Redis is healthy and persistent caching is enabled. | [ ] |
| **Infrastructure** | Sentry/monitoring tools are active and tracking error rates. | [ ] |
| **Infrastructure** | Outage and anomaly alerting is configured and active. | [ ] |
| **Security** | API keys and secrets are securely configured (no development credentials).| [ ] |
| **Security** | Multi-tenant tenant isolation verification tests pass. | [ ] |
| **AI Quality** | Merchant-defined policies (discount limit, refund routing) are set up. | [ ] |
| **AI Quality** | Brand knowledge base and product catalog are fully indexed in pgvector. | [ ] |
| **AI Quality** | Approval queue flows and manual override consoles are tested and active. | [ ] |
| **Business** | Merchant onboarding flow completed without errors. | [ ] |
| **Business** | Pilot agreement signed by the boutique owner. | [ ] |
| **Operations** | Rollback procedures have been verified and tested. | [ ] |
| **Operations** | Incident response communication contacts are confirmed on both sides. | [ ] |
