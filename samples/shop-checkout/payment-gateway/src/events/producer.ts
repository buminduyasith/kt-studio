import type { Producer } from 'kafkajs';
import type { PaymentEvent } from './types';

/** Outbound port for payment outcomes; the webhook handler depends on this, not on Kafka. */
export interface PaymentEventPublisher {
  publish(event: PaymentEvent): Promise<void>;
}

export class KafkaPaymentEventPublisher implements PaymentEventPublisher {
  /** `producer` must be created with `idempotent: true` so broker-side retries never duplicate a message. */
  constructor(private readonly producer: Producer, private readonly topic: string) {}

  async publish(event: PaymentEvent): Promise<void> {
    await this.producer.send({
      topic: this.topic,
      acks: -1, // wait for all in-sync replicas
      messages: [{
        key: event.payload.orderId, // same partition as the order's other events
        value: JSON.stringify(event),
        headers: { 'event-type': event.type },
      }],
    });
  }
}
