package com.shop.orders.inventory;

import java.util.List;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestClient;

@Component
class HttpInventoryClient implements InventoryClient {

    private final RestClient http;

    HttpInventoryClient(RestClient.Builder builder, @Value("${checkout.inventory.base-url}") String baseUrl) {
        this.http = builder.baseUrl(baseUrl).build();
    }

    @Override
    public Reservation reserve(UUID orderId, List<RequestedItem> items) {
        try {
            return http.post()
                    .uri("/reservations")
                    .body(new ReserveRequest(orderId, items))
                    .retrieve()
                    .body(Reservation.class);
        } catch (HttpClientErrorException.Conflict e) {
            throw new OutOfStockException(orderId, e.getResponseBodyAsString());
        }
    }

    @Override
    public void release(UUID orderId) {
        http.delete().uri("/reservations/{orderId}", orderId).retrieve().toBodilessEntity();
    }

    private record ReserveRequest(UUID orderId, List<RequestedItem> items) {}
}
