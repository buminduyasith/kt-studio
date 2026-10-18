package com.shop.orders.inventory;

import java.util.UUID;

/** Mapped to HTTP 409 by OrderController. */
public class OutOfStockException extends RuntimeException {

    public OutOfStockException(UUID orderId, String detail) {
        super("Stock unavailable for order " + orderId + ": " + detail);
    }
}
