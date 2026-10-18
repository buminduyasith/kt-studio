function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`Missing required env var ${name}`);
  return value;
}

export function loadConfig() {
  return {
    port: Number(process.env.PORT ?? 3002),
    kafkaBrokers: (process.env.KAFKA_BROKERS ?? 'localhost:9092').split(','),
    consumerGroup: 'payment-gateway',
    topics: { orders: 'orders.events', payments: 'payments.events' },
    redisUrl: process.env.REDIS_URL ?? 'redis://localhost:6379',
    psp: {
      baseUrl: process.env.PSP_BASE_URL ?? 'https://api.stripelike.test/v1',
      apiKey: required('PSP_API_KEY'),
      webhookSecret: required('PSP_WEBHOOK_SECRET'),
      timeoutMs: 5_000,
    },
    webhook: {
      toleranceSeconds: 5 * 60, // reject webhook events signed more than 5 minutes ago
      dedupeTtlSeconds: 24 * 60 * 60, // the PSP retries failed deliveries for up to 24h
    },
  };
}

export type Config = ReturnType<typeof loadConfig>;
