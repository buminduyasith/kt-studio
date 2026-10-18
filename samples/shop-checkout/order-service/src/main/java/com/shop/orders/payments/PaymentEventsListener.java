package com.shop.orders.payments;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.shop.orders.domain.Order.CancellationReason;
import com.shop.orders.service.OrderService;
import java.time.Clock;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

/**
 * Applies payment outcomes from payment-gateway to orders.
 *
 * <p>Delivery is at-least-once (producer retries, rebalances, PSP redeliveries older than the gateway's
 * 24h dedupe window). The processed_events insert commits in the same transaction as the order update,
 * so each eventId is applied once. If two copies race, the second insert hits the primary key, rolls back,
 * and is skipped on retry. Failures are retried by Spring Kafka's DefaultErrorHandler (10 attempts), then logged.
 */
@Component
public class PaymentEventsListener {

    private static final Logger log = LoggerFactory.getLogger(PaymentEventsListener.class);

    private final OrderService orderService;
    private final ProcessedEventRepository processedEvents;
    private final ObjectMapper json;
    private final Clock clock;

    public PaymentEventsListener(OrderService orderService, ProcessedEventRepository processedEvents,
                                 ObjectMapper json, Clock clock) {
        this.orderService = orderService;
        this.processedEvents = processedEvents;
        this.json = json;
        this.clock = clock;
    }

    @KafkaListener(topics = "payments.events", groupId = "order-service")
    @Transactional
    public void onPaymentEvent(String message) throws JsonProcessingException {
        PaymentEvent event = json.readValue(message, PaymentEvent.class);
        if (processedEvents.existsById(event.eventId())) {
            log.info("Skipping already processed {} {}", event.type(), event.eventId());
            return;
        }
        PaymentEvent.Payload p = event.payload();
        switch (event.type()) {
            case "PaymentSucceeded" -> orderService.markPaid(p.orderId(), p.paymentId(), p.amountCents());
            case "PaymentFailed" -> {
                log.info("Payment failed for order {}: {}", p.orderId(), p.failureCode());
                orderService.cancel(p.orderId(), CancellationReason.PAYMENT_FAILED);
            }
            default -> log.debug("Ignoring unknown payment event type {}", event.type());
        }
        processedEvents.save(new ProcessedEvent(event.eventId(), event.type(), clock.instant()));
    }
}
