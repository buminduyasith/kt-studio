# KT Studio: project instructions for shop-checkout

## Services

| Service | What it is for | Talks to | Login |
| --- | --- | --- | --- |
| Order service | Turns a placed order into a payment request and confirms it | Payment gateway (Kafka events), Postgres | No screens |
| Payment gateway | Talks to the payment provider and its webhooks; publishes payment results | Payment provider, order service (Kafka), Redis | No screens |

## Addresses

None: nothing is deployed and there are no screens.

## Screens and recording

- There is no web UI and nothing is deployed. Videos have no Part A; the "use it" part is a short
  "Try it" chapter of terminal scenes.
- Kafka, Redis and Postgres are not available. Run only commands that need none of them (for
  example the payment-gateway unit tests), locally.
- Run such commands in a scratch copy outside the project (for example under `/tmp`). Never leave
  `node_modules`, `target/` or other build output inside the sample folders.

## Review

- Review the storyboard locally: no Claude artifact. The user opens `storyboard.html` and comments
  in the chat.
