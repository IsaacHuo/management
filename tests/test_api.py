from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from app.database import init_database
from app.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LIBRARY_DB_PATH", str(tmp_path / "library.db"))
    init_database(reset=True, seed=True)
    with TestClient(app) as test_client:
        yield test_client


def auth_headers(client: TestClient):
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "123456"},
    )
    assert response.status_code == 200
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_login_and_dashboard_stats(client):
    old_password = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "Admin@123456"},
    )
    assert old_password.status_code == 401

    headers = auth_headers(client)
    response = client.get("/api/dashboard/stats", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["books"] >= 5
    assert data["active_readers"] >= 3
    assert data["overdue_loans"] >= 1


def test_book_and_reader_crud(client):
    headers = auth_headers(client)

    book_payload = {
        "isbn": "9780000000001",
        "title": "测试驱动开发",
        "author": "Kent Beck",
        "publisher": "测试出版社",
        "category": "软件测试",
        "published_year": 2024,
        "total_count": 2,
        "available_count": 2,
        "location": "T区-01",
        "status": "active",
    }
    created_book = client.post("/api/books", json=book_payload, headers=headers)
    assert created_book.status_code == 201
    book_id = created_book.json()["item"]["id"]

    book_payload["title"] = "测试驱动开发（修订版）"
    updated_book = client.put(f"/api/books/{book_id}", json=book_payload, headers=headers)
    assert updated_book.status_code == 200
    assert updated_book.json()["item"]["title"] == "测试驱动开发（修订版）"

    reader_payload = {
        "card_no": "RTEST001",
        "name": "测试读者",
        "phone": "13900000000",
        "email": "reader@example.com",
        "department": "测试班级",
        "status": "active",
    }
    created_reader = client.post("/api/readers", json=reader_payload, headers=headers)
    assert created_reader.status_code == 201
    reader_id = created_reader.json()["item"]["id"]

    reader_payload["department"] = "测试班级 2"
    updated_reader = client.put(f"/api/readers/{reader_id}", json=reader_payload, headers=headers)
    assert updated_reader.status_code == 200
    assert updated_reader.json()["item"]["department"] == "测试班级 2"

    assert client.delete(f"/api/books/{book_id}", headers=headers).status_code == 200
    assert client.delete(f"/api/readers/{reader_id}", headers=headers).status_code == 200


def test_loan_stock_guard_and_return(client):
    headers = auth_headers(client)

    book = client.post(
        "/api/books",
        json={
            "isbn": "9780000000002",
            "title": "单本库存图书",
            "author": "库存作者",
            "publisher": "测试出版社",
            "category": "库存",
            "published_year": 2025,
            "total_count": 1,
            "available_count": 1,
            "location": "S区-01",
            "status": "active",
        },
        headers=headers,
    ).json()["item"]
    reader = client.post(
        "/api/readers",
        json={
            "card_no": "RTEST002",
            "name": "借阅测试读者",
            "phone": "",
            "email": "",
            "department": "",
            "status": "active",
        },
        headers=headers,
    ).json()["item"]

    first_loan = client.post(
        "/api/loans",
        json={"book_id": book["id"], "reader_id": reader["id"], "days": 30, "note": "库存测试"},
        headers=headers,
    )
    assert first_loan.status_code == 201
    loan_id = first_loan.json()["item"]["id"]

    second_loan = client.post(
        "/api/loans",
        json={"book_id": book["id"], "reader_id": reader["id"], "days": 30},
        headers=headers,
    )
    assert second_loan.status_code == 400
    assert "库存" in second_loan.json()["detail"]

    returned = client.post(f"/api/loans/{loan_id}/return", json={}, headers=headers)
    assert returned.status_code == 200
    assert returned.json()["item"]["loan_status"] == "returned"

    books = client.get("/api/books?q=单本库存图书", headers=headers).json()["items"]
    assert books[0]["available_count"] == 1


def test_overdue_endpoint_has_seed_record(client):
    headers = auth_headers(client)
    response = client.get("/api/loans/overdue", headers=headers)
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) >= 1
    assert all(item["loan_status"] == "overdue" for item in items)
