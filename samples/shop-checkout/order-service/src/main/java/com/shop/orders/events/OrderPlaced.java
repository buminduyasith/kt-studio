package com.shop.orders.events;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.shop.orders.domain.Order;
import java.time.Instant;
import java.util.UUID;

/** Consumed by payment-gateway, which opens a PSP payment intent that expires at {@code expiresAt}. */
public record OrderPlaced(UUID eventId, Instant occurredAt, Payload payload) implements DomainEvent {

    public record Payload(UUID orderId, String customerId, long amountCents, String currency, Instant expiresAt) {}

    public static OrderPlaced of(Order order, Instant expiresAt) {
        return new OrderPlaced(UUID.randomUUID(), order.getCreatedAt(), new Payload(
                order.getId(), order.getCustomerId(), order.getTotalCents(), order.getCurrency(), expiresAt));
    }

    @Override @JsonProperty("type")
    public String type() { return "OrderPlaced"; }

    @Override
    public String partitionKey() { return payload.orderId().toString(); }
}
