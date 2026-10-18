package com.shop.orders.api;

import com.shop.orders.domain.Order;
import com.shop.orders.domain.OrderStatus;
import com.shop.orders.inventory.InventoryClient.RequestedItem;
import com.shop.orders.inventory.OutOfStockException;
import com.shop.orders.service.OrderService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import java.net.URI;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.http.ProblemDetail;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

/** Public order API. Contract: contracts/orders.openapi.yaml. */
@RestController
@RequestMapping("/orders")
public class OrderController {

    private final OrderService orderService;

    public OrderController(OrderService orderService) {
        this.orderService = orderService;
    }

    /** Returns 201 with status PENDING_PAYMENT; payment is asynchronous, so the client polls GET. */
    @PostMapping
    public ResponseEntity<OrderResponse> create(@Valid @RequestBody CreateOrderRequest request) {
        List<RequestedItem> items = request.items().stream().map(i -> new RequestedItem(i.sku(), i.quantity())).toList();
        Order order = orderService.placeOrder(request.customerId(), request.currency(), items);
        return ResponseEntity.created(URI.create("/orders/" + order.getId())).body(OrderResponse.from(order));
    }

    @GetMapping("/{id}")
    public OrderResponse get(@PathVariable UUID id) {
        return orderService.findOrder(id).map(OrderResponse::from)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Order " + id + " not found"));
    }

    @ExceptionHandler(OutOfStockException.class)
    ProblemDetail outOfStock(OutOfStockException e) {
        return ProblemDetail.forStatusAndDetail(HttpStatus.CONFLICT, e.getMessage());
    }

    /** Max 20 lines per order and 1..10 units per line (fraud-team limits). */
    public record CreateOrderRequest(@NotBlank String customerId,
                                     @Pattern(regexp = "EUR|USD|GBP") String currency,
                                     @NotEmpty @Size(max = 20) List<@Valid Item> items) {
        public record Item(@NotBlank String sku, @Min(1) @Max(10) int quantity) {}
    }

    public record OrderResponse(UUID id, OrderStatus status, long totalCents, String currency,
                                String paymentId, Instant createdAt, List<Line> lines) {
        public record Line(String sku, int quantity, long unitPriceCents) {}

        static OrderResponse from(Order o) {
            List<Line> lines = o.getLines().stream()
                    .map(l -> new Line(l.getSku(), l.getQuantity(), l.getUnitPriceCents())).toList();
            return new OrderResponse(o.getId(), o.getStatus(), o.getTotalCents(), o.getCurrency(),
                    o.getPaymentId(), o.getCreatedAt(), lines);
        }
    }
}
