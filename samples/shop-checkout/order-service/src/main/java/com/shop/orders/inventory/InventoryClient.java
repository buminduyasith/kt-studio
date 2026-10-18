package com.shop.orders.inventory;

import java.util.List;
import java.util.UUID;

/** Client for inventory-service (owned by the Catalog team). */
public interface InventoryClient {

    /**
     * Holds stock and snapshots current prices. The hold lasts 20 minutes, longer than our 15-minute
     * payment window, so it never lapses under a live order.
     *
     * @throws OutOfStockException if any SKU cannot be fully reserved (nothing is held in that case)
     */
    Reservation reserve(UUID orderId, List<RequestedItem> items);

    /** Idempotent: releasing an unknown or already-released reservation is a no-op. */
    void release(UUID orderId);

    record RequestedItem(String sku, int quantity) {}
    record ReservedLine(String sku, int quantity, long unitPriceCents) {}
    record Reservation(String reservationId, List<ReservedLine> lines) {}
}
