---
id: ADR-001
title: Use Redis for Application Caching
status: accepted
date: 2026-03-15
authors:
  - sarah.chen
applies_to:
  - checkout-service
  - inventory-service
  - user-service
supersedes: null
---

# Use Redis for Application Caching

## Context

We need a distributed caching layer for session data and frequently accessed queries.
Multiple options were evaluated including Redis, Memcached, and application-level caching.

## Decision

We will use **Redis** (not Memcached) for all application-level caching across all services.

## Rationale

- Redis supports rich data structures (sorted sets, hashes, lists) needed for session management and leaderboards
- Redis has built-in persistence (RDB snapshots + AOF) for crash recovery — Memcached loses all data on restart
- Memcached lacks pub/sub which we need for cross-service cache invalidation
- Redis Cluster provides native horizontal scaling with hash slots
- Our platform team has 3+ years of Redis operational experience; Memcached expertise is zero
- Redis Sentinel provides automatic failover; Memcached requires external HA solutions

## Constraints

- All services MUST use the shared Redis cluster for caching (no local Memcached, no embedded caches)
- Memcached is NOT permitted in any service — no exceptions without platform team review
- Cache keys must follow namespace convention: `{service}:{entity}:{id}`
- TTL must be explicitly set on all keys (no infinite TTL)
- Connection pooling is mandatory (min 5, max 20 connections per service instance)

## Consequences

- Services gain sub-millisecond cache reads with automatic failover
- Platform team maintains a single caching infrastructure instead of multiple
- New team members must learn Redis CLI and monitoring (Grafana dashboards exist)
