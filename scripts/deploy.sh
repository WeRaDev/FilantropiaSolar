#!/bin/bash
# FilantropiaSolar Deployment Script
# Supports multiple environments: dev, staging, production

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Configuration
DEFAULT_ENV="dev"
ENVIRONMENTS=("dev" "staging" "production")
DOCKER_IMAGE_NAME="filantropia-solar"
DOCKER_REGISTRY="ghcr.io/weradev"

# Function to print colored output
print_color() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Function to check requirements
check_requirements() {
    local missing_tools=()
    
    # Check for required tools
    command -v docker >/dev/null 2>&1 || missing_tools+=("docker")
    command -v git >/dev/null 2>&1 || missing_tools+=("git")
    
    if [ ${#missing_tools[@]} -ne 0 ]; then
        print_color $RED "Error: Missing required tools: ${missing_tools[*]}"
        print_color $YELLOW "Please install the missing tools and try again."
        exit 1
    fi
}

# Function to validate environment
validate_environment() {
    local env=$1
    
    if [[ ! " ${ENVIRONMENTS[@]} " =~ " ${env} " ]]; then
        print_color $RED "Error: Invalid environment '$env'"
        print_color $YELLOW "Valid environments: ${ENVIRONMENTS[*]}"
        exit 1
    fi
}

# Function to load environment configuration
load_env_config() {
    local env=$1
    
    # Set environment-specific variables
    case $env in
        "dev")
            NAMESPACE="filantropia-solar-dev"
            REPLICAS=1
            RESOURCE_LIMITS="cpu=500m,memory=512Mi"
            RESOURCE_REQUESTS="cpu=250m,memory=256Mi"
            ;;
        "staging")
            NAMESPACE="filantropia-solar-staging"
            REPLICAS=2
            RESOURCE_LIMITS="cpu=1000m,memory=1Gi"
            RESOURCE_REQUESTS="cpu=500m,memory=512Mi"
            ;;
        "production")
            NAMESPACE="filantropia-solar-prod"
            REPLICAS=3
            RESOURCE_LIMITS="cpu=2000m,memory=2Gi"
            RESOURCE_REQUESTS="cpu=1000m,memory=1Gi"
            ;;
    esac
    
    print_color $BLUE "Environment: $env"
    print_color $BLUE "Namespace: $NAMESPACE"
    print_color $BLUE "Replicas: $REPLICAS"
}

# Function to build Docker image
build_image() {
    local env=$1
    local version=$2
    local image_tag="${DOCKER_REGISTRY}/${DOCKER_IMAGE_NAME}:${version}-${env}"
    
    print_color $BLUE "Building Docker image: $image_tag"
    
    # Build multi-stage Docker image
    docker build \
        --build-arg ENVIRONMENT=$env \
        --build-arg VERSION=$version \
        --tag $image_tag \
        --tag "${DOCKER_REGISTRY}/${DOCKER_IMAGE_NAME}:latest-${env}" \
        .
    
    print_color $GREEN "✅ Image built successfully: $image_tag"
    echo $image_tag
}

# Function to run security scan
security_scan() {
    local image_tag=$1
    
    print_color $BLUE "Running security scan on image..."
    
    # Check if trivy is available
    if command -v trivy >/dev/null 2>&1; then
        trivy image --severity HIGH,CRITICAL --exit-code 1 $image_tag || {
            print_color $RED "❌ Security scan failed - high/critical vulnerabilities found"
            read -p "Continue deployment anyway? (y/N): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                exit 1
            fi
        }
        print_color $GREEN "✅ Security scan passed"
    else
        print_color $YELLOW "Warning: Trivy not found. Skipping security scan."
        print_color $YELLOW "Install trivy for security scanning: https://github.com/aquasecurity/trivy"
    fi
}

# Function to push image to registry
push_image() {
    local image_tag=$1
    local env=$2
    
    print_color $BLUE "Pushing image to registry..."
    
    # Login to registry if needed
    if [ -n "${GITHUB_TOKEN}" ]; then
        echo $GITHUB_TOKEN | docker login ghcr.io -u ${GITHUB_ACTOR} --password-stdin
    elif [ -n "${DOCKER_PASSWORD}" ]; then
        echo $DOCKER_PASSWORD | docker login -u ${DOCKER_USERNAME} --password-stdin
    else
        print_color $YELLOW "Warning: No registry credentials found. Attempting push without login."
    fi
    
    docker push $image_tag
    docker push "${DOCKER_REGISTRY}/${DOCKER_IMAGE_NAME}:latest-${env}"
    
    print_color $GREEN "✅ Image pushed successfully"
}

# Function to deploy to Kubernetes (if available)
deploy_kubernetes() {
    local env=$1
    local image_tag=$2
    
    if ! command -v kubectl >/dev/null 2>&1; then
        print_color $YELLOW "kubectl not found. Skipping Kubernetes deployment."
        return
    fi
    
    print_color $BLUE "Deploying to Kubernetes..."
    
    # Create deployment manifest
    cat > deployment-temp.yaml <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: filantropia-solar
  namespace: ${NAMESPACE}
  labels:
    app: filantropia-solar
    environment: ${env}
spec:
  replicas: ${REPLICAS}
  selector:
    matchLabels:
      app: filantropia-solar
  template:
    metadata:
      labels:
        app: filantropia-solar
        environment: ${env}
    spec:
      containers:
      - name: filantropia-solar
        image: ${image_tag}
        ports:
        - containerPort: 8000
        resources:
          limits:
            cpu: $(echo $RESOURCE_LIMITS | cut -d',' -f1 | cut -d'=' -f2)
            memory: $(echo $RESOURCE_LIMITS | cut -d',' -f2 | cut -d'=' -f2)
          requests:
            cpu: $(echo $RESOURCE_REQUESTS | cut -d',' -f1 | cut -d'=' -f2)
            memory: $(echo $RESOURCE_REQUESTS | cut -d',' -f2 | cut -d'=' -f2)
        env:
        - name: ENVIRONMENT
          value: "${env}"
        - name: LOG_LEVEL
          value: "INFO"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: filantropia-solar-service
  namespace: ${NAMESPACE}
  labels:
    app: filantropia-solar
spec:
  selector:
    app: filantropia-solar
  ports:
  - port: 80
    targetPort: 8000
    protocol: TCP
  type: ClusterIP
EOF

    # Create namespace if it doesn't exist
    kubectl create namespace ${NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -
    
    # Apply deployment
    kubectl apply -f deployment-temp.yaml
    
    # Wait for rollout
    kubectl rollout status deployment/filantropia-solar -n ${NAMESPACE} --timeout=300s
    
    # Clean up
    rm -f deployment-temp.yaml
    
    print_color $GREEN "✅ Kubernetes deployment successful"
}

# Function to deploy using Docker Compose
deploy_compose() {
    local env=$1
    local image_tag=$2
    
    print_color $BLUE "Deploying using Docker Compose..."
    
    # Create compose file for the environment
    cat > docker-compose.${env}.yaml <<EOF
version: '3.8'
services:
  filantropia-solar:
    image: ${image_tag}
    container_name: filantropia-solar-${env}
    restart: unless-stopped
    ports:
      - "808${env: -1}:8000"  # dev=8080, staging=8081, production=8082
    environment:
      - ENVIRONMENT=${env}
      - LOG_LEVEL=INFO
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    networks:
      - filantropia-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

networks:
  filantropia-network:
    driver: bridge
EOF

    # Deploy with compose
    docker-compose -f docker-compose.${env}.yaml up -d
    
    print_color $GREEN "✅ Docker Compose deployment successful"
    print_color $BLUE "Service available at: http://localhost:808${env: -1}"
}

# Function to run health checks
health_check() {
    local env=$1
    local max_attempts=30
    local attempt=1
    
    print_color $BLUE "Running health checks..."
    
    # Determine health check URL based on deployment method
    local health_url
    if command -v kubectl >/dev/null 2>&1; then
        # For Kubernetes, use port-forward
        kubectl port-forward service/filantropia-solar-service 8080:80 -n ${NAMESPACE} &
        local port_forward_pid=$!
        sleep 5
        health_url="http://localhost:8080/health"
    else
        # For Docker Compose
        health_url="http://localhost:808${env: -1}/health"
    fi
    
    while [ $attempt -le $max_attempts ]; do
        if curl -f -s $health_url >/dev/null 2>&1; then
            print_color $GREEN "✅ Health check passed"
            
            # Clean up port-forward if it was used
            if [ -n "${port_forward_pid}" ]; then
                kill $port_forward_pid 2>/dev/null || true
            fi
            
            return 0
        fi
        
        print_color $YELLOW "Health check attempt $attempt/$max_attempts failed. Retrying in 5 seconds..."
        sleep 5
        ((attempt++))
    done
    
    # Clean up port-forward if it was used
    if [ -n "${port_forward_pid}" ]; then
        kill $port_forward_pid 2>/dev/null || true
    fi
    
    print_color $RED "❌ Health check failed after $max_attempts attempts"
    return 1
}

# Function to send deployment notification
send_notification() {
    local env=$1
    local version=$2
    local status=$3
    
    if [ -n "${SLACK_WEBHOOK_URL}" ]; then
        local color
        local emoji
        if [ "$status" = "success" ]; then
            color="good"
            emoji="✅"
        else
            color="danger"
            emoji="❌"
        fi
        
        curl -X POST -H 'Content-type: application/json' \
            --data "{
                \"attachments\": [{
                    \"color\": \"${color}\",
                    \"text\": \"${emoji} FilantropiaSolar deployment ${status}\",
                    \"fields\": [
                        {\"title\": \"Environment\", \"value\": \"${env}\", \"short\": true},
                        {\"title\": \"Version\", \"value\": \"${version}\", \"short\": true},
                        {\"title\": \"Timestamp\", \"value\": \"$(date -u '+%Y-%m-%d %H:%M:%S UTC')\", \"short\": true}
                    ]
                }]
            }" \
            $SLACK_WEBHOOK_URL
    fi
}

# Function to rollback deployment
rollback() {
    local env=$1
    
    print_color $YELLOW "Rolling back deployment..."
    
    if command -v kubectl >/dev/null 2>&1; then
        # Kubernetes rollback
        kubectl rollout undo deployment/filantropia-solar -n ${NAMESPACE}
        kubectl rollout status deployment/filantropia-solar -n ${NAMESPACE}
    else
        # Docker Compose rollback
        print_color $YELLOW "For Docker Compose, manually revert to previous image or configuration."
    fi
    
    print_color $GREEN "✅ Rollback completed"
}

# Main deployment function
deploy() {
    local env=${1:-$DEFAULT_ENV}
    local version=${2:-$(git describe --tags --abbrev=0 2>/dev/null || echo "latest")}
    local skip_build=${3:-false}
    
    print_color $PURPLE "🚀 FilantropiaSolar Deployment"
    print_color $PURPLE "============================="
    
    # Validate inputs
    validate_environment $env
    load_env_config $env
    
    print_color $BLUE "Starting deployment..."
    print_color $BLUE "Version: $version"
    
    # Check requirements
    check_requirements
    
    local image_tag
    
    if [ "$skip_build" = false ]; then
        # Build image
        image_tag=$(build_image $env $version)
        
        # Security scan
        security_scan $image_tag
        
        # Push to registry
        if [ "$env" != "dev" ]; then
            push_image $image_tag $env
        fi
    else
        image_tag="${DOCKER_REGISTRY}/${DOCKER_IMAGE_NAME}:${version}-${env}"
        print_color $BLUE "Skipping build, using existing image: $image_tag"
    fi
    
    # Deploy
    if command -v kubectl >/dev/null 2>&1 && [ "$env" != "dev" ]; then
        deploy_kubernetes $env $image_tag
    else
        deploy_compose $env $image_tag
    fi
    
    # Health check
    if health_check $env; then
        print_color $GREEN "🎉 Deployment successful!"
        send_notification $env $version "success"
    else
        print_color $RED "💥 Deployment failed health checks!"
        send_notification $env $version "failed"
        
        read -p "Rollback deployment? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rollback $env
        fi
        exit 1
    fi
}

# Help function
show_help() {
    echo "FilantropiaSolar Deployment Script"
    echo ""
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  deploy [ENV] [VERSION]  Deploy to environment (default: dev)"
    echo "  rollback [ENV]          Rollback deployment in environment"
    echo "  status [ENV]            Check deployment status"
    echo ""
    echo "Environments: ${ENVIRONMENTS[*]}"
    echo ""
    echo "Options:"
    echo "  --skip-build           Skip Docker image build"
    echo "  --help                 Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 deploy dev                    # Deploy to dev environment"
    echo "  $0 deploy staging v1.2.3        # Deploy specific version to staging"
    echo "  $0 deploy production --skip-build # Deploy to prod without building"
    echo "  $0 rollback staging              # Rollback staging deployment"
    echo ""
    echo "Environment Variables:"
    echo "  GITHUB_TOKEN           GitHub token for registry authentication"
    echo "  SLACK_WEBHOOK_URL      Slack webhook for deployment notifications"
    echo ""
}

# Parse arguments
case ${1:-""} in
    deploy)
        shift
        skip_build=false
        if [ "$3" = "--skip-build" ] || [ "$2" = "--skip-build" ]; then
            skip_build=true
            if [ "$2" = "--skip-build" ]; then
                set -- "$1" "" "$2"
            fi
        fi
        deploy "$1" "$2" $skip_build
        ;;
    rollback)
        validate_environment ${2:-$DEFAULT_ENV}
        rollback ${2:-$DEFAULT_ENV}
        ;;
    status)
        env=${2:-$DEFAULT_ENV}
        validate_environment $env
        print_color $BLUE "Checking deployment status for $env..."
        if command -v kubectl >/dev/null 2>&1; then
            kubectl get deployments,services,pods -n filantropia-solar-${env}
        else
            docker-compose -f docker-compose.${env}.yaml ps
        fi
        ;;
    -h|--help|help)
        show_help
        ;;
    "")
        deploy
        ;;
    *)
        print_color $RED "Unknown command: $1"
        show_help
        exit 1
        ;;
esac