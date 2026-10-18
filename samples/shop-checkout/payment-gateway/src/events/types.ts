/** Wire format shared with order-service. Source of truth: contracts/events.asyncapi.yaml. */
export interface EventEnvelope<TType extends string, TPayload> {
  eventId: string;
  type: TType;
  occurredAt: string; // ISO-8601
  payload: TPayload;
}

export type OrderPlaced = EventEnvelope<'OrderPlaced',
  { orderId: string; customerId: string; amountCents: number; currency: string; expiresAt: string }>;
export type OrderCancelled = EventEnvelope<'OrderCancelled',
  { orderId: string; reason: 'PAYMENT_FAILED' | 'PAYMENT_TIMEOUT' }>;
export type PaymentSucceeded = EventEnvelope<'PaymentSucceeded',
  { orderId: string; paymentId: string; amountCents: number; currency: string }>;
export type PaymentFailed = EventEnvelope<'PaymentFailed',
  { orderId: string; paymentId: string; failureCode: string; failureMessage: string }>;

export type OrderEvent = OrderPlaced | OrderCancelled;
export type PaymentEvent = PaymentSucceeded | PaymentFailed;
