package com.shop.orders.domain;

import java.time.Instant;
import java.util.List;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface OrderRepository extends JpaRepository<Order, UUID> {

    /** Oldest-first batch (max 100) of orders in {@code status} created before {@code cutoff}. */
    List<Order> findTop100ByStatusAndCreatedAtBeforeOrderByCreatedAtAsc(OrderStatus status, Instant cutoff);
}
