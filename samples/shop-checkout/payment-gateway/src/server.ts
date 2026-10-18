import express from 'express';
import Redis from 'ioredis';
import { Kafka } from 'kafkajs';
import { loadConfig } from './config';
import { startOrderEventsConsumer } from './events/consumer';
import { KafkaPaymentEventPublisher } from './events/producer';
import { RedisIdempotencyStore } from './idempotency/store';
import { logger } from './logger';
import { PspClient } from './psp/client';
import { IntentIndex } from './psp/intent-index';
import { webhookRoute } from './webhooks/handler';

/** Composition root: every dependency is built here and passed in explicitly. */
async function main(): Promise<void> {
  const config = loadConfig();
  const kafka = new Kafka({ clientId: 'payment-gateway', brokers: config.kafkaBrokers });
  const producer = kafka.producer({ idempotent: true, maxInFlightRequests: 1 });
  const consumer = kafka.consumer({ groupId: config.consumerGroup });
  await Promise.all([producer.connect(), consumer.connect()]);
  const redis = new Redis(config.redisUrl);

  const app = express();
  app.post('/webhooks/psp', express.raw({ type: 'application/json', limit: '256kb' }), webhookRoute({
    secret: config.psp.webhookSecret,
    store: new RedisIdempotencyStore(redis),
    publisher: new KafkaPaymentEventPublisher(producer, config.topics.payments),
    toleranceSeconds: config.webhook.toleranceSeconds,
    dedupeTtlSeconds: config.webhook.dedupeTtlSeconds,
  }));
  app.get('/healthz', (_req, res) => {
    res.json({ status: 'ok' });
  });

  await startOrderEventsConsumer(consumer, config.topics.orders, {
    psp: new PspClient(config.psp),
    intents: new IntentIndex(redis),
  });
  const server = app.listen(config.port, () => logger.info({ port: config.port }, 'payment-gateway listening'));

  process.once('SIGTERM', async () => {
    server.close();
    await Promise.all([consumer.disconnect(), producer.disconnect()]);
    redis.disconnect();
  });
}

main().catch((err) => {
  logger.fatal({ err }, 'payment-gateway failed to start');
  process.exit(1);
});
