package com.shop.orders.service;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.Mockito.*;

import com.shop.orders.domain.*;
import com.shop.orders.events.DomainEvent;
import com.shop.orders.events.EventPublisher;
import com.shop.orders.events.OrderPlaced;
import com.shop.orders.inventory.InventoryClient;
import com.shop.orders.inventory.InventoryClient.*;
import com.shop.orders.inventory.OutOfStockException;
import java.time.*;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class OrderServiceTest {

    private static final Instant NOW = Instant.parse("2026-03-02T10:00:00Z");

    @Mock OrderRepository orders;
    @Mock InventoryClient inventory;
    @Mock EventPublisher events;
    private OrderService service;

    @BeforeEach
    void setUp() {
        service = new OrderService(orders, inventory, events, Clock.fixed(NOW, ZoneOffset.UTC), Duration.ofMinutes(15));
    }

    @Test
    void placesOrderAsPendingPaymentAndPublishesOrderPlacedWithExpiry() {
        when(inventory.reserve(any(), anyList())).thenReturn(new Reservation("res-1", List.of(
                new ReservedLine("SKU-MUG-01", 2, 1_250), new ReservedLine("SKU-TEE-XL", 1, 4_999))));
        when(orders.save(any())).thenAnswer(invocation -> invocation.getArgument(0));

        Order order = service.placeOrder("cust-42", "EUR",
                List.of(new RequestedItem("SKU-MUG-01", 2), new RequestedItem("SKU-TEE-XL", 1)));

        assertThat(order.getStatus()).isEqualTo(OrderStatus.PENDING_PAYMENT);
        assertThat(order.getTotalCents()).isEqualTo(7_499);
        ArgumentCaptor<DomainEvent> published = ArgumentCaptor.forClass(DomainEvent.class);
        verify(events).publish(published.capture());
        OrderPlaced placed = (OrderPlaced) published.getValue();
        assertThat(placed.payload().orderId()).isEqualTo(order.getId());
        assertThat(placed.payload().expiresAt()).isEqualTo(Instant.parse("2026-03-02T10:15:00Z"));
    }

    @Test
    void outOfStockLeavesNoOrderAndPublishesNothing() {
        when(inventory.reserve(any(), anyList())).thenThrow(new OutOfStockException(UUID.randomUUID(), "SKU-MUG-01"));

        assertThatThrownBy(() -> service.placeOrder("cust-42", "EUR", List.of(new RequestedItem("SKU-MUG-01", 10))))
                .isInstanceOf(OutOfStockException.class);
        verifyNoInteractions(orders, events);
    }

    @Test
    void cancelIsANoOpOnceTheOrderIsPaid() {
        Order order = Order.create(UUID.randomUUID(), "cust-42", "EUR", List.of(new OrderLine("SKU-MUG-01", 1, 1_250)), NOW);
        order.markPaid("pi_123", NOW);
        when(orders.findById(order.getId())).thenReturn(Optional.of(order));

        assertThat(service.cancel(order.getId(), Order.CancellationReason.PAYMENT_TIMEOUT)).isFalse();
        assertThat(order.getStatus()).isEqualTo(OrderStatus.PAID);
        verify(inventory, never()).release(any());
        verifyNoInteractions(events);
    }
}
