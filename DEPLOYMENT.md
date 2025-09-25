# Starline Backend Deployment Guide

## Overview
The Starline backend has been streamlined with two Docker Compose configurations and a unified deployment script.

## Files Structure
- `docker-compose-dev.yml` - Development environment configuration
- `docker-compose-prod.yml` - Production environment configuration
- `deploy.sh` - Unified deployment script for both environments

## Quick Start

### Development Environment
```bash
# Deploy to development
./deploy.sh dev

# Deploy with rebuild
./deploy.sh dev --build

# Check status
./deploy.sh dev --status

# View logs
./deploy.sh dev --logs

# Stop services
./deploy.sh dev --stop
```

### Production Environment
```bash
# Deploy to production
./deploy.sh production

# Deploy with rebuild
./deploy.sh production --build

# Deploy with database backup
./deploy.sh prod --backup

# Deploy with monitoring stack
./deploy.sh prod --monitoring

# Skip confirmation prompt
./deploy.sh prod --force
```

## Service URLs

### Development
- API Documentation: http://localhost:8000/api/v1/docs
- API Health: http://localhost:8000/health
- pgAdmin: http://localhost:5050
- Redis Commander: http://localhost:8081

### Production
- API: http://localhost (nginx proxy)
- API Documentation: http://localhost/api/v1/docs
- Health Check: http://localhost/health
- Prometheus: http://localhost:9090 (if monitoring enabled)
- Grafana: http://localhost:3000 (if monitoring enabled)

**Note:** HTTPS is handled by AWS CloudFront. The nginx server runs on HTTP only and CloudFront provides SSL/TLS termination.

## Environment Configuration

### Required Environment Variables
Create a `.env` file with the following variables:

```env
# Application
SECRET_KEY=your-secret-key
API_HOST=0.0.0.0
API_PORT=8000

# Database
POSTGRES_USER=starline
POSTGRES_PASSWORD=your-secure-password
POSTGRES_DB=starline_db
POSTGRES_PORT=5435  # External port for local access

# Redis (Production)
REDIS_PASSWORD=your-redis-password  # Only for production

# AWS
AWS_ACCESS_KEY=your-access-key
AWS_SECRET_KEY=your-secret-key
AWS_S3_BUCKET=your-bucket-name
AWS_REGION=your-region
CLOUDFRONT_URL=https://your-cloudfront-url/

# Email
RESEND_API_KEY=your-resend-key
FROM_EMAIL=noreply@yourdomain.com
FRONTEND_URL=http://localhost:4200

# Default Admin
DEFAULT_ADMIN_EMAIL=admin@yourdomain.com
DEFAULT_ADMIN_USERNAME=admin
DEFAULT_ADMIN_PASSWORD=SecurePassword123!
DEFAULT_ADMIN_FULL_NAME=Administrator
```

## Architecture

### Development Environment
- **PostgreSQL 15**: Database with pgAdmin for management
- **Redis 7**: Caching and session storage with Redis Commander
- **FastAPI Backend**: Hot-reload enabled for development
- **Volume Mounts**: Live code updates without rebuilding

### Production Environment
- **PostgreSQL 15**: Production database with backup support
- **Redis 7**: With optional password protection
- **FastAPI Backend**: Multi-worker deployment
- **Nginx**: Reverse proxy (HTTP only, CloudFront handles HTTPS)
- **Optional Monitoring**: Prometheus and Grafana stack
- **Resource Limits**: CPU and memory constraints for stability
- **CloudFront**: AWS CloudFront CDN provides SSL/TLS termination and HTTPS

## Docker Compose Commands

If you prefer using Docker Compose directly:

```bash
# Development
docker compose -f docker-compose-dev.yml up -d --build
docker compose -f docker-compose-dev.yml logs -f
docker compose -f docker-compose-dev.yml down

# Production
docker compose -f docker-compose-prod.yml up -d --build
docker compose -f docker-compose-prod.yml logs -f
docker compose -f docker-compose-prod.yml down

# With monitoring (production)
docker compose -f docker-compose-prod.yml --profile monitoring up -d
```

## Troubleshooting

### Port Conflicts
If you encounter port conflicts, modify the ports in `.env`:
```env
POSTGRES_PORT=5433  # Change external PostgreSQL port
API_PORT=8001       # Change API port
REDIS_PORT=6380     # Change Redis port
```

### Database Connection Issues
1. Ensure volumes are clean: `docker compose -f docker-compose-dev.yml down -v`
2. Restart with fresh volumes: `./deploy.sh dev --build`

### SSL/HTTPS Configuration
- **Development**: Direct HTTP access on port 8000
- **Production**: HTTP via nginx on port 80, with HTTPS handled by AWS CloudFront
- No SSL certificates needed locally as CloudFront manages SSL/TLS termination

## Backup and Restore

### Database Backup
```bash
# Manual backup
docker compose -f docker-compose-prod.yml exec -T postgres \
  pg_dump -U $POSTGRES_USER $POSTGRES_DB > backup_$(date +%Y%m%d_%H%M%S).sql

# Automated backup during deployment
./deploy.sh prod --backup
```

### Database Restore
```bash
# Restore from backup
docker compose -f docker-compose-prod.yml exec -T postgres \
  psql -U $POSTGRES_USER $POSTGRES_DB < backup_file.sql
```

## Security Notes

1. **Never commit `.env` file** to version control
2. **Use strong passwords** for production
3. **Enable Redis password** in production
4. **Configure CloudFront security settings** properly (WAF, geo-restrictions, etc.)
5. **Configure firewall rules** for production servers (allow only CloudFront IPs)
6. **Regular backups** are essential
7. **CloudFront handles HTTPS** - ensure proper origin protocol policy is set

## Maintenance

### Update Dependencies
```bash
# Update Python packages
docker compose -f docker-compose-dev.yml exec backend pip install --upgrade -r requirements.txt

# Update Docker images
docker compose -f docker-compose-dev.yml pull
docker compose -f docker-compose-dev.yml up -d
```

### View Logs
```bash
# All services
docker compose -f docker-compose-dev.yml logs -f

# Specific service
docker compose -f docker-compose-dev.yml logs -f backend

# Last 100 lines
docker compose -f docker-compose-dev.yml logs --tail=100
```

### Clean Up
```bash
# Remove stopped containers
docker compose -f docker-compose-dev.yml rm

# Remove volumes (WARNING: deletes data)
docker compose -f docker-compose-dev.yml down -v

# Remove all unused Docker resources
docker system prune -a
```