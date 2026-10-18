package com.shop.orders.domain;

/**
 * PENDING_PAYMENT -> PAID -> SHIPPED, or PENDING_PAYMENT -> CANCELLED (payment failed / unpaid after 15 min).
 * Transitions are enforced by {@link Order}.
 */
public enum OrderStatus { PENDING_PAYMENT, PAID, SHIPPED, CANCELLED }
