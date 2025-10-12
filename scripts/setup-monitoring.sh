#!/bin/bash
# FilantropiaSolar Monitoring Setup Script
# Sets up comprehensive monitoring with Prometheus, Grafana, and alerting

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Configuration
MONITORING_DIR="monitoring"
PROMETHEUS_VERSION="v2.45.0"
GRAFANA_VERSION="10.0.3"
ALERTMANAGER_VERSION="v0.25.0"

# Function to print colored output
print_color() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Function to create monitoring directory structure
create_monitoring_structure() {
    print_color $BLUE "Creating monitoring directory structure..."
    
    mkdir -p ${MONITORING_DIR}/{prometheus,grafana,alertmanager}/{config,data}
    mkdir -p ${MONITORING_DIR}/grafana/dashboards
    mkdir -p ${MONITORING_DIR}/grafana/provisioning/{dashboards,datasources,notifiers}
    
    print_color $GREEN "✅ Directory structure created"
}

# Function to create Prometheus configuration
create_prometheus_config() {
    print_color $BLUE "Creating Prometheus configuration..."
    
    cat > ${MONITORING_DIR}/prometheus/config/prometheus.yml <<EOF
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "alert_rules.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093

scrape_configs:
  # Prometheus itself
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  # FilantropiaSolar application metrics
  - job_name: 'filantropia-solar'
    static_configs:
      - targets: ['filantropia-solar:8000']
    metrics_path: '/metrics'
    scrape_interval: 10s
    
  # System metrics (node exporter)
  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']
    
  # Docker container metrics
  - job_name: 'cadvisor'
    static_configs:
      - targets: ['cadvisor:8080']

  # Python application specific metrics
  - job_name: 'python-app-metrics'
    static_configs:
      - targets: ['filantropia-solar:8000']
    metrics_path: '/app-metrics'
    scrape_interval: 30s

  # ML model performance metrics
  - job_name: 'ml-model-metrics'
    static_configs:
      - targets: ['filantropia-solar:8000']
    metrics_path: '/model-metrics'
    scrape_interval: 60s
EOF

    print_color $GREEN "✅ Prometheus configuration created"
}

# Function to create Prometheus alert rules
create_alert_rules() {
    print_color $BLUE "Creating Prometheus alert rules..."
    
    cat > ${MONITORING_DIR}/prometheus/config/alert_rules.yml <<EOF
groups:
  - name: filantropia_solar_alerts
    rules:
      # Application availability
      - alert: ApplicationDown
        expr: up{job="filantropia-solar"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "FilantropiaSolar application is down"
          description: "The FilantropiaSolar application has been down for more than 1 minute."

      # High error rate
      - alert: HighErrorRate
        expr: rate(http_requests_total{job="filantropia-solar",status=~"5.."}[5m]) > 0.1
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ \$value }} errors per second for the last 5 minutes."

      # High response time
      - alert: HighResponseTime
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{job="filantropia-solar"}[5m])) > 2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High response time detected"
          description: "95th percentile response time is {{ \$value }} seconds."

      # High memory usage
      - alert: HighMemoryUsage
        expr: (process_resident_memory_bytes{job="filantropia-solar"} / 1024 / 1024) > 1024
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage"
          description: "Application memory usage is {{ \$value }}MB."

      # ML Model prediction accuracy drop
      - alert: ModelAccuracyDrop
        expr: ml_model_accuracy{job="filantropia-solar"} < 0.8
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "ML model accuracy dropped"
          description: "Model accuracy is {{ \$value }}, below threshold of 0.8."

      # Data quality issues
      - alert: DataQualityIssue
        expr: data_quality_score{job="filantropia-solar"} < 0.9
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Data quality issue detected"
          description: "Data quality score is {{ \$value }}, below threshold of 0.9."

      # Weather API failure
      - alert: WeatherAPIFailure
        expr: weather_api_requests_failed_total{job="filantropia-solar"} > 10
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Weather API failures"
          description: "Weather API has failed {{ \$value }} times in the last period."

  - name: system_alerts
    rules:
      # High CPU usage
      - alert: HighCPUUsage
        expr: 100 - (avg by (instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High CPU usage"
          description: "CPU usage is {{ \$value }}% on {{ \$labels.instance }}."

      # High disk usage
      - alert: HighDiskUsage
        expr: (node_filesystem_size_bytes - node_filesystem_free_bytes) / node_filesystem_size_bytes * 100 > 85
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High disk usage"
          description: "Disk usage is {{ \$value }}% on {{ \$labels.instance }} ({{ \$labels.device }})."

      # Low disk space
      - alert: LowDiskSpace
        expr: node_filesystem_free_bytes / node_filesystem_size_bytes * 100 < 10
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Low disk space"
          description: "Disk space is {{ \$value }}% on {{ \$labels.instance }} ({{ \$labels.device }})."
EOF

    print_color $GREEN "✅ Alert rules created"
}

# Function to create Grafana configuration
create_grafana_config() {
    print_color $BLUE "Creating Grafana configuration..."
    
    # Grafana main configuration
    cat > ${MONITORING_DIR}/grafana/config/grafana.ini <<EOF
[analytics]
reporting_enabled = false

[security]
admin_password = admin

[users]
allow_sign_up = false

[dashboards]
default_home_dashboard_path = /var/lib/grafana/dashboards/filantropia-solar-dashboard.json

[log]
mode = console
level = info
EOF

    # Datasource provisioning
    cat > ${MONITORING_DIR}/grafana/provisioning/datasources/prometheus.yml <<EOF
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: true
EOF

    # Dashboard provisioning
    cat > ${MONITORING_DIR}/grafana/provisioning/dashboards/dashboard.yml <<EOF
apiVersion: 1

providers:
  - name: 'filantropia-solar'
    orgId: 1
    folder: ''
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /var/lib/grafana/dashboards
EOF

    print_color $GREEN "✅ Grafana configuration created"
}

# Function to create Grafana dashboards
create_grafana_dashboards() {
    print_color $BLUE "Creating Grafana dashboards..."
    
    # Main application dashboard
    cat > ${MONITORING_DIR}/grafana/dashboards/filantropia-solar-dashboard.json <<'EOF'
{
  "dashboard": {
    "id": null,
    "title": "FilantropiaSolar Monitoring",
    "description": "Comprehensive monitoring dashboard for FilantropiaSolar application",
    "tags": ["filantropia-solar", "monitoring"],
    "timezone": "browser",
    "panels": [
      {
        "id": 1,
        "title": "Application Status",
        "type": "stat",
        "targets": [
          {
            "expr": "up{job=\"filantropia-solar\"}",
            "refId": "A"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "color": {
              "mode": "thresholds"
            },
            "mappings": [
              {
                "options": {
                  "0": {
                    "color": "red",
                    "text": "DOWN"
                  },
                  "1": {
                    "color": "green",
                    "text": "UP"
                  }
                },
                "type": "value"
              }
            ],
            "thresholds": {
              "steps": [
                {
                  "color": "red",
                  "value": null
                },
                {
                  "color": "green",
                  "value": 1
                }
              ]
            }
          }
        },
        "gridPos": {
          "h": 8,
          "w": 12,
          "x": 0,
          "y": 0
        }
      },
      {
        "id": 2,
        "title": "Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(http_requests_total{job=\"filantropia-solar\"}[5m])",
            "refId": "A",
            "legendFormat": "Requests/sec"
          }
        ],
        "gridPos": {
          "h": 8,
          "w": 12,
          "x": 12,
          "y": 0
        }
      },
      {
        "id": 3,
        "title": "Response Time",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.50, rate(http_request_duration_seconds_bucket{job=\"filantropia-solar\"}[5m]))",
            "refId": "A",
            "legendFormat": "50th percentile"
          },
          {
            "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{job=\"filantropia-solar\"}[5m]))",
            "refId": "B",
            "legendFormat": "95th percentile"
          }
        ],
        "gridPos": {
          "h": 8,
          "w": 12,
          "x": 0,
          "y": 8
        }
      },
      {
        "id": 4,
        "title": "Memory Usage",
        "type": "graph",
        "targets": [
          {
            "expr": "process_resident_memory_bytes{job=\"filantropia-solar\"} / 1024 / 1024",
            "refId": "A",
            "legendFormat": "Memory Usage (MB)"
          }
        ],
        "gridPos": {
          "h": 8,
          "w": 12,
          "x": 12,
          "y": 8
        }
      },
      {
        "id": 5,
        "title": "ML Model Accuracy",
        "type": "graph",
        "targets": [
          {
            "expr": "ml_model_accuracy{job=\"filantropia-solar\"}",
            "refId": "A",
            "legendFormat": "Model Accuracy"
          }
        ],
        "gridPos": {
          "h": 8,
          "w": 24,
          "x": 0,
          "y": 16
        },
        "yAxes": [
          {
            "min": 0,
            "max": 1
          }
        ]
      }
    ],
    "time": {
      "from": "now-1h",
      "to": "now"
    },
    "refresh": "30s"
  }
}
EOF

    print_color $GREEN "✅ Grafana dashboards created"
}

# Function to create Alertmanager configuration
create_alertmanager_config() {
    print_color $BLUE "Creating Alertmanager configuration..."
    
    cat > ${MONITORING_DIR}/alertmanager/config/alertmanager.yml <<EOF
global:
  smtp_smarthost: 'localhost:587'
  smtp_from: 'alerts@filantropia-solar.com'

route:
  group_by: ['alertname']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 1h
  receiver: 'web.hook'

receivers:
  - name: 'web.hook'
    webhook_configs:
      - url: 'http://localhost:5001/'
        send_resolved: true
  
  - name: 'slack-notifications'
    slack_configs:
      - api_url: '\${SLACK_WEBHOOK_URL}'
        channel: '#alerts'
        title: 'FilantropiaSolar Alert'
        text: '{{ range .Alerts }}{{ .Annotations.summary }}: {{ .Annotations.description }}{{ end }}'
        send_resolved: true

  - name: 'email-notifications'
    email_configs:
      - to: 'admin@filantropia-solar.com'
        subject: 'FilantropiaSolar Alert: {{ .GroupLabels.alertname }}'
        body: |
          {{ range .Alerts }}
          Alert: {{ .Annotations.summary }}
          Description: {{ .Annotations.description }}
          Severity: {{ .Labels.severity }}
          {{ end }}

inhibit_rules:
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['alertname', 'dev', 'instance']
EOF

    print_color $GREEN "✅ Alertmanager configuration created"
}

# Function to create Docker Compose for monitoring stack
create_monitoring_compose() {
    print_color $BLUE "Creating monitoring Docker Compose file..."
    
    cat > ${MONITORING_DIR}/docker-compose.monitoring.yml <<EOF
version: '3.8'

networks:
  monitoring:
    driver: bridge

volumes:
  prometheus_data:
  grafana_data:
  alertmanager_data:

services:
  prometheus:
    image: prom/prometheus:${PROMETHEUS_VERSION}
    container_name: prometheus
    restart: unless-stopped
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus/config:/etc/prometheus
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
      - '--storage.tsdb.retention.time=200h'
      - '--web.enable-lifecycle'
      - '--web.enable-admin-api'
    networks:
      - monitoring

  alertmanager:
    image: prom/alertmanager:${ALERTMANAGER_VERSION}
    container_name: alertmanager
    restart: unless-stopped
    ports:
      - "9093:9093"
    volumes:
      - ./alertmanager/config:/etc/alertmanager
      - alertmanager_data:/alertmanager
    command:
      - '--config.file=/etc/alertmanager/alertmanager.yml'
      - '--storage.path=/alertmanager'
      - '--web.external-url=http://localhost:9093'
    networks:
      - monitoring

  grafana:
    image: grafana/grafana:${GRAFANA_VERSION}
    container_name: grafana
    restart: unless-stopped
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning
      - ./grafana/dashboards:/var/lib/grafana/dashboards
      - ./grafana/config/grafana.ini:/etc/grafana/grafana.ini
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_USERS_ALLOW_SIGN_UP=false
    networks:
      - monitoring

  node-exporter:
    image: prom/node-exporter:latest
    container_name: node-exporter
    restart: unless-stopped
    ports:
      - "9100:9100"
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    command:
      - '--path.procfs=/host/proc'
      - '--path.rootfs=/rootfs'
      - '--path.sysfs=/host/sys'
      - '--collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)'
    networks:
      - monitoring

  cadvisor:
    image: gcr.io/cadvisor/cadvisor:latest
    container_name: cadvisor
    restart: unless-stopped
    ports:
      - "8080:8080"
    volumes:
      - /:/rootfs:ro
      - /var/run:/var/run:ro
      - /sys:/sys:ro
      - /var/lib/docker/:/var/lib/docker:ro
      - /dev/disk/:/dev/disk:ro
    privileged: true
    devices:
      - /dev/kmsg:/dev/kmsg
    networks:
      - monitoring
EOF

    print_color $GREEN "✅ Monitoring Docker Compose file created"
}

# Function to create monitoring startup script
create_startup_script() {
    print_color $BLUE "Creating monitoring startup script..."
    
    cat > ${MONITORING_DIR}/start-monitoring.sh <<'EOF'
#!/bin/bash
# Start FilantropiaSolar monitoring stack

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

print_color() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

print_color $BLUE "🚀 Starting FilantropiaSolar Monitoring Stack"
print_color $BLUE "==========================================="

# Start monitoring services
docker-compose -f docker-compose.monitoring.yml up -d

print_color $GREEN "✅ Monitoring stack started successfully!"
print_color $BLUE ""
print_color $BLUE "Access URLs:"
print_color $BLUE "  Prometheus: http://localhost:9090"
print_color $BLUE "  Grafana:    http://localhost:3000 (admin/admin)"
print_color $BLUE "  Alertmanager: http://localhost:9093"
print_color $BLUE ""
print_color $BLUE "Waiting for services to be ready..."

# Wait for services to be healthy
sleep 10

# Check service health
services=("prometheus:9090" "grafana:3000" "alertmanager:9093")
for service in "${services[@]}"; do
    name=$(echo $service | cut -d':' -f1)
    port=$(echo $service | cut -d':' -f2)
    
    if curl -f -s http://localhost:$port > /dev/null 2>&1; then
        print_color $GREEN "✅ $name is healthy"
    else
        print_color $YELLOW "⚠️  $name is not ready yet (this is normal on first startup)"
    fi
done

print_color $GREEN "🎉 Monitoring setup complete!"
EOF

    chmod +x ${MONITORING_DIR}/start-monitoring.sh
    
    print_color $GREEN "✅ Startup script created"
}

# Function to create Python metrics instrumentation
create_metrics_instrumentation() {
    print_color $BLUE "Creating Python metrics instrumentation..."
    
    mkdir -p src/filantropia_solar/monitoring
    
    cat > src/filantropia_solar/monitoring/__init__.py <<EOF
"""Monitoring and metrics instrumentation for FilantropiaSolar."""

from .metrics import (
    setup_metrics,
    track_prediction_accuracy,
    track_data_quality,
    track_weather_api_calls,
    increment_request_counter,
    observe_request_duration,
)

__all__ = [
    'setup_metrics',
    'track_prediction_accuracy',
    'track_data_quality',
    'track_weather_api_calls',
    'increment_request_counter',
    'observe_request_duration',
]
EOF

    cat > src/filantropia_solar/monitoring/metrics.py <<EOF
"""Prometheus metrics for FilantropiaSolar application."""

import time
from functools import wraps
from typing import Callable, Any

from prometheus_client import Counter, Histogram, Gauge, start_http_server, CollectorRegistry


# Create custom registry for our metrics
REGISTRY = CollectorRegistry()

# Request metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status'],
    registry=REGISTRY
)

REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    registry=REGISTRY
)

# Application-specific metrics
ML_MODEL_ACCURACY = Gauge(
    'ml_model_accuracy',
    'Current ML model accuracy',
    registry=REGISTRY
)

DATA_QUALITY_SCORE = Gauge(
    'data_quality_score',
    'Current data quality score',
    registry=REGISTRY
)

WEATHER_API_REQUESTS_TOTAL = Counter(
    'weather_api_requests_total',
    'Total weather API requests',
    ['status'],
    registry=REGISTRY
)

WEATHER_API_REQUESTS_FAILED = Counter(
    'weather_api_requests_failed_total',
    'Total failed weather API requests',
    registry=REGISTRY
)

SOLAR_PREDICTIONS_TOTAL = Counter(
    'solar_predictions_total',
    'Total solar energy predictions made',
    registry=REGISTRY
)

SOLAR_PREDICTION_ACCURACY = Histogram(
    'solar_prediction_accuracy',
    'Solar prediction accuracy distribution',
    registry=REGISTRY
)

# System metrics
MEMORY_USAGE_BYTES = Gauge(
    'process_memory_usage_bytes',
    'Process memory usage in bytes',
    registry=REGISTRY
)


def setup_metrics(port: int = 8001) -> None:
    """Start Prometheus metrics server."""
    start_http_server(port, registry=REGISTRY)


def increment_request_counter(method: str, endpoint: str, status: str) -> None:
    """Increment HTTP request counter."""
    REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()


def observe_request_duration(method: str, endpoint: str, duration: float) -> None:
    """Observe HTTP request duration."""
    REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(duration)


def track_prediction_accuracy(accuracy: float) -> None:
    """Track ML model prediction accuracy."""
    ML_MODEL_ACCURACY.set(accuracy)
    SOLAR_PREDICTION_ACCURACY.observe(accuracy)


def track_data_quality(score: float) -> None:
    """Track data quality score."""
    DATA_QUALITY_SCORE.set(score)


def track_weather_api_calls(success: bool) -> None:
    """Track weather API call success/failure."""
    status = 'success' if success else 'failure'
    WEATHER_API_REQUESTS_TOTAL.labels(status=status).inc()
    
    if not success:
        WEATHER_API_REQUESTS_FAILED.inc()


def track_solar_prediction() -> None:
    """Track solar prediction made."""
    SOLAR_PREDICTIONS_TOTAL.inc()


def monitor_endpoint(endpoint: str) -> Callable:
    """Decorator to monitor HTTP endpoint metrics."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                status = '200'  # Assume success
                return result
            except Exception as e:
                status = '500'  # Assume server error
                raise
            finally:
                duration = time.time() - start_time
                method = 'GET'  # Default, should be extracted from request
                
                increment_request_counter(method, endpoint, status)
                observe_request_duration(method, endpoint, duration)
        
        return wrapper
    return decorator


def update_memory_usage(memory_bytes: int) -> None:
    """Update process memory usage metric."""
    MEMORY_USAGE_BYTES.set(memory_bytes)
EOF

    print_color $GREEN "✅ Python metrics instrumentation created"
}

# Main function
main() {
    local command=${1:-"setup"}
    
    case $command in
        "setup")
            print_color $PURPLE "🔧 Setting up FilantropiaSolar Monitoring"
            print_color $PURPLE "========================================"
            
            create_monitoring_structure
            create_prometheus_config
            create_alert_rules
            create_grafana_config
            create_grafana_dashboards
            create_alertmanager_config
            create_monitoring_compose
            create_startup_script
            create_metrics_instrumentation
            
            print_color $GREEN "🎉 Monitoring setup complete!"
            print_color $BLUE ""
            print_color $BLUE "Next steps:"
            print_color $BLUE "  1. Start monitoring stack: cd ${MONITORING_DIR} && ./start-monitoring.sh"
            print_color $BLUE "  2. Add metrics to your application code"
            print_color $BLUE "  3. Configure Slack webhook in alertmanager.yml"
            print_color $BLUE "  4. Customize dashboards in Grafana"
            ;;
        
        "start")
            print_color $BLUE "Starting monitoring services..."
            cd ${MONITORING_DIR}
            ./start-monitoring.sh
            ;;
        
        "stop")
            print_color $BLUE "Stopping monitoring services..."
            cd ${MONITORING_DIR}
            docker-compose -f docker-compose.monitoring.yml down
            print_color $GREEN "✅ Monitoring services stopped"
            ;;
        
        "status")
            print_color $BLUE "Checking monitoring services status..."
            cd ${MONITORING_DIR}
            docker-compose -f docker-compose.monitoring.yml ps
            ;;
        
        *)
            echo "Usage: $0 [setup|start|stop|status]"
            echo ""
            echo "Commands:"
            echo "  setup   - Create monitoring configuration files"
            echo "  start   - Start monitoring services"
            echo "  stop    - Stop monitoring services"
            echo "  status  - Check monitoring services status"
            ;;
    esac
}

# Parse arguments and run
main "$@"