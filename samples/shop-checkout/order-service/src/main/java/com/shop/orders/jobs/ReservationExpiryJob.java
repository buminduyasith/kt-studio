package com.shop.orders.jobs;

import com.shop.orders.domain.Order;
import com.shop.orders.domain.Order.CancellationReason;
import com.shop.orders.domain.OrderRepository;
import com.shop.orders.domain.OrderStatus;
import com.shop.orders.service.OrderService;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.dao.OptimisticLockingFailureException;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/**
 * Cancels orders still PENDING_PAYMENT after {@code checkout.reservation.payment-timeout} (15 minutes) and
 * gives their stock back. Sweeps every 60 seconds, at most 100 orders per sweep.
 *
 * <p>Each order is cancelled in its own transaction (via OrderService), so one conflict does not roll back
 * the batch. Runs on every instance; the @Version check on Order lets exactly one writer win, and a payment
 * that commits first always wins.
 */
@Component
public class ReservationExpiryJob {

    private static final Logger log = LoggerFactory.getLogger(ReservationExpiryJob.class);

    private final OrderRepository orders;
    private final OrderService orderService;
    private final Clock clock;
    private final Duration paymentTimeout;

    public ReservationExpiryJob(OrderRepository orders, OrderService orderService, Clock clock,
                                @Value("${checkout.reservation.payment-timeout}") Duration paymentTimeout) {
        this.orders = orders;
        this.orderService = orderService;
        this.clock = clock;
        this.paymentTimeout = paymentTimeout;
    }

    @Scheduled(fixedDelayString = "${checkout.reservation.sweep-interval-ms}", initialDelay = 30_000)
    public void cancelExpiredOrders() {
        Instant cutoff = clock.instant().minus(paymentTimeout);
        int cancelled = 0;
        for (Order order : orders.findTop100ByStatusAndCreatedAtBeforeOrderByCreatedAtAsc(OrderStatus.PENDING_PAYMENT, cutoff)) {
            try {
                if (orderService.cancel(order.getId(), CancellationReason.PAYMENT_TIMEOUT)) {
                    cancelled++;
                }
            } catch (OptimisticLockingFailureException e) {
                log.info("Order {} changed while expiring (payment arrived?), skipping", order.getId());
            }
        }
        if (cancelled > 0) {
            log.info("Expired {} unpaid orders created before {}", cancelled, cutoff);
        }
    }
}
