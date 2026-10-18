package com.shop.orders.events;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.shop.orders.domain.Order;
import java.time.Instant;
import java.util.UUID;

/** Consumed by payment-gateway, which cancels the open intent so a late payment cannot be captured. */
public record OrderCancelled(UUID eventId, Instant occurredAt, Payload payload) implements DomainEvent {

    public record Payload(UUID orderId, Order.CancellationReason reason) {}

    public static OrderCancelled of(Order order, Instant now) {
        return new OrderCancelled(UUID.randomUUID(), now, new Payload(order.getId(), order.getCancellationReason()));
    }

    @Override @JsonProperty("type")
    public String type() { return "OrderCancelled"; }

    @Override
    public String partitionKey() { return payload.orderId().toString(); }
}
