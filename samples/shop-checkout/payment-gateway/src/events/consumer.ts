import type { Consumer } from 'kafkajs';
import { logger } from '../logger';
import { PspClient, PspError } from '../psp/client';
import type { IntentIndex } from '../psp/intent-index';
import type { OrderEvent } from './types';

export interface OrderEventDeps {
  psp: PspClient;
  intents: IntentIndex;
  now?: () => number;
}

export async function handleOrderEvent(event: OrderEvent, { psp, intents, now = Date.now }: OrderEventDeps): Promise<void> {
  const { orderId } = event.payload;

  if (event.type === 'OrderPlaced') {
    const { amountCents, currency, expiresAt } = event.payload;
    if (Date.parse(expiresAt) <= now()) {
      logger.warn({ orderId, expiresAt }, 'OrderPlaced arrived after its reservation expired; no intent opened');
      return;
    }
    // PAY-231 (Nov 2025): a consumer-group rebalance redelivered ~40 OrderPlaced messages and each one
    // opened a second payment intent, so some customers were charged twice. The Idempotency-Key is now
    // derived from the order id: a redelivery gets back the intent that already exists.
    const intent = await psp.createPaymentIntent({ orderId, amountCents, currency, expiresAt }, `order-${orderId}`);
    await intents.remember(orderId, intent.id);
    logger.info({ orderId, intentId: intent.id }, 'Payment intent opened');
    return;
  }

  // OrderCancelled: close the intent so a late payment cannot be captured.
  const intentId = await intents.lookup(orderId);
  if (!intentId) return;
  try {
    await psp.cancelPaymentIntent(intentId, `cancel-${orderId}`);
  } catch (err) {
    // 400 means the intent already succeeded or was cancelled. If it succeeded, order-service receives a
    // PaymentSucceeded for a CANCELLED order and flags it for a manual refund (PAY-260).
    if (!(err instanceof PspError && err.status === 400)) throw err;
    logger.warn({ orderId, intentId }, 'Intent no longer cancellable');
  }
}

/**
 * Consumes orders.events. A thrown error makes kafkajs retry the message (then restart the consumer),
 * so PSP failures that outlive PspClient's own 3 attempts are retried again from Kafka.
 */
export async function startOrderEventsConsumer(consumer: Consumer, topic: string, deps: OrderEventDeps): Promise<void> {
  await consumer.subscribe({ topics: [topic], fromBeginning: false });
  await consumer.run({
    eachMessage: async ({ message }) => {
      if (!message.value) return;
      await handleOrderEvent(JSON.parse(message.value.toString()) as OrderEvent, deps);
    },
  });
}
