package com.shop.orders.events;

import java.time.Instant;
import java.util.UUID;

/** Envelope shared by every event order-service publishes to orders.events. */
public interface DomainEvent {
    UUID eventId();
    String type();
    Instant occurredAt();
    /** Kafka key. All events of one order share a partition, so consumers see them in order. */
    String partitionKey();
}
