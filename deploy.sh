#!/bin/bash

# Starline Backend Deployment Script
# Usage: ./deploy.sh [dev|production] [options]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT=""
ACTION="deploy"
MONITORING=false
BACKUP=false
FORCE=false

# Function to print colored output
print_color() {
    color=$1
    message=$2
    echo -e "${color}${message}${NC}"
}

# Function to print usage
print_usage() {
    cat << EOF
Usage: $0 [environment] [options]

Environments:
    dev, development    Deploy to development environment
    prod, production    Deploy to production environment

Options:
    --build            Force rebuild of Docker images
    --restart          Restart services without rebuilding
    --stop             Stop all services
    --status           Show service status
    --logs             Follow service logs
    --backup           Backup database before deployment (production only)
    --monitoring       Enable monitoring stack (production only)
    --force            Skip confirmation prompts
    --help, -h         Show this help message

Examples:
    $0 dev                     Deploy to development environment
    $0 production --build      Deploy to production with image rebuild
    $0 prod --backup          Deploy to production with database backup
    $0 dev --logs             Deploy to dev and follow logs

EOF
}

# Function to check prerequisites
check_prerequisites() {
    print_color "$BLUE" "🔍 Checking prerequisites..."

    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_color "$RED" "❌ Docker is not installed. Please install Docker first."
        print_color "$YELLOW" "   Visit: https://docs.docker.com/get-docker/"
        exit 1
    fi

    # Check Docker Compose
    if ! docker compose version &> /dev/null; then
        print_color "$RED" "❌ Docker Compose is not installed."
        print_color "$YELLOW" "   Visit: https://docs.docker.com/compose/install/"
        exit 1
    fi

    # Set Docker Compose command
    DOCKER_COMPOSE="sudo docker compose"

    # Check .env file
    if [ ! -f .env ]; then
        print_color "$RED" "❌ .env file not found."
        print_color "$YELLOW" "   Please create .env file with required configuration."
        exit 1
    fi

    print_color "$GREEN" "✅ All prerequisites met"
}

# Function to create necessary directories
create_directories() {
    print_color "$BLUE" "📁 Creating necessary directories..."

    mkdir -p nginx
    mkdir -p logs
    mkdir -p uploads
    mkdir -p backups/postgres
    mkdir -p monitoring/grafana/dashboards
    mkdir -p monitoring/grafana/datasources
    mkdir -p static

    print_color "$GREEN" "✅ Directories created"
}

# Function to backup database
backup_database() {
    print_color "$BLUE" "💾 Backing up database..."

    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_FILE="backups/postgres/backup_${TIMESTAMP}.sql"

    # Check if postgres container is running
    if [ "$($DOCKER_COMPOSE -f docker-compose-prod.yml ps -q postgres)" ]; then
        $DOCKER_COMPOSE -f docker-compose-prod.yml exec -T postgres \
            pg_dump -U ${POSTGRES_USER:-starline} ${POSTGRES_DB:-starline_db} > $BACKUP_FILE

        if [ -f $BACKUP_FILE ]; then
            print_color "$GREEN" "✅ Database backed up to: $BACKUP_FILE"

            # Keep only last 10 backups
            ls -t backups/postgres/backup_*.sql 2>/dev/null | tail -n +11 | xargs -r rm
        else
            print_color "$YELLOW" "⚠️  Backup failed or database is empty"
        fi
    else
        print_color "$YELLOW" "⚠️  Database container not running, skipping backup"
    fi
}

# Function to deploy development environment
deploy_dev() {
    print_color "$BLUE" "🚀 Deploying DEVELOPMENT environment..."

    COMPOSE_FILE="docker-compose-dev.yml"

    if [ "$ACTION" == "stop" ]; then
        print_color "$YELLOW" "⏹️  Stopping development services..."
        $DOCKER_COMPOSE -f $COMPOSE_FILE down
        print_color "$GREEN" "✅ Development services stopped"
        return
    fi

    if [ "$ACTION" == "status" ]; then
        print_color "$BLUE" "📊 Development services status:"
        $DOCKER_COMPOSE -f $COMPOSE_FILE ps
        return
    fi

    if [ "$ACTION" == "logs" ]; then
        print_color "$BLUE" "📋 Following development logs..."
        $DOCKER_COMPOSE -f $COMPOSE_FILE logs -f
        return
    fi

    # Pull latest images
    print_color "$BLUE" "📥 Pulling latest images..."
    $DOCKER_COMPOSE -f $COMPOSE_FILE pull --quiet

    # Build or restart
    if [ "$ACTION" == "build" ]; then
        print_color "$BLUE" "🏗️  Building development services..."
        $DOCKER_COMPOSE -f $COMPOSE_FILE up -d --build
    fi

    if [ "$ACTION" == "restart" ]; then
        print_color "$BLUE" "🔄 Restarting development services..."
        $DOCKER_COMPOSE -f $COMPOSE_FILE restart
    else
        print_color "$BLUE" "▶️  Starting development services..."
        $DOCKER_COMPOSE -f $COMPOSE_FILE up -d
    fi

    # Wait for services
    print_color "$BLUE" "⏳ Waiting for services to be ready..."
    sleep 10

    # Check health
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        print_color "$GREEN" "✅ Backend is healthy!"
    else
        print_color "$YELLOW" "⚠️  Backend may still be starting up..."
    fi

    print_color "$GREEN" "\n🎉 Development environment deployed successfully!"
    print_color "$BLUE" "\n📍 Service URLs:"
    print_color "$NC" "   • API Documentation: http://localhost:8000/api/v1/docs"
    print_color "$NC" "   • API Health: http://localhost:8000/health"
    print_color "$NC" "   • pgAdmin: http://localhost:5050"
    print_color "$NC" "   • Redis Commander: http://localhost:8081"

    if [ "$ACTION" == "deploy" ] || [ "$ACTION" == "build" ]; then
        print_color "$BLUE" "\n🔧 Useful Commands:"
        print_color "$NC" "   • View logs: $DOCKER_COMPOSE -f $COMPOSE_FILE logs -f"
        print_color "$NC" "   • Stop services: ./deploy.sh dev --stop"
        print_color "$NC" "   • Service status: ./deploy.sh dev --status"
    fi
}

# Function to deploy production environment
deploy_prod() {
    print_color "$BLUE" "🚀 Deploying PRODUCTION environment..."

    COMPOSE_FILE="docker-compose-prod.yml"

    # Confirmation for production
    if [ "$FORCE" != true ] && [ "$ACTION" != "status" ] && [ "$ACTION" != "logs" ]; then
        print_color "$YELLOW" "⚠️  You are about to deploy to PRODUCTION!"
        read -p "Are you sure? (yes/no): " confirmation
        if [ "$confirmation" != "yes" ]; then
            print_color "$RED" "❌ Deployment cancelled"
            exit 1
        fi
    fi

    if [ "$ACTION" == "stop" ]; then
        print_color "$YELLOW" "⏹️  Stopping production services..."
        $DOCKER_COMPOSE -f $COMPOSE_FILE down
        print_color "$GREEN" "✅ Production services stopped"
        return
    fi

    if [ "$ACTION" == "status" ]; then
        print_color "$BLUE" "📊 Production services status:"
        $DOCKER_COMPOSE -f $COMPOSE_FILE ps
        return
    fi

    if [ "$ACTION" == "logs" ]; then
        print_color "$BLUE" "📋 Following production logs..."
        $DOCKER_COMPOSE -f $COMPOSE_FILE logs -f
        return
    fi

    # Backup if requested
    if [ "$BACKUP" == true ]; then
        backup_database
    fi

    # Set monitoring profile if enabled
    COMPOSE_PROFILES=""
    if [ "$MONITORING" == true ]; then
        COMPOSE_PROFILES="--profile monitoring"
        print_color "$BLUE" "📊 Monitoring stack will be enabled"
    fi

    # Pull latest images
    print_color "$BLUE" "📥 Pulling latest images..."
    $DOCKER_COMPOSE -f $COMPOSE_FILE pull --quiet

    # Build or restart
    if [ "$ACTION" == "build" ]; then
        print_color "$BLUE" "🏗️  Building production services..."
        $DOCKER_COMPOSE -f $COMPOSE_FILE up -d --build $COMPOSE_PROFILES
    fi

    if [ "$ACTION" == "restart" ]; then
        print_color "$BLUE" "🔄 Restarting production services..."
        $DOCKER_COMPOSE -f $COMPOSE_FILE $COMPOSE_PROFILES restart
    else
        print_color "$BLUE" "▶️  Starting production services..."
        $DOCKER_COMPOSE -f $COMPOSE_FILE $COMPOSE_PROFILES up -d
    fi

    # Wait for services
    print_color "$BLUE" "⏳ Waiting for services to be ready..."
    sleep 15

    # Check health
    if curl -f http://localhost/health > /dev/null 2>&1; then
        print_color "$GREEN" "✅ Backend is healthy!"
    else
        print_color "$YELLOW" "⚠️  Backend may still be starting up..."
    fi

    print_color "$GREEN" "\n🎉 Production environment deployed successfully!"
    print_color "$BLUE" "\n📍 Service URLs:"
    print_color "$NC" "   • API: http://localhost (via nginx)"
    print_color "$NC" "   • API Documentation: http://localhost/api/v1/docs"
    print_color "$NC" "   • Health Check: http://localhost/health"
    print_color "$YELLOW" "\n📌 Note: HTTPS will be handled by AWS CloudFront"

    if [ "$MONITORING" == true ]; then
        print_color "$NC" "   • Prometheus: http://localhost:9090"
        print_color "$NC" "   • Grafana: http://localhost:3000"
    fi

    if [ "$ACTION" == "deploy" ] || [ "$ACTION" == "build" ]; then
        print_color "$BLUE" "\n🔧 Useful Commands:"
        print_color "$NC" "   • View logs: $DOCKER_COMPOSE -f $COMPOSE_FILE logs -f"
        print_color "$NC" "   • Stop services: ./deploy.sh prod --stop"
        print_color "$NC" "   • Service status: ./deploy.sh prod --status"
        print_color "$NC" "   • Backup database: ./deploy.sh prod --backup"
    fi
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        dev|development)
            ENVIRONMENT="dev"
            shift
            ;;
        prod|production)
            ENVIRONMENT="prod"
            shift
            ;;
        --build)
            ACTION="build"
            shift
            ;;
        --restart)
            ACTION="restart"
            shift
            ;;
        --stop)
            ACTION="stop"
            shift
            ;;
        --status)
            ACTION="status"
            shift
            ;;
        --logs)
            ACTION="logs"
            shift
            ;;
        --backup)
            BACKUP=true
            shift
            ;;
        --monitoring)
            MONITORING=true
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        --help|-h)
            print_usage
            exit 0
            ;;
        *)
            print_color "$RED" "❌ Unknown option: $1"
            print_usage
            exit 1
            ;;
    esac
done

# Check if environment is specified
if [ -z "$ENVIRONMENT" ]; then
    print_color "$RED" "❌ No environment specified"
    print_usage
    exit 1
fi

# Main execution
print_color "$BLUE" "═══════════════════════════════════════════"
print_color "$BLUE" "   STARLINE BACKEND DEPLOYMENT SCRIPT"
print_color "$BLUE" "═══════════════════════════════════════════\n"

# Check prerequisites
check_prerequisites

# Create necessary directories
create_directories

# Deploy based on environment
if [ "$ENVIRONMENT" == "dev" ]; then
    deploy_dev
elif [ "$ENVIRONMENT" == "prod" ]; then
    deploy_prod
fi

print_color "$BLUE" "\n═══════════════════════════════════════════"