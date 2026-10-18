import type { RequestHandler } from 'express';
import type { PaymentEventPublisher } from '../events/producer';
import type { PaymentEvent } from '../events/types';
import type { IdempotencyStore } from '../idempotency/store';
import { logger } from '../logger';
import { SIGNATURE_HEADER, verifySignature } from './verify';

/** The subset of a PSP webhook event we rely on. */
export interface PspWebhookEvent {
  id: string; // evt_..., stable across redeliveries
  type: string;
  created: number; // unix seconds
  data: { object: {
    id: string; // payment intent id
    amount: number;
    currency: string;
    metadata?: { orderId?: string };
    last_payment_error?: { code?: string; message?: string };
  } };
}

export interface WebhookDeps {
  secret: string;
  store: IdempotencyStore;
  publisher: PaymentEventPublisher;
  toleranceSeconds: number; // 300 in production
  dedupeTtlSeconds: number; // 86_400 in production
  now?: () => number;
}

/**
 * Declines the customer cannot fix in the same checkout. Soft declines (insufficient_funds,
 * authentication_required, ...) are only logged: the customer may try another card until the
 * 15-minute reservation runs out, and order-service's ReservationExpiryJob cleans up after that.
 */
const HARD_DECLINE_CODES = new Set(['fraudulent', 'stolen_card', 'lost_card', 'pickup_card', 'restricted_card']);

/** Maps a PSP event to our domain event, or null if order-service does not need to hear about it. */
export function toPaymentEvent(event: PspWebhookEvent): PaymentEvent | null {
  const intent = event.data.object;
  const orderId = intent.metadata?.orderId;
  if (!orderId) return null; // not an intent we opened (e.g. a dashboard test payment)

  // Reusing the PSP event id as our eventId lets order-service dedupe on it as well.
  const base = { eventId: event.id, occurredAt: new Date(event.created * 1000).toISOString() };
  if (event.type === 'payment_intent.succeeded') {
    return { ...base, type: 'PaymentSucceeded', payload: {
      orderId, paymentId: intent.id, amountCents: intent.amount, currency: intent.currency.toUpperCase() } };
  }
  if (event.type === 'payment_intent.payment_failed') {
    const code = intent.last_payment_error?.code ?? 'unknown';
    if (!HARD_DECLINE_CODES.has(code)) return null;
    return { ...base, type: 'PaymentFailed', payload: {
      orderId, paymentId: intent.id, failureCode: code, failureMessage: intent.last_payment_error?.message ?? '' } };
  }
  return null;
}

export async function processWebhook(rawBody: Buffer, signatureHeader: string | undefined, deps: WebhookDeps)
  : Promise<{ status: number; body: Record<string, unknown> }> {
  const now = deps.now ?? Date.now;
  const verdict = verifySignature(rawBody, signatureHeader, deps.secret, now(), deps.toleranceSeconds);
  if (!verdict.ok) {
    logger.warn({ reason: verdict.reason }, 'Rejected PSP webhook');
    return { status: verdict.reason === 'stale' ? 400 : 401, body: { error: verdict.reason } };
  }

  const event = JSON.parse(rawBody.toString('utf8')) as PspWebhookEvent;
  const paymentEvent = toPaymentEvent(event);
  // Always 2xx for events we ignore, or the PSP keeps redelivering them for 24h.
  if (!paymentEvent) return { status: 200, body: { ignored: event.type } };

  // PAY-231 follow-up: the PSP redelivers on any non-2xx or on a response slower than 10s, and each
  // redelivery used to become a new PaymentSucceeded. Claim the PSP event id; only the first delivery publishes.
  const key = `psp-event:${event.id}`;
  if (!(await deps.store.claim(key, deps.dedupeTtlSeconds))) {
    logger.info({ pspEventId: event.id }, 'Duplicate PSP delivery ignored');
    return { status: 200, body: { duplicate: true } };
  }
  try {
    await deps.publisher.publish(paymentEvent);
  } catch (err) {
    // Give the claim back and answer 503 so the PSP redelivers; otherwise the outcome would be lost.
    await deps.store.release(key);
    logger.error({ err, pspEventId: event.id }, 'Publishing payment event failed');
    return { status: 503, body: { error: 'publish_failed' } };
  }
  return { status: 200, body: { received: true } };
}

/** Express adapter. Must be mounted behind `express.raw()`: the HMAC covers the exact bytes received. */
export function webhookRoute(deps: WebhookDeps): RequestHandler {
  return (req, res, next) => {
    if (!Buffer.isBuffer(req.body)) {
      res.status(415).json({ error: 'expected application/json' });
      return;
    }
    processWebhook(req.body, req.header(SIGNATURE_HEADER), deps)
      .then((result) => res.status(result.status).json(result.body))
      .catch(next);
  };
}
