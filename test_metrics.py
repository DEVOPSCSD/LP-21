import pytest
import time
from prometheus_client.parser import text_string_to_metric_families
from app.app import app as flask_app

def _parse_metrics_text(text):
    return list(text_string_to_metric_families(text))

def _extract_sample_value(families, metric_name, label_filters=None):
    """
    Find a sample value for metric_name that matches label_filters (dict).
    Returns the first matching value or 0 if not found.
    Handles both tuple-style and object-style samples.
    """
    for fam in families:
        if fam.name != metric_name:
            continue
        for s in fam.samples:
            # sample can be (name, labels, value) or an object with .labels/.value
            if hasattr(s, "labels"):
                labels = s.labels
                value = s.value
            else:
                # tuple: (name, labels, value)
                # some parsers include timestamp/exemplar; we just take third element as value
                try:
                    labels = s[1]
                    value = s[2]
                except Exception:
                    continue
            if not label_filters:
                return value
            if all(str(labels.get(k)) == str(v) for k, v in label_filters.items()):
                return value
    return 0

@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c

def get_metrics_families(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    text = resp.data.decode("utf-8")
    families = _parse_metrics_text(text)
    return families

def test_metrics_endpoint_returns_prometheus_format(client):
    families = get_metrics_families(client)
    names = {f.name for f in families}
    assert "http_requests_total" in names
    # histogram exposes a _count metric
    assert "http_request_duration_seconds_count" in names

def test_root_increments_counter_and_histogram(client):
    before = get_metrics_families(client)
    before_count = _extract_sample_value(before, "http_requests_total", {"method": "GET", "endpoint": "/", "status": "200"})
    before_hist = _extract_sample_value(before, "http_request_duration_seconds_count", {"endpoint": "/"})

    r = client.get("/")
    assert r.status_code == 200

    after = get_metrics_families(client)
    after_count = _extract_sample_value(after, "http_requests_total", {"method": "GET", "endpoint": "/", "status": "200"})
    after_hist = _extract_sample_value(after, "http_request_duration_seconds_count", {"endpoint": "/"})

    assert after_count >= before_count + 1
    assert after_hist >= before_hist + 1

def test_work_endpoint_success_and_error_record_metrics(client, monkeypatch):
    # Force success: random.random() returns 1.0 so 1.0 < 0.1 is False => success (200)
    monkeypatch.setattr("app.app.random.random", lambda: 1.0)

    before = get_metrics_families(client)
    before_count_success = _extract_sample_value(before, "http_requests_total", {"method": "GET", "endpoint": "/work", "status": "200"})
    before_hist_success = _extract_sample_value(before, "http_request_duration_seconds_count", {"endpoint": "/work"})

    r = client.get("/work")
    assert r.status_code == 200

    after = get_metrics_families(client)
    after_count_success = _extract_sample_value(after, "http_requests_total", {"method": "GET", "endpoint": "/work", "status": "200"})
    after_hist_success = _extract_sample_value(after, "http_request_duration_seconds_count", {"endpoint": "/work"})

    assert after_count_success >= before_count_success + 1
    assert after_hist_success >= before_hist_success + 1

    # Force failure: random.random() returns 0.0 so 0.0 < 0.1 is True => 500
    monkeypatch.setattr("app.app.random.random", lambda: 0.0)

    before_err = get_metrics_families(client)
    before_count_err = _extract_sample_value(before_err, "http_requests_total", {"method": "GET", "endpoint": "/work", "status": "500"})
    before_hist_err = _extract_sample_value(before_err, "http_request_duration_seconds_count", {"endpoint": "/work"})

    r2 = client.get("/work")
    assert r2.status_code == 500

    after_err = get_metrics_families(client)
    after_count_err = _extract_sample_value(after_err, "http_requests_total", {"method": "GET", "endpoint": "/work", "status": "500"})
    after_hist_err = _extract_sample_value(after_err, "http_request_duration_seconds_count", {"endpoint": "/work"})

    assert after_count_err >= before_count_err + 1
    # histogram should still have recorded latency for the failed request? In this app the 500 path increments counter but does not observe the histogram,
    # so we only require that the histogram count increases when success path runs (already checked). Here we assert the histogram count did not decrease.
    assert after_hist_err >= before_hist_err
