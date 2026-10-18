# payment-gateway

Node 20 / TypeScript. The only service that talks to the PSP ("StripeLike").

- **Consumes** `orders.events`: `OrderPlaced` opens a payment intent (`Idempotency-Key: order-<orderId>`),
  `OrderCancelled` cancels it.
- **Receives** `POST /webhooks/psp`: verifies `X-Psp-Signature` (HMAC SHA-256, 5-minute tolerance),
  dedupes on the PSP event id for 24h in Redis, then publishes `PaymentSucceeded` / `PaymentFailed`
  to `payments.events`.

| File | Role |
|---|---|
| `src/server.ts` | Composition root: Kafka, Redis, Express wiring |
| `src/psp/client.ts` | PSP REST wrapper; 3 attempts, 200ms * 2^n backoff, 5xx/timeouts only |
| `src/webhooks/verify.ts` | Signature + timestamp check |
| `src/webhooks/handler.ts` | Webhook → domain event mapping, dedupe, publish |
| `src/idempotency/store.ts` | `SET NX EX` claim store (Redis) + in-memory variant for tests |
| `src/events/consumer.ts` / `producer.ts` | Kafka in / out |

Env: `PSP_API_KEY`, `PSP_WEBHOOK_SECRET` (required), `PSP_BASE_URL`, `KAFKA_BROKERS`, `REDIS_URL`, `PORT` (3002).

```bash
npm install
npm test        # vitest
npm run dev
```
