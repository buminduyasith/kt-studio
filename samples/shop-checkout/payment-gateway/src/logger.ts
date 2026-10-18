import pino from 'pino';

export const logger = pino({ name: 'payment-gateway', level: process.env.LOG_LEVEL ?? 'info' });
