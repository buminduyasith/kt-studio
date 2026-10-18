# Checkout flow

Status: current as of v1.8 (order-service) / v2.4 (payment-gateway). Owner: Checkout squad.

## Happy path

1. Storefront calls `POST /orders`. `OrderService.placeOrder` asks inventory-service to reserve the
   stock (20-minute hold, prices snapshotted), saves the order as `PENDING_PAYMENT`, and publishes
   `OrderPlaced` to `orders.events` with `expiresAt = createdAt + 15 min`.
2. payment-gateway's consumer receives `OrderPlaced` and creates a PSP payment intent with
   `Idempotency-Key: order-<orderId>`, then records `intent:<orderId>` in Redis.
3. The customer pays on the PSP's hosted page. The PSP calls `POST /webhooks/psp` with
   `payment_intent.succeeded`.
4. The gateway verifies `X-Psp-Signature`, rejects anything signed more than 5 minutes ago, claims
   `psp-event:<evt id>` in Redis (24h TTL) and publishes `PaymentSucceeded` (eventId = PSP event id).
5. order-service's `PaymentEventsListener` checks `processed_events`, marks the order `PAID`, and
   inserts the event id, all in one transaction. Fulfilment later moves it to `SHIPPED`.

```
Storefront -> order-service -> [orders.events] -> payment-gateway -> PSP
                    ^                                    |
                    +------- [payments.events] <---- webhook
```

## Failure paths

| What happens | Who reacts | Result |
|---|---|---|
| SKU out of stock | `HttpInventoryClient` gets 409 | `POST /orders` returns 409, no order stored |
| Hard decline (`stolen_card`, `fraudulent`, ...) | gateway publishes `PaymentFailed` | order `CANCELLED (PAYMENT_FAILED)`, stock released, `OrderCancelled` sent |
| Soft decline (`insufficient_funds`, ...) | gateway only logs | customer may retry until the 15 minutes are up |
| No payment within 15 minutes | `ReservationExpiryJob` (every 60s, 100 per sweep) | `CANCELLED (PAYMENT_TIMEOUT)`, stock released, gateway cancels the intent |
| PSP 5xx or timeout | `PspClient` | 3 attempts, 200ms then 400ms backoff, then Kafka redelivery |
| Webhook redelivered | Redis `SET NX` claim | 200 `{duplicate: true}`, nothing published |
| Kafka publish fails in webhook | handler releases the claim | 503, the PSP retries later |
| Payment lands after expiry | `OrderService.markPaid` | order stays `CANCELLED`, logged for manual refund (PAY-260) |

## Idempotency layers

1. PSP `Idempotency-Key` on intent create/cancel (PAY-231: duplicate charges from redelivered `OrderPlaced`).
2. Gateway webhook dedupe on PSP event id, 24h.
3. order-service `processed_events` primary key, plus `@Version` on `Order` for job vs. listener races.

## Known gaps

- ORD-118: `OrderPlaced` is sent before the DB commit; an outbox would close this.
- ORD-131: stock is released before the cancel commits, so a payment that wins the race can lose its hold.
- PAY-260: late payments need a manual refund.
