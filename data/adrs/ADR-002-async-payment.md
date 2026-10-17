---
id: ADR-002
title: Asynchronous Communication with Payment Service
status: accepted
date: 2026-02-20
authors:
  - david.kumar
  - sarah.chen
applies_to:
  - checkout-service
  - payment-service
  - order-service
supersedes: null
---

# Asynchronous Communication with Payment Service

## Context

The checkout flow currently makes synchronous HTTP calls to the payment service.
During peak traffic (flash sales, holiday seasons), synchronous calls create cascading
timeout failures when the payment service is slow or degraded.

## Decision

All communication between checkout-service and payment-service MUST be asynchronous
via message queue (RabbitMQ). Synchronous HTTP calls to payment-service from the
checkout flow are prohibited.

## Rationale

- Synchronous calls create tight coupling: if payment-service has 5s latency, checkout-service threads are blocked
- During Black Friday 2025, synchronous payment calls caused checkout to exhaust its thread pool, leading to a 45-minute outage
- Async messaging via RabbitMQ provides natural backpressure and retry semantics
- Payment processing is inherently asynchronous (bank confirmations take seconds to minutes)
- Circuit breakers on sync calls are a band-aid, not a solution

## Constraints

- checkout-service MUST NOT make synchronous HTTP calls to payment-service
- All payment requests must go through the `payment.requests` RabbitMQ queue
- Payment confirmations come back via `payment.confirmations` queue
- Timeout for payment confirmation: 30 seconds (after which order is marked "pending_payment")
- Direct REST calls to payment-service are only allowed for admin/backoffice read operations

## Consequences

- Checkout flow becomes resilient to payment-service degradation
- Order state machine becomes more complex (pending_payment state)
- Frontend needs WebSocket or polling for payment confirmation UX
- RabbitMQ becomes a critical infrastructure dependency
