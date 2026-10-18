package com.shop.orders.payments;

import jakarta.persistence.*;
import java.time.Instant;

/** Proof that a payment event was applied. Its primary key is what makes consumption idempotent. */
@Entity
@Table(name = "processed_events")
public class ProcessedEvent {

    @Id
    @Column(name = "event_id")
    private String eventId;
    @Column(name = "event_type", nullable = false)
    private String eventType;
    @Column(name = "processed_at", nullable = false)
    private Instant processedAt;

    protected ProcessedEvent() {
        // for JPA
    }

    public ProcessedEvent(String eventId, String eventType, Instant processedAt) {
        this.eventId = eventId;
        this.eventType = eventType;
        this.processedAt = processedAt;
    }
}
