# Docker Compose Integration Hooks

This document describes the Docker Compose integration hooks for Runway deployments in the CMM Web project.

## Overview

The Docker Compose integration hooks provide seamless integration between Runway infrastructure deployments and Docker Compose local development environments. These hooks automatically start containers after infrastructure deployment and stop/cleanup containers during infrastructure destruction.

## Hook Files

- `docker_compose_integration.py` - Main hook implementation
- `test_docker_compose_integration.py` - Test suite for the hooks

## Configuration

The hooks are configured in the infrastructure `stacks.yml` file:

```yaml
# Docker Compose integration hooks for local environment
pre_deploy:
  - path: hooks.docker_compose_integration.start_containers_hook
    required: false
    enabled: ${docker_compose_enabled}
    args:
      compose_file: docker-compose.yml
      env_file: .env.local
      services: ["api-public", "api-internal", "registration-site", "internal-site", "sales-dashboard", "scanner-service", "worker-service", "report-service"]
      build: false
      wait_timeout: 300
      health_check: true
      working_directory: ../..

post_destroy:
  - path: hooks.docker_compose_integration.stop_containers_hook
    required: false
    enabled: ${docker_compose_enabled}
    args:
      compose_file: docker-compose.yml
      cleanup: true
      remove_volumes: false
      timeout: 30
      working_directory: ../..
```

## Environment Variables

The hooks are controlled by the `docker_compose_enabled` variable in environment files:

- `local.env`: `docker_compose_enabled: true` (enables hooks for local development)
- `dev.env`: `docker_compose_enabled: false` (disables hooks for dev environment)
- `prod.env`: `docker_compose_enabled: false` (disables hooks for prod environment)

## Hook Functions

### start_containers_hook

**Purpose**: Start Docker Compose containers after infrastructure deployment

**Parameters**:

- `compose_file`: Path to docker-compose.yml file (default: "docker-compose.yml")
- `services`: List of specific services to start (optional, defaults to all services)
- `env_file`: Environment file to check for existence (optional)
- `build`: Build images before starting (default: false)
- `wait_timeout`: Timeout for waiting for services to be healthy (default: 300 seconds)
- `health_check`: Whether to wait for health checks (default: true)
- `working_directory`: Directory to run commands from (default: current directory)

**Behavior**:

1. Validates Docker Compose availability
2. Checks for required files (docker-compose.yml, .env.local)
3. Optionally builds Docker images
4. Starts specified containers in detached mode
5. Waits for containers to be healthy (if health_check=true)
6. Returns success/failure status

### stop_containers_hook

**Purpose**: Stop and cleanup Docker Compose containers during infrastructure destruction

**Parameters**:

- `compose_file`: Path to docker-compose.yml file (default: "docker-compose.yml")
- `services`: List of specific services to stop (optional, defaults to all services)
- `cleanup`: Whether to remove containers after stopping (default: true)
- `remove_volumes`: Whether to remove volumes during cleanup (default: false)
- `timeout`: Timeout for stopping containers (default: 30 seconds)
- `working_directory`: Directory to run commands from (default: current directory)

**Behavior**:

1. Validates Docker Compose availability
2. Stops specified containers
3. Optionally removes containers and volumes
4. Returns success/failure status

## Usage Examples

### Command Line Usage

```bash
# Start all containers
python hooks/docker_compose_integration.py start

# Start specific services
python hooks/docker_compose_integration.py start --services api-public api-internal

# Start with build
python hooks/docker_compose_integration.py start --build --wait-timeout 600

# Stop all containers
python hooks/docker_compose_integration.py stop

# Stop with cleanup
python hooks/docker_compose_integration.py stop --cleanup --remove-volumes

# Get container status
python hooks/docker_compose_integration.py status
```

### Runway Integration

The hooks are automatically triggered during Runway operations:

```bash
# Deploy infrastructure (triggers start_containers_hook)
cd 0_infrastructure
DEPLOY_ENVIRONMENT=local runway deploy

# Destroy infrastructure (triggers stop_containers_hook)
cd 0_infrastructure
DEPLOY_ENVIRONMENT=local runway destroy
```

## Prerequisites

1. **Docker and Docker Compose**: Must be installed and available in PATH
2. **Environment File**: `.env.local` should exist with AWS resource configurations
3. **Docker Compose File**: `docker-compose.yml` must exist in the project root
4. **AWS Resources**: Infrastructure must be deployed before starting containers

## Error Handling

The hooks include comprehensive error handling:

- **Docker Unavailable**: Gracefully fails if Docker/Docker Compose is not installed
- **File Missing**: Warns if required files are missing but continues execution
- **Container Failures**: Provides detailed error messages for container startup/shutdown issues
- **Timeout Handling**: Respects timeout settings and provides clear timeout messages
- **Health Check Failures**: Warns if health checks fail but doesn't block deployment

## Testing

Run the test suite to validate hook functionality:

```bash
# Run unit tests
python3 hooks/test_docker_compose_integration.py

# Run unit tests + live tests (requires Docker)
python3 hooks/test_docker_compose_integration.py --live
```

## Troubleshooting

### Common Issues

1. **Docker Compose Not Found**
   - Ensure Docker and Docker Compose are installed
   - Check that `docker compose` or `docker-compose` commands work

2. **Environment File Missing**
   - Generate `.env.local` using `python local-dev/generate-env-local.py`
   - Ensure AWS infrastructure is deployed first

3. **Container Health Check Failures**
   - Check container logs: `docker-compose logs <service-name>`
   - Verify AWS connectivity from containers
   - Ensure AWS credentials are properly configured

4. **Permission Issues**
   - Ensure user has Docker permissions
   - Check file permissions on docker-compose.yml and .env.local

### Debug Commands

```bash
# Check Docker Compose status
docker-compose ps

# View container logs
docker-compose logs <service-name>

# Test hook manually
python hooks/docker_compose_integration.py status

# Validate environment file
cat .env.local
```

## Integration with Local Development Workflow

The hooks integrate seamlessly with the local development workflow:

1. **Deploy Infrastructure**: `runway deploy` in infrastructure directories
2. **Generate Environment**: `.env.local` is created from deployed resources
3. **Start Containers**: Hooks automatically start Docker containers
4. **Develop**: Make changes to code with hot reload support
5. **Destroy Infrastructure**: `runway destroy` stops containers and cleans up AWS resources

This provides a complete local development environment that uses real AWS services while maintaining the convenience of containerized development.
