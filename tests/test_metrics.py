import pytest
import app.app as app_module


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(app_module.time, "sleep", lambda _: None)
    with app_module.app.test_client() as client:
        yield client


def test_home_counter_and_histogram(client):
    counter = app_module.REQUEST_COUNT.labels(
        method="GET", endpoint="/", status="200"
    )
    before = counter._value.get()

    response = client.get("/")

    assert response.status_code == 200
    assert counter._value.get() == before + 1

    metrics_response = client.get("/metrics")
    metrics_text = metrics_response.get_data(as_text=True)

    assert 'http_request_duration_seconds_count{endpoint="/"}' in metrics_text


def test_work_success(client, monkeypatch):
    monkeypatch.setattr(app_module.random, "random", lambda: 0.5)

    counter = app_module.REQUEST_COUNT.labels(
        method="GET", endpoint="/work", status="200"
    )
    before = counter._value.get()

    response = client.get("/work")

    assert response.status_code == 200
    assert counter._value.get() == before + 1

    metrics_response = client.get("/metrics")
    metrics_text = metrics_response.get_data(as_text=True)

    assert 'http_request_duration_seconds_count{endpoint="/work"}' in metrics_text



def test_work_error(client, monkeypatch):
    monkeypatch.setattr(app_module.random, "random", lambda: 0.01)

    counter = app_module.REQUEST_COUNT.labels(
        method="GET", endpoint="/work", status="500"
    )
    before = counter._value.get()

    response = client.get("/work")

    assert response.status_code == 500
    assert counter._value.get() == before + 1


def test_metrics_format(client):
    response = client.get("/metrics")

    assert response.status_code == 200
    assert b"http_requests_total" in response.data
    assert b"http_request_duration_seconds" in response.data
    assert b"# HELP" in response.data
    assert b"# TYPE" in response.data
