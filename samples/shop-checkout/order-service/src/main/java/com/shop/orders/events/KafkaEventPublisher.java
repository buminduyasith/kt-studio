package com.shop.orders.events;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.concurrent.TimeUnit;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Component;

@Component
class KafkaEventPublisher implements EventPublisher {

    private final KafkaTemplate<String, String> kafka;
    private final ObjectMapper json;
    private final String topic;

    KafkaEventPublisher(KafkaTemplate<String, String> kafka, ObjectMapper json,
                        @Value("${checkout.topics.orders}") String topic) {
        this.kafka = kafka;
        this.json = json;
        this.topic = topic;
    }

    @Override
    public void publish(DomainEvent event) {
        try {
            // Block (max 5s) until the broker acks, so a failed send rolls back the caller's transaction.
            kafka.send(topic, event.partitionKey(), json.writeValueAsString(event)).get(5, TimeUnit.SECONDS);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("Interrupted publishing " + event.type(), e);
        } catch (Exception e) {
            throw new IllegalStateException("Failed to publish " + event.type() + " " + event.eventId(), e);
        }
    }
}
