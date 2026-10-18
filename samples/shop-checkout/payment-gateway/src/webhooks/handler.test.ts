import { beforeEach, describe, expect, it, vi } from 'vitest';
import { InMemoryIdempotencyStore } from '../idempotency/store';
import { processWebhook, type WebhookDeps } from './handler';
import { signPayload } from './verify';

const SECRET = 'whsec_test_8f2c';
const NOW = Date.parse('2026-03-02T10:00:00Z');

function pspEvent(id = 'evt_1001', type = 'payment_intent.succeeded', declineCode?: string) {
  const last_payment_error = declineCode ? { code: declineCode, message: 'Your card was declined.' } : undefined;
  return { id, type, created: NOW / 1000 - 5, data: { object: {
    id: 'pi_789', amount: 7499, currency: 'eur', metadata: { orderId: 'ord-42' }, last_payment_error } } };
}

function signed(event: object, signedAtMs = NOW) {
  const body = Buffer.from(JSON.stringify(event));
  return { body, header: signPayload(body, SECRET, Math.floor(signedAtMs / 1000)) };
}

describe('processWebhook', () => {
  const publish = vi.fn();
  let deps: WebhookDeps;

  beforeEach(() => {
    publish.mockReset().mockResolvedValue(undefined);
    deps = { secret: SECRET, store: new InMemoryIdempotencyStore(() => NOW), publisher: { publish },
      toleranceSeconds: 300, dedupeTtlSeconds: 86_400, now: () => NOW };
  });

  it('publishes PaymentSucceeded for a correctly signed event', async () => {
    const { body, header } = signed(pspEvent());

    expect((await processWebhook(body, header, deps)).status).toBe(200);
    expect(publish).toHaveBeenCalledWith(expect.objectContaining({
      eventId: 'evt_1001',
      type: 'PaymentSucceeded',
      payload: { orderId: 'ord-42', paymentId: 'pi_789', amountCents: 7499, currency: 'EUR' },
    }));
  });

  it('rejects a body that was changed after signing', async () => {
    const { header } = signed(pspEvent());
    const tampered = Buffer.from(JSON.stringify(pspEvent('evt_forged')));

    expect(await processWebhook(tampered, header, deps)).toEqual({ status: 401, body: { error: 'bad_signature' } });
    expect(publish).not.toHaveBeenCalled();
  });

  it('rejects events signed more than 5 minutes ago', async () => {
    const { body, header } = signed(pspEvent(), NOW - 6 * 60 * 1000);

    expect(await processWebhook(body, header, deps)).toEqual({ status: 400, body: { error: 'stale' } });
    expect(publish).not.toHaveBeenCalled();
  });

  it('publishes only once when the PSP redelivers the same event (PAY-231)', async () => {
    const { body, header } = signed(pspEvent());

    await processWebhook(body, header, deps);
    expect((await processWebhook(body, header, deps)).body).toEqual({ duplicate: true });
    expect(publish).toHaveBeenCalledTimes(1);
  });

  it('releases the claim when publishing fails so the PSP retry goes through', async () => {
    publish.mockRejectedValueOnce(new Error('broker unavailable'));
    const { body, header } = signed(pspEvent());

    expect((await processWebhook(body, header, deps)).status).toBe(503);
    expect((await processWebhook(body, header, deps)).status).toBe(200);
    expect(publish).toHaveBeenCalledTimes(2);
  });

  it('publishes PaymentFailed for hard declines only', async () => {
    const soft = signed(pspEvent('evt_2001', 'payment_intent.payment_failed', 'insufficient_funds'));
    const hard = signed(pspEvent('evt_2002', 'payment_intent.payment_failed', 'stolen_card'));

    await processWebhook(soft.body, soft.header, deps);
    await processWebhook(hard.body, hard.header, deps);

    expect(publish).toHaveBeenCalledTimes(1);
    expect(publish).toHaveBeenCalledWith(expect.objectContaining({
      eventId: 'evt_2002', type: 'PaymentFailed', payload: expect.objectContaining({ failureCode: 'stolen_card' }),
    }));
  });
});
