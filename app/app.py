from flask import Flask, request
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import random
import time

app = Flask(__name__)

# --- Metrics definitions ---
# Counter: a number that only goes up (total requests, total errors)
REQUEST_COUNT = Counter(
    'http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status']
)

# Histogram: tracks distribution of values (great for latency)
REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds', 'Request latency', ['endpoint']
)

# --- Routes ---
@app.route('/')
def home():
    start = time.time()
    time.sleep(random.uniform(0.01, 0.2))  # simulate some work
    REQUEST_LATENCY.labels(endpoint='/').observe(time.time() - start)
    REQUEST_COUNT.labels(method='GET', endpoint='/', status='200').inc()
    return "Welcome to the monitored app!"

@app.route('/work')
def work():
    start = time.time()
    # simulate occasional failure
    if random.random() < 0.1:
        REQUEST_COUNT.labels(method='GET', endpoint='/work', status='500').inc()
        return "Something went wrong", 500

    time.sleep(random.uniform(0.05, 0.5))
    REQUEST_LATENCY.labels(endpoint='/work').observe(time.time() - start)
    REQUEST_COUNT.labels(method='GET', endpoint='/work', status='200').inc()
    return "Work done!"

# --- Metrics endpoint for Prometheus to scrape ---
@app.route('/metrics')
def metrics():
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)