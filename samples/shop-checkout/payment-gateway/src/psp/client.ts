import { logger } from '../logger';

/** The fields we use from a StripeLike payment intent. */
export interface PaymentIntent {
  id: string; // pi_...
  status: 'requires_payment_method' | 'requires_action' | 'processing' | 'succeeded' | 'canceled';
  amount: number; // minor units
  currency: string; // lowercase ISO code
  client_secret: string;
}

export class PspError extends Error {
  constructor(message: string, readonly status?: number) {
    super(message);
    this.name = 'PspError';
  }
}

export interface PspClientOptions {
  baseUrl: string;
  apiKey: string;
  timeoutMs: number;
  maxAttempts?: number; // default 3
  baseDelayMs?: number; // default 200
}

const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

/** Thin wrapper around the StripeLike REST API with bounded retries. */
export class PspClient {
  constructor(private readonly opts: PspClientOptions) {}

  createPaymentIntent(
    input: { orderId: string; amountCents: number; currency: string; expiresAt: string },
    idempotencyKey: string,
  ): Promise<PaymentIntent> {
    return this.request('/payment_intents', {
      amount: input.amountCents,
      currency: input.currency.toLowerCase(),
      metadata: { orderId: input.orderId },
      expires_at: Math.floor(Date.parse(input.expiresAt) / 1000),
    }, idempotencyKey);
  }

  cancelPaymentIntent(intentId: string, idempotencyKey: string): Promise<PaymentIntent> {
    return this.request(`/payment_intents/${encodeURIComponent(intentId)}/cancel`,
      { cancellation_reason: 'abandoned' }, idempotencyKey);
  }

  /**
   * At most 3 attempts with backoff 200ms * 2^n (200ms, then 400ms), and only for 5xx and timeouts.
   * Retrying a POST is safe because the PSP replays the original response for a repeated Idempotency-Key.
   * Other 4xx (including 429) go straight back to the caller; Kafka redelivery is the outer retry loop.
   */
  private async request(path: string, body: unknown, idempotencyKey: string): Promise<PaymentIntent> {
    const maxAttempts = this.opts.maxAttempts ?? 3;
    for (let attempt = 0; ; attempt++) {
      try {
        return await this.post(path, body, idempotencyKey);
      } catch (err) {
        if (!isRetryable(err) || attempt + 1 >= maxAttempts) throw err;
        const delayMs = (this.opts.baseDelayMs ?? 200) * 2 ** attempt;
        logger.warn({ path, attempt: attempt + 1, delayMs, err: (err as Error).message }, 'PSP call failed, retrying');
        await sleep(delayMs);
      }
    }
  }

  private async post(path: string, body: unknown, idempotencyKey: string): Promise<PaymentIntent> {
    const res = await fetch(`${this.opts.baseUrl}${path}`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${this.opts.apiKey}`,
        'Content-Type': 'application/json',
        'Idempotency-Key': idempotencyKey,
      },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(this.opts.timeoutMs),
    });
    if (!res.ok) throw new PspError(`PSP POST ${path} failed with ${res.status}: ${await res.text()}`, res.status);
    return (await res.json()) as PaymentIntent;
  }
}

function isRetryable(err: unknown): boolean {
  if (err instanceof PspError) return err.status !== undefined && err.status >= 500;
  // AbortSignal.timeout() rejects fetch with a DOMException named "TimeoutError".
  return (err as { name?: string } | null)?.name === 'TimeoutError';
}
