from fastapi.testclient import TestClient


def test_get_quote_valid_symbol(client: TestClient) -> None:
    """Test getting a quote for a valid symbol."""
    response = client.get("/api/v1/trading/quote/AAPL")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "AAPL"
    assert "price" in data
    assert "change" in data
    assert "volume" in data


def test_get_quote_invalid_symbol(client: TestClient) -> None:
    """Test getting a quote for an invalid symbol."""
    response = client.get("/api/v1/trading/quote/INVALID")
    assert response.status_code == 404


def test_create_order(client: TestClient) -> None:
    """Test creating a new order."""
    order_data = {"symbol": "AAPL", "order_type": "buy", "quantity": 10, "price": 150.0}
    response = client.post("/api/v1/trading/order", json=order_data)
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "AAPL"
    assert data["order_type"] == "buy"
    assert data["quantity"] == 10
    assert data["price"] == 150.0
    assert data["status"] == "pending"
    assert "id" in data


def test_get_orders(client: TestClient) -> None:
    """Test getting all orders."""
    response = client.get("/api/v1/trading/orders")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_get_order_by_id(client: TestClient) -> None:
    """Test getting a specific order by ID."""
    # First create an order
    order_data = {
        "symbol": "GOOGL",
        "order_type": "sell",
        "quantity": 5,
        "price": 2800.0,
    }
    create_response = client.post("/api/v1/trading/order", json=order_data)
    order_id = create_response.json()["id"]

    # Then get it by ID
    response = client.get(f"/api/v1/trading/order/{order_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == order_id
    assert data["symbol"] == "GOOGL"


def test_cancel_order(client: TestClient) -> None:
    """Test canceling an order."""
    # First create an order
    order_data = {"symbol": "AAPL", "order_type": "buy", "quantity": 10, "price": 150.0}
    create_response = client.post("/api/v1/trading/order", json=order_data)
    order_id = create_response.json()["id"]

    # Then cancel it
    response = client.delete(f"/api/v1/trading/order/{order_id}")
    assert response.status_code == 200

    # Verify it's cancelled
    get_response = client.get(f"/api/v1/trading/order/{order_id}")
    assert get_response.json()["status"] == "cancelled"
