---
id: ADR-003
title: PostgreSQL as Primary Database Engine
status: accepted
date: 2026-01-10
authors:
  - maria.garcia
applies_to:
  - user-service
  - order-service
  - inventory-service
  - analytics-service
supersedes: null
---

# PostgreSQL as Primary Database Engine

## Context

As we transitioned from a monolith to microservices, each team considered their own
database choices. Some teams proposed MongoDB for its schema flexibility, others
wanted DynamoDB for auto-scaling.

## Decision

**PostgreSQL** is the standard primary database for all services. MongoDB and other
NoSQL databases are not permitted without explicit architecture review board approval.

## Rationale

- PostgreSQL provides ACID transactions required for financial data (orders, payments)
- JSONB columns give us document-style flexibility when needed, eliminating the MongoDB argument
- Our DBA team has deep PostgreSQL expertise; MongoDB expertise is limited to 1 person
- pg_stat_statements and pgBouncer give us mature observability and connection pooling
- Schema migrations are well-tooled (Alembic, Flyway) with rollback support
- Cross-service JOIN queries are occasionally needed for analytics; PostgreSQL makes this straightforward

## Constraints

- All services MUST use PostgreSQL as their primary data store
- MongoDB is NOT approved for any production service
- DynamoDB may be used ONLY for specific event sourcing / append-only log patterns with ARB approval
- All schemas must have migration files checked into the service repository
- Connection pooling via pgBouncer is mandatory for all services

## Consequences

- Consistent tooling and monitoring across all services
- DBA team can support all services effectively
- Some services may need JSONB columns for semi-structured data instead of separate document stores
- Team autonomy is slightly reduced in exchange for operational consistency
