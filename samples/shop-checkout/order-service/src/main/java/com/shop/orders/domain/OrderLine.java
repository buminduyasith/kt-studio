package com.shop.orders.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Embeddable;

/** One SKU on an order. The unit price is the snapshot inventory-service returned when stock was reserved. */
@Embeddable
public class OrderLine {

    private String sku;
    private int quantity;
    @Column(name = "unit_price_cents")
    private long unitPriceCents;

    protected OrderLine() {
        // for JPA
    }

    public OrderLine(String sku, int quantity, long unitPriceCents) {
        this.sku = sku;
        this.quantity = quantity;
        this.unitPriceCents = unitPriceCents;
    }

    public long lineTotalCents() { return unitPriceCents * quantity; }
    public String getSku() { return sku; }
    public int getQuantity() { return quantity; }
    public long getUnitPriceCents() { return unitPriceCents; }
}
