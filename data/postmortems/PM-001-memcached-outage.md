---
id: PM-001
title: Checkout Service Outage Due to Unauthorized Memcached Usage
incident_id: INC-089
severity: SEV-1
date: 2026-05-22
duration_minutes: 135
affected_services:
  - checkout-service
  - payment-service
root_cause_service: checkout-service
author: david.kumar
reviewers:
  - sarah.chen
  - maria.garcia
---

# Post-Mortem: Checkout Service Outage (INC-089)

## Summary

Checkout service experienced 100% failure rate for 2 hours and 15 minutes on May 22, 2026.
The root cause was an unauthorized introduction of Memcached as a caching layer, which
violated ADR-001 (Use Redis for Application Caching).

## Impact

- **Duration**: 2h 15m (14:00 - 16:15 UTC)
- **Revenue Impact**: Estimated $47,000 in lost sales
- **Users Affected**: ~12,000 active checkout sessions dropped
- **Downstream**: payment-service experienced cascading failures due to retry storms

## Root Cause

A junior developer on the checkout team added `pymemcache` as a dependency to
checkout-service in PR #1847 for "performance optimization" of product catalog lookups.
The developer was unaware of ADR-001 which mandates Redis for all caching.

The Memcached instance was configured with:
- Connection pool size: 5 (far too small for production traffic)
- No circuit breaker or fallback
- No monitoring or alerting

During a traffic spike from a marketing campaign at 14:00 UTC, the Memcached connection
pool was exhausted within 5 minutes. Because there was no circuit breaker, every request
to checkout-service blocked waiting for a Memcached connection, causing thread pool
exhaustion and 100% 500 errors.

## Timeline

- **13:45** — Marketing campaign email sent to 500K subscribers
- **14:00** — Traffic spike begins (3x normal checkout volume)
- **14:05** — Memcached connection pool saturated (5/5 connections in use)
- **14:07** — checkout-service thread pool exhausted, returning 500 errors
- **14:10** — PagerDuty alert fires: "checkout-service error rate > 50%"
- **14:12** — payment-service starts receiving retry storms, also degrades
- **14:15** — On-call engineer (Alex Wong) begins investigation
- **14:35** — Alex identifies Memcached connections as the bottleneck
- **14:50** — Sarah Chen (platform team) joins, recognizes ADR-001 violation
- **15:00** — Decision made to hot-patch: remove Memcached, restore Redis cache
- **15:30** — PR #1902 merged: Memcached removed, Redis cache restored
- **15:45** — Deployment begins rolling out
- **16:15** — Full recovery confirmed, error rate back to baseline

## Lessons Learned

- **CONSTRAINT**: Memcached must NEVER be used in any service. ADR-001 exists for exactly this reason.
- **CONSTRAINT**: All new caching dependencies must be reviewed by the platform team before merge.
- **CONSTRAINT**: All services must have circuit breakers on external connection pools.
- The PR review process failed: PR #1847 was reviewed by a checkout team member who also didn't know about ADR-001.
- We need automated enforcement of architectural decision records.

## Action Items

- [x] Remove Memcached from checkout-service (PR #1902) — David Kumar
- [x] Add ADR-001 reference to checkout-service README — David Kumar
- [ ] Implement automated ADR constraint checking in CI pipeline — Sarah Chen
- [ ] Add circuit breaker library to all services — Platform Team
- [ ] Create onboarding checklist that includes reading all active ADRs — Maria Garcia
