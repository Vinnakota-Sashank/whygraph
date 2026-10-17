---
id: PM-002
title: Cascading Timeout Failure from Synchronous Payment Calls
incident_id: INC-112
severity: SEV-1
date: 2026-07-14
duration_minutes: 90
affected_services:
  - checkout-service
  - payment-service
  - order-service
root_cause_service: checkout-service
author: alex.wong
reviewers:
  - david.kumar
  - sarah.chen
---

# Post-Mortem: Cascading Timeout from Sync Payment Calls (INC-112)

## Summary

On July 14, 2026, checkout-service experienced degraded performance (95th percentile
latency > 30s) for 90 minutes. Root cause: a new feature branch reintroduced synchronous
HTTP calls to payment-service, violating ADR-002 (Async Communication with Payment Service).

## Impact

- **Duration**: 1h 30m (10:30 - 12:00 UTC)
- **Revenue Impact**: Estimated $28,000 in abandoned carts
- **Users Affected**: ~6,000 users experienced checkout timeouts
- **Downstream**: order-service queue backed up with 15,000 pending orders

## Root Cause

A feature for "instant payment verification" was implemented in checkout-service by
making a synchronous REST call to `payment-service/api/v2/verify` to check payment
status before showing the confirmation page. This was done to improve UX (show
confirmation faster) but violated ADR-002.

When payment-service experienced a brief latency spike (P99 went from 200ms to 8s
due to a Stripe API slowdown), all checkout-service threads were blocked waiting for
synchronous responses. The 30-second HTTP timeout meant threads were held for 30s each,
quickly exhausting the thread pool.

## Timeline

- **10:25** — Stripe API experiences intermittent latency (external, not our fault)
- **10:30** — payment-service P99 latency spikes to 8 seconds
- **10:32** — checkout-service threads start blocking on sync payment calls
- **10:35** — checkout-service thread pool 80% utilized
- **10:40** — PagerDuty alert: "checkout-service latency P95 > 10s"
- **10:45** — On-call (David Kumar) begins investigation
- **11:00** — David identifies sync HTTP calls to payment-service in new code
- **11:10** — David recognizes ADR-002 violation, escalates to Sarah Chen
- **11:30** — Feature flag disabled to bypass sync payment verification
- **11:45** — checkout-service latency returning to normal
- **12:00** — Full recovery, order queue drained

## Lessons Learned

- **CONSTRAINT**: Synchronous HTTP calls to payment-service from checkout flow are absolutely prohibited. ADR-002 was written specifically because of a similar incident in 2025.
- **CONSTRAINT**: Any new inter-service communication pattern must be reviewed by the platform team.
- Feature flags saved us — the instant verification feature was behind a flag, allowing quick rollback.
- The same type of failure has now happened TWICE (this + the 2025 incident that led to ADR-002). We are creating a recurring failure pattern.

## Action Items

- [x] Disable sync payment verification feature flag — David Kumar
- [ ] Rewrite instant verification using WebSocket push from payment-service — Alex Wong
- [ ] Add integration test that detects synchronous calls between checkout and payment — Platform Team
- [ ] Create "recurring incident" tag in incident tracker — Sarah Chen
