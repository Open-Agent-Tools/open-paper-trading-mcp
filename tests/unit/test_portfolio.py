from fastapi.testclient import TestClient


def test_get_portfolio(client: TestClient):
    """Test getting the portfolio."""
    response = client.get("/api/v1/portfolio/")
    assert response.status_code == 200
    data = response.json()
    assert "cash_balance" in data
    assert "total_value" in data
    assert "positions" in data
    assert "daily_pnl" in data
    assert "total_pnl" in data
    assert isinstance(data["positions"], list)


def test_get_portfolio_summary(client: TestClient):
    """Test getting the portfolio summary."""
    response = client.get("/api/v1/portfolio/summary")
    assert response.status_code == 200
    data = response.json()
    assert "total_value" in data
    assert "cash_balance" in data
    assert "invested_value" in data
    assert "daily_pnl" in data
    assert "daily_pnl_percent" in data
    assert "total_pnl" in data
    assert "total_pnl_percent" in data


def test_get_positions(client: TestClient):
    """Test getting all positions."""
    response = client.get("/api/v1/portfolio/positions")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if data:  # If there are positions
        position = data[0]
        assert "symbol" in position
        assert "quantity" in position
        assert "avg_price" in position
        assert "current_price" in position
        assert "unrealized_pnl" in position


def test_get_position_by_symbol(client: TestClient):
    """Test getting a specific position by symbol."""
    response = client.get("/api/v1/portfolio/position/AAPL")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "AAPL"
    assert "quantity" in data
    assert "avg_price" in data
    assert "current_price" in data
    assert "unrealized_pnl" in data


def test_get_position_invalid_symbol(client: TestClient):
    """Test getting a position for an invalid symbol."""
    response = client.get("/api/v1/portfolio/position/INVALID")
    assert response.status_code == 404
