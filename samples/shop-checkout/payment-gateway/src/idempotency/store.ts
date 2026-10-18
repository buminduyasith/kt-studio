/** The slice of the ioredis API we use. */
export interface RedisLike {
  set(key: string, value: string, secondsToken: 'EX', seconds: number): Promise<'OK'>;
  set(key: string, value: string, secondsToken: 'EX', seconds: number, nx: 'NX'): Promise<'OK' | null>;
  get(key: string): Promise<string | null>;
  del(key: string): Promise<number>;
}

export interface IdempotencyStore {
  /** Atomically claims `key` for `ttlSeconds`. Resolves true only for the first caller in that window. */
  claim(key: string, ttlSeconds: number): Promise<boolean>;
  /** Gives a claim back, so a later retry of the same key is processed again. */
  release(key: string): Promise<void>;
}

export class RedisIdempotencyStore implements IdempotencyStore {
  constructor(private readonly redis: RedisLike, private readonly prefix = 'idem:') {}

  async claim(key: string, ttlSeconds: number): Promise<boolean> {
    // SET NX EX is one atomic command: two deliveries racing on different pods cannot both win.
    return (await this.redis.set(this.prefix + key, '1', 'EX', ttlSeconds, 'NX')) === 'OK';
  }

  async release(key: string): Promise<void> {
    await this.redis.del(this.prefix + key);
  }
}

/** Single-process store for tests and local development. */
export class InMemoryIdempotencyStore implements IdempotencyStore {
  private readonly expiries = new Map<string, number>();
  constructor(private readonly now: () => number = Date.now) {}

  async claim(key: string, ttlSeconds: number): Promise<boolean> {
    if ((this.expiries.get(key) ?? 0) > this.now()) return false;
    this.expiries.set(key, this.now() + ttlSeconds * 1000);
    return true;
  }

  async release(key: string): Promise<void> {
    this.expiries.delete(key);
  }
}
