# order-service

Spring Boot 3 / Java 17. Owns orders and their lifecycle: `PENDING_PAYMENT → PAID → SHIPPED`,
or `PENDING_PAYMENT → CANCELLED`.

| Piece | What it does |
|---|---|
| `api/OrderController` | `POST /orders`, `GET /orders/{id}` |
| `service/OrderService` | Reserves stock, saves the order, publishes `OrderPlaced` / `OrderCancelled` |
| `payments/PaymentEventsListener` | Consumes `payments.events`, dedupes on `processed_events` |
| `jobs/ReservationExpiryJob` | Cancels orders unpaid after 15 minutes and releases stock |
| `events/KafkaEventPublisher` | `EventPublisher` implementation, writes to `orders.events` |

Config lives in `src/main/resources/application.yml` (`checkout.*`). Tables (`orders`, `order_lines`,
`processed_events`) are migrated from the shop-db repo.

```bash
mvn spring-boot:run      # needs Postgres on :5432 and Kafka on :9092
mvn test
```
