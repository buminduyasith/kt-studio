package com.shop.orders.domain;

import jakarta.persistence.*;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

/** A customer order. State changes only go through the transition methods below. */
@Entity
@Table(name = "orders")
public class Order {

    public enum CancellationReason { PAYMENT_FAILED, PAYMENT_TIMEOUT }

    @Id
    private UUID id;
    @Column(name = "customer_id", nullable = false)
    private String customerId;
    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private OrderStatus status;
    @Column(name = "total_cents", nullable = false)
    private long totalCents;
    @Column(nullable = false, length = 3)
    private String currency;
    /** PSP payment intent id, set when the order is paid. */
    @Column(name = "payment_id")
    private String paymentId;
    @Enumerated(EnumType.STRING)
    @Column(name = "cancellation_reason")
    private CancellationReason cancellationReason;
    @Column(name = "created_at", nullable = false)
    private Instant createdAt;
    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    /** Optimistic lock: ReservationExpiryJob and PaymentEventsListener can race on the same order. */
    @Version
    private long version;

    @ElementCollection(fetch = FetchType.EAGER)
    @CollectionTable(name = "order_lines", joinColumns = @JoinColumn(name = "order_id"))
    private List<OrderLine> lines = new ArrayList<>();

    protected Order() {
        // for JPA
    }

    public static Order create(UUID id, String customerId, String currency, List<OrderLine> lines, Instant now) {
        Order order = new Order();
        order.id = id;
        order.customerId = customerId;
        order.currency = currency;
        order.lines = new ArrayList<>(lines);
        order.totalCents = lines.stream().mapToLong(OrderLine::lineTotalCents).sum();
        order.status = OrderStatus.PENDING_PAYMENT;
        order.createdAt = now;
        order.updatedAt = now;
        return order;
    }

    public void markPaid(String paymentId, Instant now) {
        transition(OrderStatus.PENDING_PAYMENT, OrderStatus.PAID, now);
        this.paymentId = paymentId;
    }

    public void markShipped(Instant now) {
        transition(OrderStatus.PAID, OrderStatus.SHIPPED, now);
    }

    public void cancel(CancellationReason reason, Instant now) {
        transition(OrderStatus.PENDING_PAYMENT, OrderStatus.CANCELLED, now);
        this.cancellationReason = reason;
    }

    private void transition(OrderStatus expected, OrderStatus next, Instant now) {
        if (status != expected) {
            throw new IllegalStateException("Order %s cannot move %s -> %s".formatted(id, status, next));
        }
        this.status = next;
        this.updatedAt = now;
    }

    public UUID getId() { return id; }
    public String getCustomerId() { return customerId; }
    public OrderStatus getStatus() { return status; }
    public long getTotalCents() { return totalCents; }
    public String getCurrency() { return currency; }
    public String getPaymentId() { return paymentId; }
    public CancellationReason getCancellationReason() { return cancellationReason; }
    public Instant getCreatedAt() { return createdAt; }
    public List<OrderLine> getLines() { return List.copyOf(lines); }
}
