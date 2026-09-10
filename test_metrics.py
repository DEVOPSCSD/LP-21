import pytest
from prometheus_client import REGISTRY
from app.app import app  # Adjust this import based on your project structure

@pytest.fixture
def client():
    """Setup a Flask test client for integration testing."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        # Clear metrics before each test to ensure isolated state if needed
        # (Note: Prometheus REGISTRY persists across tests by default)
        yield client

def test_metrics_endpoint_format(client):
    """Verify that the /metrics endpoint returns valid Prometheus text format."""
    response = client.get('/metrics')
    
    assert response.status_code == 200
    assert response.mimetype == 'text/plain'
    
    metrics_data = response.data.decode('utf-8')
    assert 'http_requests_total' in metrics_data
    assert 'http_request_duration_seconds' in metrics_data

def test_root_endpoint_metrics(client):
    """Verify metrics increment correctly for a successful request to '/'."""
    # Note: Adjust the label keys (e.g., 'endpoint', 'status') to match exactly 
    # what you defined in your app.py instrumentation.
    labels = {'endpoint': '/', 'status': '200'}
    
    # Get initial values (defaults to 0.0 if not yet recorded)
    initial_requests = REGISTRY.get_sample_value('http_requests_total', labels) or 0.0
    initial_duration_count = REGISTRY.get_sample_value('http_request_duration_seconds_count', labels) or 0.0

    # Trigger the endpoint
    response = client.get('/')
    assert response.status_code == 200

    # Verify the counter and histogram count incremented by 1
    new_requests = REGISTRY.get_sample_value('http_requests_total', labels)
    new_duration_count = REGISTRY.get_sample_value('http_request_duration_seconds_count', labels)
    
    assert new_requests == initial_requests + 1
    assert new_duration_count == initial_duration_count + 1

def test_work_endpoint_metrics_success_and_error(client):
    """Verify metrics track both 200 and 500 responses for the '/work' endpoint."""
    # Since /work returns 200 or 500 randomly, we capture the actual status code
    response = client.get('/work')
    actual_status = str(response.status_code)
    
    assert actual_status in ['200', '500']
    
    labels = {'endpoint': '/work', 'status': actual_status}
    
    # After the request, ensure the specific status code metric exists and is > 0
    requests = REGISTRY.get_sample_value('http_requests_total', labels)
    duration_count = REGISTRY.get_sample_value('http_request_duration_seconds_count', labels)
    
    assert requests is not None and requests > 0
    assert duration_count is not None and duration_count > 0

    # Optional: Verify it shows up in the /metrics output payload
    metrics_response = client.get('/metrics')
    metrics_data = metrics_response.data.decode('utf-8')
    assert f'status="{actual_status}"' in metrics_data
    assert 'endpoint="/work"' in metrics_data
