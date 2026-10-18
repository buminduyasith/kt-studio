package com.shop.orders.events;

/** Outbound port for domain events. Production: {@link KafkaEventPublisher}; unit tests use a mock. */
public interface EventPublisher {
    /** Publishes synchronously; throws if the broker did not acknowledge the event. */
    void publish(DomainEvent event);
}
