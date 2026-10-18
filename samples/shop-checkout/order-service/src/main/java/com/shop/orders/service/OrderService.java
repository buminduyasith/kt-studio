package com.shop.orders.service;

import com.shop.orders.domain.Order;
import com.shop.orders.domain.Order.CancellationReason;
import com.shop.orders.domain.OrderLine;
import com.shop.orders.domain.OrderRepository;
import com.shop.orders.domain.OrderStatus;
import com.shop.orders.events.EventPublisher;
import com.shop.orders.events.OrderCancelled;
import com.shop.orders.events.OrderPlaced;
import com.shop.orders.inventory.InventoryClient;
import com.shop.orders.inventory.InventoryClient.RequestedItem;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/** Application service for the order lifecycle. All state changes to {@link Order} go through here. */
@Service
public class OrderService {

    private static final Logger log = LoggerFactory.getLogger(OrderService.class);

    private final OrderRepository orders;
    private final InventoryClient inventory;
    private final EventPublisher events;
    private final Clock clock;
    private final Duration paymentTimeout;

    public OrderService(OrderRepository orders, InventoryClient inventory, EventPublisher events, Clock clock,
                        @Value("${checkout.reservation.payment-timeout}") Duration paymentTimeout) {
        this.orders = orders;
        this.inventory = inventory;
        this.events = events;
        this.clock = clock;
        this.paymentTimeout = paymentTimeout;
    }

    /**
     * Reserves stock (which also snapshots prices), stores the order as PENDING_PAYMENT and
     * announces it with OrderPlaced so payment-gateway can open a payment intent.
     */
    @Transactional
    public Order placeOrder(String customerId, String currency, List<RequestedItem> items) {
        UUID orderId = UUID.randomUUID();
        // Reserve first so an OutOfStockException leaves nothing behind. If the insert below fails,
        // inventory-service drops the orphaned hold after its own 20-minute TTL.
        List<OrderLine> lines = inventory.reserve(orderId, items).lines().stream()
                .map(line -> new OrderLine(line.sku(), line.quantity(), line.unitPriceCents()))
                .toList();
        Instant now = clock.instant();
        Order order = orders.save(Order.create(orderId, customerId, currency, lines, now));

        // TODO(ORD-118): move to a transactional outbox. Today a commit failure after this send leaves
        // payment-gateway holding an OrderPlaced for an order that was never stored.
        events.publish(OrderPlaced.of(order, now.plus(paymentTimeout)));
        log.info("Order {} placed: total={} {}", orderId, order.getTotalCents(), currency);
        return order;
    }

    @Transactional(readOnly = true)
    public Optional<Order> findOrder(UUID orderId) {
        return orders.findById(orderId);
    }

    /** Applies a PaymentSucceeded event. Safe to call repeatedly for the same order. */
    @Transactional
    public void markPaid(UUID orderId, String paymentId, long amountCents) {
        Order order = load(orderId);
        switch (order.getStatus()) {
            case PENDING_PAYMENT -> {
                if (amountCents != order.getTotalCents()) {
                    // Leave it pending: the expiry job cancels it and finance reconciles the charge.
                    log.error("Payment {} amount {} != order {} total {}", paymentId, amountCents, orderId, order.getTotalCents());
                    return;
                }
                order.markPaid(paymentId, clock.instant());
            }
            // Paid after the reservation expired and the intent could not be cancelled in time.
            // TODO(PAY-260): publish RefundRequested instead of relying on the nightly finance reconciliation.
            case CANCELLED -> log.warn("Late payment {} for cancelled order {} needs a manual refund", paymentId, orderId);
            default -> log.debug("Order {} already {}, ignoring payment {}", orderId, order.getStatus(), paymentId);
        }
    }

    /** Cancels a PENDING_PAYMENT order, releases its stock and publishes OrderCancelled. False if not pending. */
    @Transactional
    public boolean cancel(UUID orderId, CancellationReason reason) {
        Order order = load(orderId);
        if (order.getStatus() != OrderStatus.PENDING_PAYMENT) {
            return false;
        }
        Instant now = clock.instant();
        order.cancel(reason, now);
        // Known gap (ORD-131): the release is an HTTP call made before commit. If the commit then fails on
        // the optimistic lock (a payment won the race), the paid order has lost its stock hold.
        inventory.release(orderId);
        events.publish(OrderCancelled.of(order, now));
        log.info("Order {} cancelled: {}", orderId, reason);
        return true;
    }

    private Order load(UUID orderId) {
        return orders.findById(orderId).orElseThrow(() -> new IllegalArgumentException("Unknown order " + orderId));
    }
}
