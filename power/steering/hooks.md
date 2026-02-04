# Runway Hooks Guide

Complete guide for using and creating custom Runway/CFNgin hooks to extend deployment workflows.

## Overview

Runway hooks allow you to execute custom Python code at specific points in the deployment lifecycle. Hooks can perform tasks like building Docker images, invalidating CloudFront caches, generating environment files, or integrating with external tools.

This guide covers both using the included example hooks and creating your own custom hooks.

## What are Hooks?

Hooks are Python functions that CFNgin (Runway's CloudFormation orchestration tool) calls at specific points during deployment:

- **pre_deploy**: Before deploying stacks
- **post_deploy**: After deploying stacks
- **pre_destroy**: Before destroying stacks
- **post_destroy**: After destroying stacks

Hooks receive the CFNgin context and can access stack outputs, environment variables, and AWS resources.

## Hook Configuration

Hooks are configured in your CFNgin `config.yml` file:

```yaml
# config.yml
namespace: ${namespace}

# Pre-deploy hooks (run before stacks are deployed)
pre_deploy:
  - path: hooks.module_name.function_name
    required: true  # Fail deployment if hook fails
    enabled: true   # Can be conditional: ${some_variable}
    args:
      param1: value1
      param2: value2

# Post-deploy hooks (run after stacks are deployed)
post_deploy:
  - path: hooks.another_hook.function_name
    required: false
    args:
      stack_output: ${output stack-name.OutputKey}

# Pre-destroy hooks (run before stacks are destroyed)
pre_destroy:
  - path: hooks.cleanup_hook.function_name
    required: false

# Post-destroy hooks (run after stacks are destroyed)
post_destroy:
  - path: hooks.final_cleanup.function_name
    required: false

stacks:
  - name: my-stack
    class_path: blueprints.my_stack.MyStack
```

## Included Example Hooks

### 1. CloudFront Invalidation Hook

Invalidate CloudFront distributions after deploying static sites or updating content.

**File**: `hooks/cloudfront_invalidation.py`

**Usage in CFNgin**:

```yaml
post_deploy:
  - path: hooks.cloudfront_invalidation.cfngin_hook
    required: false
    args:
      distribution_id: ${output cdn-stack.DistributionId}
      paths:
        - "/*"
        - "/index.html"
      wait: false  # Set true to wait for invalidation completion
      timeout: 900  # Timeout in seconds (default: 900)
```

**Command Line Usage**:

```bash
# Basic invalidation
python hooks/cloudfront_invalidation.py E1234567890ABC

# Specific paths
python hooks/cloudfront_invalidation.py E1234567890ABC --paths /index.html /assets/*

# Wait for completion
python hooks/cloudfront_invalidation.py E1234567890ABC --wait --timeout 600

# Verbose output
python hooks/cloudfront_invalidation.py E1234567890ABC --verbose
```

**Parameters**:

- `distribution_id` (required): CloudFront distribution ID
- `paths` (optional): List of paths to invalidate (default: `["/*"]`)
- `wait` (optional): Wait for invalidation to complete (default: `false`)
- `timeout` (optional): Timeout for waiting in seconds (default: `900`)

### 2. Docker Build and Push Hook

Build Docker images and push them to Amazon ECR repositories.

**File**: `hooks/docker_build_push.py`

**Usage in CFNgin**:

```yaml
pre_deploy:
  - path: hooks.docker_build_push.cfngin_hook
    required: true
    args:
      repository_name: my-app
      image_tag: ${environment}
      dockerfile_path: Dockerfile
      build_context: .
      region: us-east-1
      environment: ${environment}
      working_directory: ../app
```

**Command Line Usage**:

```bash
# Basic build and push
python hooks/docker_build_push.py my-app-repo

# With custom tag and Dockerfile
python hooks/docker_build_push.py my-app-repo \\
    --image-tag v1.0.0 \\
    --dockerfile-path docker/Dockerfile \\
    --build-context .

# Different region and working directory
python hooks/docker_build_push.py my-app-repo \\
    --region us-west-2 \\
    --environment prod \\
    --working-directory ../application
```

**Parameters**:

- `repository_name` (required): ECR repository name
- `image_tag` (optional): Image tag (default: `latest`)
- `dockerfile_path` (optional): Path to Dockerfile (default: `Dockerfile`)
- `build_context` (optional): Docker build context (default: `.`)
- `region` (optional): AWS region (default: `us-east-1`)
- `environment` (optional): Environment name (default: `dev`)
- `working_directory` (optional): Directory to run commands from

**Features**:

- Automatically creates ECR repository if it doesn't exist
- Enables image scanning on push
- Handles ECR authentication
- Builds for linux/amd64 platform (Lambda compatible)
- Tags images appropriately

### 3. Docker Compose Integration Hook

Start and stop Docker Compose containers as part of deployment workflow (useful for local development).

**File**: `hooks/docker_compose_integration.py`

**Usage in CFNgin**:

```yaml
# Start containers after infrastructure deployment
pre_deploy:
  - path: hooks.docker_compose_integration.start_containers_hook
    required: false
    enabled: ${docker_compose_enabled}  # Control via environment variable
    args:
      compose_file: docker-compose.yml
      env_file: .env.local
      services:
        - api-public
        - api-internal
        - worker-service
      build: false
      wait_timeout: 300
      health_check: true
      working_directory: ../..

# Stop containers during infrastructure destruction
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

**Command Line Usage**:

```bash
# Start all containers
python hooks/docker_compose_integration.py start

# Start specific services
python hooks/docker_compose_integration.py start \\
    --services api-public api-internal worker-service

# Start with build
python hooks/docker_compose_integration.py start \\
    --build --wait-timeout 600

# Stop all containers
python hooks/docker_compose_integration.py stop

# Stop with cleanup
python hooks/docker_compose_integration.py stop \\
    --cleanup --remove-volumes

# Get container status
python hooks/docker_compose_integration.py status
```

**Start Parameters**:

- `compose_file` (optional): Path to docker-compose.yml (default: `docker-compose.yml`)
- `services` (optional): List of specific services to start (default: all)
- `env_file` (optional): Environment file to check for existence
- `build` (optional): Build images before starting (default: `false`)
- `wait_timeout` (optional): Timeout for waiting for services (default: `300`)
- `health_check` (optional): Wait for health checks (default: `true`)
- `working_directory` (optional): Directory to run commands from

**Stop Parameters**:

- `compose_file` (optional): Path to docker-compose.yml (default: `docker-compose.yml`)
- `services` (optional): List of specific services to stop (default: all)
- `cleanup` (optional): Remove containers after stopping (default: `true`)
- `remove_volumes` (optional): Remove volumes during cleanup (default: `false`)
- `timeout` (optional): Timeout for stopping containers (default: `30`)
- `working_directory` (optional): Directory to run commands from

### 4. Environment File Generator Hook

Generate `.env` files from key-value pairs, including stack outputs and SSM parameters.

**File**: `hooks/env_file_generator.py`

**Usage in CFNgin**:

```yaml
pre_deploy:
  - path: hooks.env_file_generator.cfngin_hook
    required: true
    args:
      output_file: ./app/.env.local
      variables:
        NEXT_PUBLIC_API_URL: ${output api-stack.ApiUrl}
        NEXT_PUBLIC_USER_POOL_ID: ${output cognito-stack.UserPoolId}
        DATABASE_URL: ${ssm /app-${environment}/database-url}
        ENVIRONMENT: ${environment}
        AWS_REGION: us-east-1
      overwrite: true
      create_backup: true
      verbose: false
```

**Command Line Usage**:

```bash
# Basic usage
python hooks/env_file_generator.py --output-file .env.local \\
    --variables NEXT_PUBLIC_API_URL=https://api.example.com \\
               DATABASE_URL=postgres://localhost:5432/db

# With JSON variables
python hooks/env_file_generator.py --output-file .env.local \\
    --json-variables '{"API_URL": "https://api.example.com", "DEBUG": "true"}'

# Overwrite existing file with backup
python hooks/env_file_generator.py --output-file .env.local \\
    --variables NODE_ENV=production \\
    --overwrite --create-backup --verbose
```

**Parameters**:

- `output_file` (required): Path to output .env file
- `variables` (required): Dictionary of environment variables to write
- `overwrite` (optional): Overwrite existing files (default: `false`)
- `create_backup` (optional): Backup existing files (default: `true`)
- `verbose` (optional): Enable verbose logging (default: `false`)

**Features**:

- Supports CFNgin lookups (stack outputs, SSM parameters, environment variables)
- Creates backups of existing files with timestamps
- Handles multiline values and special characters
- Validates variable names
- Generates formatted .env files with comments

### 5. NPM Build Hook

Build Next.js or Node.js applications and sync to S3 buckets.

**File**: `hooks/npm_build.py`

**Usage in CFNgin**:

```yaml
post_deploy:
  - path: hooks.npm_build.build_and_sync_app
    required: true
    args:
      bucket_name: ${output static-site-stack.BucketName}
      app_path: ./app
      environment: ${environment}
```

**Command Line Usage**:

```bash
python hooks/npm_build.py \\
    --bucket-name my-static-site-bucket \\
    --app-path ./app \\
    --environment prod
```

**Parameters**:

- `bucket_name` (required): S3 bucket name for deployment
- `app_path` (optional): Path to app directory (default: `./app`)
- `environment` (optional): Environment name (default: `dev`)

**Features**:

- Copies environment-specific .env files (`.env.{environment}` → `.env.local`)
- Runs `npm install` if `node_modules` doesn't exist
- Executes `npm run build`
- Syncs build output to S3 with appropriate cache headers
- Sets correct content types for HTML and JSON files
- Supports Next.js static exports

### 6. SAM Deploy Hook

Deploy AWS SAM (Serverless Application Model) templates as part of Runway deployments.

**File**: `hooks/sam_deploy.py`

**Usage in CFNgin**:

```yaml
pre_deploy:
  - path: hooks.sam_deploy.cfngin_hook
    required: true
    args:
      template_file: template.yaml
      stack_name: my-sam-stack
      config_file: samconfig.toml
      env: ${environment}
      parameters:
        Environment: ${environment}
        BucketName: ${output storage-stack.BucketName}
      capabilities:
        - CAPABILITY_IAM
        - CAPABILITY_NAMED_IAM
      wait: true
      skip_build: false
      working_directory: ../sam-app

# Delete SAM stack during destroy
post_destroy:
  - path: hooks.sam_deploy.cfngin_delete_hook
    required: false
    args:
      stack_name: my-sam-stack
      wait: true
```

**Command Line Usage**:

```bash
# Deploy SAM application
python hooks/sam_deploy.py deploy \\
    --template template.yaml \\
    --stack-name my-sam-stack

# With config file and environment
python hooks/sam_deploy.py deploy \\
    --template template.yaml \\
    --stack-name my-sam-stack \\
    --config-file samconfig.toml \\
    --env dev

# With parameter overrides
python hooks/sam_deploy.py deploy \\
    --template template.yaml \\
    --stack-name my-sam-stack \\
    --parameters Environment=dev BucketName=my-bucket

# With parameter file
python hooks/sam_deploy.py deploy \\
    --template template.yaml \\
    --stack-name my-sam-stack \\
    --param-file parameters.json

# Skip build step (use existing artifacts)
python hooks/sam_deploy.py deploy \\
    --template template.yaml \\
    --stack-name my-sam-stack \\
    --skip-build

# Delete SAM stack
python hooks/sam_deploy.py delete --stack-name my-sam-stack

# Delete with resource retention
python hooks/sam_deploy.py delete \\
    --stack-name my-sam-stack \\
    --retain-resources MyS3Bucket MyDynamoTable
```

**Deploy Parameters**:

- `template_file` (required): Path to SAM template file
- `stack_name` (required): CloudFormation stack name
- `config_file` (optional): Path to SAM config file (samconfig.toml)
- `env` (optional): Environment name for config
- `parameters` (optional): Dictionary of parameter overrides
- `param_file` (optional): Path to JSON file with parameters
- `capabilities` (optional): IAM capabilities (default: `CAPABILITY_IAM`, `CAPABILITY_NAMED_IAM`)
- `region` (optional): AWS region (default: `us-east-1`)
- `wait` (optional): Wait for deployment completion (default: `true`)
- `timeout` (optional): Timeout in seconds (default: `1800`)
- `working_directory` (optional): Directory to run SAM command from
- `skip_build` (optional): Skip sam build step (default: `false`)

**Delete Parameters**:

- `stack_name` (required): CloudFormation stack name
- `region` (optional): AWS region (default: `us-east-1`)
- `wait` (optional): Wait for deletion completion (default: `true`)
- `timeout` (optional): Timeout in seconds (default: `1800`)
- `retain_resources` (optional): List of logical resource IDs to retain

**Features**:

- Automatically handles failed stack states (prompts for deletion)
- Runs `sam build` before deployment (unless skipped)
- Supports parameter files and inline parameters
- Handles "no changes to deploy" gracefully
- Provides detailed error messages
- Supports both deployment and deletion operations

## Creating Custom Hooks

### Hook Function Signature

All CFNgin hooks must follow this signature:

```python
def my_hook_function(context, provider, **kwargs):
    """
    Custom CFNgin hook.
    
    Args:
        context: CFNgin context object containing:
            - context.logger: Logger instance
            - context.hook_data: Dictionary for sharing data between hooks
            - context.environment: Environment variables
        provider: CFNgin provider object containing:
            - provider.region: AWS region
            - provider.s3_conn: S3 connection
        **kwargs: Arguments from config.yml args section
        
    Returns:
        bool or dict: True/dict for success, False for failure
    """
    # Your hook logic here
    return True
```

### Basic Hook Example

```python
#!/usr/bin/env python3
"""
Custom hook example.
"""

import logging

logger = logging.getLogger(__name__)


def my_custom_hook(context, provider, **kwargs):
    """
    Example custom hook.
    
    Args:
        context: CFNgin context
        provider: CFNgin provider
        **kwargs: Hook arguments
    """
    try:
        # Get parameters from kwargs
        param1 = kwargs.get('param1')
        param2 = kwargs.get('param2', 'default_value')
        
        # Log execution
        logger.info(f"Running custom hook with param1={param1}")
        
        # Access stack outputs (if available)
        # stack_output = context.get_stack_output('stack-name', 'OutputKey')
        
        # Perform your custom logic
        result = perform_custom_operation(param1, param2)
        
        # Store result in context for other hooks
        if not hasattr(context, 'hook_data'):
            context.hook_data = {}
        context.hook_data['my_custom_hook'] = result
        
        logger.info("Custom hook completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Custom hook failed: {e}")
        return False


def perform_custom_operation(param1, param2):
    """Your custom logic here."""
    return {'status': 'success'}
```

### Advanced Hook Example with CLI

```python
#!/usr/bin/env python3
"""
Advanced custom hook with CLI support.
"""

import argparse
import logging
import sys
from typing import Any, Dict

logger = logging.getLogger(__name__)


class CustomHookError(Exception):
    """Custom exception for hook errors."""
    pass


class CustomHook:
    """Custom hook implementation."""
    
    def __init__(self, context=None, provider=None):
        """Initialize the hook."""
        self.context = context
        self.provider = provider
        self.logger = context.logger if context else logger
    
    def execute(self, param1: str, param2: str = 'default') -> Dict[str, Any]:
        """
        Execute the custom hook logic.
        
        Args:
            param1: Required parameter
            param2: Optional parameter
            
        Returns:
            Dictionary with execution results
        """
        try:
            self.logger.info(f"Executing custom hook: param1={param1}, param2={param2}")
            
            # Your custom logic here
            result = self._perform_operation(param1, param2)
            
            self.logger.info("Custom hook execution completed")
            return {
                'success': True,
                'result': result
            }
            
        except Exception as e:
            self.logger.error(f"Custom hook execution failed: {e}")
            raise CustomHookError(f"Execution failed: {e}")
    
    def _perform_operation(self, param1: str, param2: str) -> Any:
        """Perform the actual operation."""
        # Implement your logic here
        return f"Processed {param1} with {param2}"


def cfngin_hook(context, provider, **kwargs) -> bool:
    """
    CFNgin hook entry point.
    
    Args:
        context: CFNgin context
        provider: CFNgin provider
        **kwargs: Hook arguments
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Extract parameters
        param1 = kwargs.get('param1')
        param2 = kwargs.get('param2', 'default')
        
        if not param1:
            raise CustomHookError("param1 is required")
        
        # Execute hook
        hook = CustomHook(context, provider)
        result = hook.execute(param1, param2)
        
        # Store result in context
        if context:
            if not hasattr(context, 'hook_data'):
                context.hook_data = {}
            context.hook_data['custom_hook'] = result
        
        return True
        
    except Exception as e:
        if context and context.logger:
            context.logger.error(f"Custom hook failed: {e}")
        else:
            logger.error(f"Custom hook failed: {e}")
        return False


def main():
    """Command line interface."""
    parser = argparse.ArgumentParser(description='Custom hook CLI')
    parser.add_argument('--param1', required=True, help='Required parameter')
    parser.add_argument('--param2', default='default', help='Optional parameter')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        hook = CustomHook()
        result = hook.execute(args.param1, args.param2)
        
        print(f"✅ Success: {result}")
        return 0
        
    except CustomHookError as e:
        logger.error(f"❌ Error: {e}")
        return 1
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
```

## Hook Best Practices

### 1. Error Handling

Always handle errors gracefully and provide meaningful error messages:

```python
def my_hook(context, provider, **kwargs):
    try:
        # Hook logic
        result = perform_operation()
        return True
    except SpecificError as e:
        context.logger.error(f"Specific error occurred: {e}")
        return False
    except Exception as e:
        context.logger.error(f"Unexpected error: {e}")
        return False
```

### 2. Parameter Validation

Validate required parameters early:

```python
def my_hook(context, provider, **kwargs):
    # Validate required parameters
    required_param = kwargs.get('required_param')
    if not required_param:
        context.logger.error("required_param is missing")
        return False
    
    # Validate parameter types
    if not isinstance(required_param, str):
        context.logger.error("required_param must be a string")
        return False
    
    # Continue with hook logic
    return True
```

### 3. Logging

Use appropriate log levels:

```python
def my_hook(context, provider, **kwargs):
    context.logger.debug("Debug information")
    context.logger.info("Informational message")
    context.logger.warning("Warning message")
    context.logger.error("Error message")
    return True
```

### 4. Sharing Data Between Hooks

Use `context.hook_data` to share data:

```python
# First hook stores data
def first_hook(context, provider, **kwargs):
    if not hasattr(context, 'hook_data'):
        context.hook_data = {}
    context.hook_data['my_data'] = {'key': 'value'}
    return True

# Second hook retrieves data
def second_hook(context, provider, **kwargs):
    my_data = context.hook_data.get('my_data', {})
    context.logger.info(f"Retrieved data: {my_data}")
    return True
```

### 5. Conditional Execution

Use environment variables or parameters to control hook execution:

```yaml
pre_deploy:
  - path: hooks.my_hook.cfngin_hook
    enabled: ${enable_my_hook}  # Control via environment variable
    args:
      param: value
```

### 6. Idempotency

Make hooks idempotent (safe to run multiple times):

```python
def my_hook(context, provider, **kwargs):
    # Check if operation already completed
    if resource_exists():
        context.logger.info("Resource already exists, skipping")
        return True
    
    # Perform operation
    create_resource()
    return True
```

### 7. Timeout Handling

Implement timeouts for long-running operations:

```python
import time

def my_hook(context, provider, **kwargs):
    timeout = kwargs.get('timeout', 300)
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        if operation_complete():
            return True
        time.sleep(10)
    
    context.logger.error(f"Operation timed out after {timeout} seconds")
    return False
```

### 8. CLI Support

Provide CLI support for testing hooks independently:

```python
def main():
    """Command line interface for testing."""
    parser = argparse.ArgumentParser(description='Hook CLI')
    parser.add_argument('--param', required=True)
    args = parser.parse_args()
    
    # Test hook logic
    result = perform_operation(args.param)
    print(f"Result: {result}")
    return 0 if result else 1

if __name__ == '__main__':
    sys.exit(main())
```

## Testing Hooks

### Unit Testing

```python
import unittest
from unittest.mock import Mock, patch

class TestMyHook(unittest.TestCase):
    def setUp(self):
        self.context = Mock()
        self.provider = Mock()
        self.context.logger = Mock()
    
    def test_hook_success(self):
        result = my_hook(
            self.context,
            self.provider,
            param1='value1'
        )
        self.assertTrue(result)
    
    def test_hook_missing_param(self):
        result = my_hook(
            self.context,
            self.provider
        )
        self.assertFalse(result)

if __name__ == '__main__':
    unittest.main()
```

### Integration Testing

Test hooks with actual AWS resources in a test environment:

```bash
# Set test environment
export DEPLOY_ENVIRONMENT=test

# Run Runway deployment with hooks
cd infrastructure
runway deploy --ci
```

## Troubleshooting

### Hook Not Found

**Error**: `ImportError: No module named 'hooks.my_hook'`

**Solution**:

1. Ensure hook file is in the `hooks/` directory
2. Verify `hooks/__init__.py` exists
3. Check the path in config.yml matches the file structure

### Hook Fails Silently

**Error**: Hook doesn't execute or fails without error messages

**Solution**:

1. Check `required: true` in config.yml to see errors
2. Add verbose logging to your hook
3. Run with `--debug` flag: `runway deploy --debug`

### Import Errors

**Error**: `ModuleNotFoundError: No module named 'boto3'`

**Solution**:

1. Install required dependencies: `pip install boto3`
2. Add dependencies to `requirements.txt`
3. Ensure virtual environment is activated

### Permission Errors

**Error**: `AccessDenied` or permission-related errors

**Solution**:

1. Verify AWS credentials are configured
2. Check IAM permissions for the operation
3. Ensure assume role configuration is correct

## Additional Resources

- CFNgin Documentation: <https://runway.readthedocs.io/page/cfngin/index.html>
- CFNgin Hooks Reference: <https://runway.readthedocs.io/page/cfngin/hooks.html>
- Example Hooks: `powers/runway/hooks/` directory
- Hook Tests: `powers/runway/hooks/test_*.py` files

## Summary

Runway hooks provide powerful extensibility for deployment workflows. The included example hooks cover common use cases like Docker builds, CloudFront invalidation, and SAM deployments. Use these as templates for creating your own custom hooks to integrate with any tool or service in your deployment pipeline.

Key takeaways:

- Hooks run at specific lifecycle points (pre/post deploy/destroy)
- All hooks receive context and provider objects
- Return `True` for success, `False` for failure
- Use `context.hook_data` to share data between hooks
- Provide CLI support for independent testing
- Handle errors gracefully with meaningful messages
- Make hooks idempotent and include timeout handling
