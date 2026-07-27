# Pilot Real 01: Improvement & Feature Backlog

This backlog lists the feedback, issues, and requests observed during the first merchant pilot run, mapped to the Sprint 8 prioritization matrix.

## Sprint 8 Priority Bug Fixes (P0 / P1)

* **P0: Out-of-Stock Filter Lag**
  * *Observation*: When stock count changes to 0 in the database, the search cache occasionally retrieves the product for a brief window until Redis recycles keys.
  * *Action*: Ensure immediate Redis key purge/invalidation on stock update queries.
* **P1: CSV Line Ending Parsing Failure**
  * *Observation*: Catalog files exported from old Excel versions using MAC-style `` line-endings fail to decode correctly in the CSV validator.
  * *Action*: Update standard character encoding and reader handlers to normalize line-endings before reading dict rows.

## Post-Beta V2 Deferred Backlog (P2 / P3)

* **P2: Richer Recommendation Feedback Star Ratings**
  * *Observation*: Merchants want to rate recommendations on multiple dimensions (e.g., Correct Budget vs. Correct Style vs. Correct Fabric) instead of simple binary ratings.
  * *Action*: Implement V2 multi-dimensional ratings schema and API.
* **P2: Customer Outcome Tracking**
  * *Observation*: We need to track the exact lifecycle of recommendations (e.g. customer bought, customer ignored, merchant overrode AI).
  * *Action*: Implement transaction outcome logging.
* **P2: Chat Log Replay PDF Export**
  * *Observation*: Support staff and tailors require printing or archiving chat transcripts as PDFs for stitching specifications.
  * *Action*: Implement PDF generation endpoint under `/api/conversations/{id}/export/pdf`.
* **P3: Pre-order Waitlist Notification**
  * *Observation*: Customers want to opt-in for notifications when out-of-stock items (like SKU-SAR-004) are back in stock.
  * *Action*: Build a waitlist notifications scheduler.
