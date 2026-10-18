import type { RedisLike } from '../idempotency/store';

const TTL_SECONDS = 24 * 60 * 60;

/** Remembers which PSP intent belongs to which order, so an OrderCancelled can cancel it. */
export class IntentIndex {
  constructor(private readonly redis: RedisLike) {}

  async remember(orderId: string, intentId: string): Promise<void> {
    await this.redis.set(`intent:${orderId}`, intentId, 'EX', TTL_SECONDS);
  }

  lookup(orderId: string): Promise<string | null> {
    return this.redis.get(`intent:${orderId}`);
  }
}
