package com.shop.orders.payments;

import java.time.Instant;
import java.util.UUID;

/**
 * Envelope published by payment-gateway on payments.events (see contracts/events.asyncapi.yaml).
 * {@code eventId} is the PSP's webhook event id, so it is stable across redeliveries.
 */
public record PaymentEvent(String eventId, String type, Instant occurredAt, Payload payload) {

    /** amountCents/currency are set for PaymentSucceeded, failureCode/failureMessage for PaymentFailed. */
    public record Payload(UUID orderId, String paymentId, Long amountCents, String currency,
                          String failureCode, String failureMessage) {}
}
