# shop-checkout

Checkout for the web shop: turning a cart into a paid order. Two services own it, and they only
talk to each other through Kafka.

| Folder | Stack | Owns |
|---|---|---|
| [`order-service/`](order-service/) | Java 17, Spring Boot 3, Postgres | Orders, their state machine, stock reservation, payment timeout |
| [`payment-gateway/`](payment-gateway/) | Node 20, TypeScript, Express, Redis | Everything that talks to the PSP: intents, webhooks, retries |
| [`contracts/`](contracts/) | OpenAPI 3, AsyncAPI 3 | The public order API and the four Kafka events |
| [`docs/`](docs/) | Markdown | [Checkout flow](docs/checkout-flow.md): happy path, failures, known gaps |

## How they talk

```
POST /orders ─▶ order-service ──OrderPlaced / OrderCancelled──▶ orders.events ─▶ payment-gateway ─▶ PSP
                     ▲                                                                 │
                     └──────── payments.events ◀── PaymentSucceeded / PaymentFailed ◀──┘ (webhook)
```

- `orders.events`: `OrderPlaced` (open a payment intent) and `OrderCancelled` (cancel it).
- `payments.events`: `PaymentSucceeded` (order becomes `PAID`) and `PaymentFailed` (order becomes `CANCELLED`).
- Every message is keyed by `orderId` and delivered at least once, so every consumer is idempotent.

## Key numbers

| Rule | Value | Where |
|---|---|---|
| Payment window before an unpaid order is cancelled | 15 minutes | `order-service/.../application.yml` |
| Expiry sweep | every 60 s, max 100 orders | `ReservationExpiryJob` |
| Items per order / units per line | 20 / 1-10 | `OrderController.CreateOrderRequest` |
| PSP retries | 3 attempts, 200ms * 2^n, 5xx and timeouts only | `payment-gateway/src/psp/client.ts` |
| Webhook freshness | 5 minutes | `payment-gateway/src/webhooks/verify.ts` |
| Webhook dedupe | 24 hours | `payment-gateway/src/idempotency/store.ts` |

## Running locally

Needs Kafka (`localhost:9092`), Postgres (`localhost:5432/orders`) and Redis (`localhost:6379`).
See each service's README for its commands.
