# Advanced Features Guide

Complete guide for advanced Runway features including parallel deployments, conditional deployment, lookups, and remote modules.

## Parallel Module Deployment

Deploy multiple independent modules simultaneously for faster deployments.

### Basic Parallel Deployment

```yaml
# runway.yml
deployments:
  - modules:
      - parallel:
          - app1.tf
          - app2.tf
          - app3.tf
    regions:
      - us-east-1
```

All modules in the `parallel` block deploy simultaneously.

### Mixed Sequential and Parallel

```yaml
deployments:
  - modules:
      - networking.tf  # Deploy first
      - parallel:      # Then deploy these in parallel
          - app1.tf
          - app2.tf
          - app3.tf
      - monitoring.tf  # Deploy last
    regions:
      - us-east-1
```

Execution order:

1. `networking.tf` (sequential)
2. `app1.tf`, `app2.tf`, `app3.tf` (parallel)
3. `monitoring.tf` (sequential)

### Parallel with Dependencies

```yaml
deployments:
  - modules:
      - vpc.tf
      - parallel:
          - path: app1.tf
            parameters:
              vpc_id: ${output vpc.vpc_id}
          - path: app2.tf
            parameters:
              vpc_id: ${output vpc.vpc_id}
```

Both apps deploy in parallel after VPC is ready.

## Conditional Deployment

Deploy modules only in specific environments or based on conditions.

### Environment-Specific Modules

```yaml
deployments:
  - modules:
      - path: core-infrastructure.tf
        environments:
          dev: true
          staging: true
          prod: true
      - path: expensive-resources.tf
        environments:
          prod: true  # Only deploy in prod
      - path: dev-tools.sls
        environments:
          dev: true  # Only deploy in dev
    regions:
      - us-east-1
```

### Account-Specific Deployment

```yaml
deployments:
  - modules:
      - path: myapp.tf
    environments:
      dev: true
      staging: 234567890123  # AWS Account ID
      prod: 345678901234     # AWS Account ID
```

Runway verifies the current AWS account matches before deploying.

### Using Tags for Selective Deployment

```yaml
deployments:
  - modules:
      - path: networking.tf
        tags:
          - layer:network
          - critical:true
      - path: app.tf
        tags:
          - layer:application
          - team:backend
      - path: frontend.web
        tags:
          - layer:frontend
          - team:frontend
```

Deploy specific modules:

```bash
# Deploy only network layer
runway deploy --tag layer:network

# Deploy only backend team modules
runway deploy --tag team:backend

# Deploy critical modules
runway deploy --tag critical:true
```

## Lookups

Dynamically resolve values from various sources.

### Environment Variable Lookup

```yaml
deployments:
  - modules:
      - path: myapp.tf
        parameters:
          api_key: ${env API_KEY}
          region: ${env AWS_REGION}
```

### Variable Lookup

```yaml
variables:
  namespace: myapp
  regions:
    dev:
      - us-east-1
    prod:
      - us-east-1
      - us-west-2
  instance_types:
    dev: t3.micro
    prod: t3.large

deployments:
  - modules:
      - path: myapp.tf
        parameters:
          namespace: ${var namespace}-${env DEPLOY_ENVIRONMENT}
          instance_type: ${var instance_types.${env DEPLOY_ENVIRONMENT}}
    regions: ${var regions.${env DEPLOY_ENVIRONMENT}}
```

### SSM Parameter Store Lookup

```yaml
deployments:
  - modules:
      - path: myapp.tf
        parameters:
          db_password: ${ssm /myapp/${env DEPLOY_ENVIRONMENT}/db-password}
          api_key: ${ssm /myapp/api-key~true}  # ~true for encrypted parameters
```

### CloudFormation Output Lookup (CFNgin)

```yaml
# For CFNgin modules
stacks:
  - name: vpc
    class_path: blueprints.vpc.VPC
    
  - name: app
    class_path: blueprints.app.Application
    variables:
      VpcId: ${output vpc.VpcId}
      SubnetIds: ${output vpc.PrivateSubnetIds}
```

### CloudFormation Stack Output Lookup

```yaml
deployments:
  - modules:
      - path: networking.cfn
      - path: application.tf
        parameters:
          vpc_id: ${cfn networking-stack.VpcId}
          subnet_ids: ${cfn networking-stack.PrivateSubnetIds}
```

### DynamoDB Lookup

```yaml
deployments:
  - modules:
      - path: myapp.tf
        parameters:
          config_value: ${dynamodb us-east-1@config-table:environment.${env DEPLOY_ENVIRONMENT}:value}
```

Format: `${dynamodb REGION@TABLE:PARTITION_KEY.SORT_KEY:ATTRIBUTE}`

### Combining Lookups

```yaml
deployments:
  - modules:
      - path: myapp.tf
        parameters:
          namespace: ${var namespace}-${env DEPLOY_ENVIRONMENT}
          vpc_id: ${cfn vpc-stack.VpcId}
          db_password: ${ssm /myapp/${env DEPLOY_ENVIRONMENT}/db-password}
          api_endpoint: ${output api-stack.Endpoint}
```

## Remote Modules

Use modules from git repositories for shared infrastructure.

### Basic Remote Module

```yaml
deployments:
  - modules:
      - path: git::https://github.com/org/repo.git//path/to/module
    regions:
      - us-east-1
```

### With Branch

```yaml
deployments:
  - modules:
      - path: git::https://github.com/org/repo.git//terraform/vpc?branch=main
```

### With Tag

```yaml
deployments:
  - modules:
      - path: git::https://github.com/org/repo.git//terraform/vpc?tag=v1.2.3
```

### With Commit

```yaml
deployments:
  - modules:
      - path: git::https://github.com/org/repo.git//terraform/vpc?commit=abc123
```

### Private Repository

```yaml
deployments:
  - modules:
      - path: git::git@github.com:org/private-repo.git//modules/vpc
```

Requires SSH key configured for git authentication.

### Remote Module with Parameters

```yaml
deployments:
  - modules:
      - path: git::https://github.com/org/infra-modules.git//vpc?branch=main
        parameters:
          vpc_cidr: 10.0.0.0/16
          environment: ${env DEPLOY_ENVIRONMENT}
```

## Assume IAM Role

Deploy to different AWS accounts using IAM role assumption.

### Basic Role Assumption

```yaml
deployments:
  - modules:
      - myapp.tf
    assume_role:
      arn: arn:aws:iam::123456789012:role/DeployRole
    regions:
      - us-east-1
```

### With Session Duration

```yaml
deployments:
  - modules:
      - myapp.tf
    assume_role:
      arn: arn:aws:iam::123456789012:role/DeployRole
      duration: 3600  # 1 hour
      session_name: runway-deploy-${env DEPLOY_ENVIRONMENT}
    regions:
      - us-east-1
```

### Environment-Specific Roles

```yaml
variables:
  deploy_roles:
    dev: arn:aws:iam::111111111111:role/DevDeployRole
    staging: arn:aws:iam::222222222222:role/StagingDeployRole
    prod: arn:aws:iam::333333333333:role/ProdDeployRole

deployments:
  - modules:
      - myapp.tf
    assume_role:
      arn: ${var deploy_roles.${env DEPLOY_ENVIRONMENT}}
      duration: 3600
    regions:
      - us-east-1
```

### With External ID

```yaml
deployments:
  - modules:
      - myapp.tf
    assume_role:
      arn: arn:aws:iam::123456789012:role/DeployRole
      external_id: unique-external-id
      duration: 3600
```

## Module Parameters

Pass parameters from Runway to modules.

### Static Parameters

```yaml
deployments:
  - modules:
      - path: myapp.tf
        parameters:
          instance_type: t3.micro
          ami_id: ami-12345678
          enable_monitoring: true
```

### Dynamic Parameters with Lookups

```yaml
deployments:
  - modules:
      - path: myapp.tf
        parameters:
          namespace: ${var namespace}-${env DEPLOY_ENVIRONMENT}
          vpc_id: ${cfn vpc-stack.VpcId}
          db_password: ${ssm /myapp/${env DEPLOY_ENVIRONMENT}/db-password}
          current_region: ${env AWS_REGION}
```

### Environment-Specific Parameters

```yaml
variables:
  instance_types:
    dev: t3.micro
    prod: t3.large
  instance_counts:
    dev: 1
    prod: 3

deployments:
  - modules:
      - path: myapp.tf
        parameters:
          instance_type: ${var instance_types.${env DEPLOY_ENVIRONMENT}}
          instance_count: ${var instance_counts.${env DEPLOY_ENVIRONMENT}}
```

## Multi-Region Deployment

Deploy the same infrastructure to multiple regions.

### Basic Multi-Region

```yaml
deployments:
  - modules:
      - myapp.tf
    regions:
      - us-east-1
      - us-west-2
      - eu-west-1
```

Runway deploys to each region sequentially.

### Region-Specific Configuration

For Terraform, use region-specific `.tfvars` files:

- `dev-us-east-1.tfvars`
- `dev-us-west-2.tfvars`
- `dev-eu-west-1.tfvars`

For Serverless, use region-specific config files:

- `env/dev-us-east-1.yml`
- `env/dev-us-west-2.yml`

### Environment-Specific Regions

```yaml
variables:
  regions:
    dev:
      - us-east-1
    staging:
      - us-east-1
      - us-west-2
    prod:
      - us-east-1
      - us-west-2
      - eu-west-1

deployments:
  - modules:
      - myapp.tf
    regions: ${var regions.${env DEPLOY_ENVIRONMENT}}
```

## Multiple Deployments

Organize modules into separate deployment groups.

```yaml
deployments:
  # Network infrastructure
  - name: networking
    modules:
      - networking.tf
    regions:
      - us-east-1
      - us-west-2
    environments:
      dev: true
      prod: true

  # Application infrastructure
  - name: applications
    modules:
      - app1.sls
      - app2.sls
      - app3.cdk
    regions:
      - us-east-1
      - us-west-2
    environments:
      dev: true
      prod: true

  # Monitoring (prod only)
  - name: monitoring
    modules:
      - monitoring.tf
    regions:
      - us-east-1
    environments:
      prod: true
```

Deploy specific deployment:

```bash
runway deploy --deploy-environment prod
# Deploys all deployments

# Or deploy specific modules with tags
runway deploy --tag layer:network
```

## Environment Variables

Set environment variables for all modules in a deployment.

```yaml
deployments:
  - modules:
      - myapp.tf
    env_vars:
      AWS_PROFILE: myprofile
      TF_LOG: DEBUG
      CUSTOM_VAR: custom-value
    regions:
      - us-east-1
```

Environment variables are available to all modules during deployment.

## Module Options

Configure module-specific behavior.

### Terraform Options

```yaml
modules:
  - path: myapp.tf
    options:
      terraform_version: "1.5.0"
      terraform_backend_config:
        bucket: my-tfstate-bucket
        dynamodb_table: my-lock-table
        region: us-east-1
      args:
        - '-parallelism=25'
        - '-lock-timeout=10m'
```

### Serverless Options

```yaml
modules:
  - path: myapp.sls
    options:
      skip_npm_ci: false
      args:
        - '--verbose'
        - '--config'
        - 'custom-sls.yml'
      extend_serverless_yml:
        custom:
          webpack:
            includeModules: true
```

### CDK Options

```yaml
modules:
  - path: myapp.cdk
    options:
      skip_npm_ci: false
      build_steps:
        - npx tsc
        - npm run build
      args:
        - '--require-approval'
        - 'never'
```

## Best Practices

### 1. Use Parallel Deployment for Independent Modules

```yaml
deployments:
  - modules:
      - networking.tf
      - parallel:
          - app1.sls
          - app2.sls
          - app3.cdk
```

Reduces total deployment time.

### 2. Use Tags for Selective Deployment

```yaml
modules:
  - path: critical-infra.tf
    tags:
      - critical:true
      - layer:infrastructure
```

Deploy only critical modules in emergencies:

```bash
runway deploy --tag critical:true
```

### 3. Use Lookups for Secrets

```yaml
parameters:
  db_password: ${ssm /myapp/${env DEPLOY_ENVIRONMENT}/db-password}
```

Never hardcode secrets in runway.yml.

### 4. Use Remote Modules for Shared Infrastructure

```yaml
modules:
  - path: git::https://github.com/org/infra-modules.git//vpc?tag=v1.0.0
```

Ensures consistent infrastructure across projects.

### 5. Use Assume Role for Cross-Account Deployment

```yaml
assume_role:
  arn: ${var deploy_roles.${env DEPLOY_ENVIRONMENT}}
```

Enables secure multi-account deployments.

### 6. Use Variables for Environment-Specific Configuration

```yaml
variables:
  instance_types:
    dev: t3.micro
    prod: t3.large

deployments:
  - modules:
      - path: myapp.tf
        parameters:
          instance_type: ${var instance_types.${env DEPLOY_ENVIRONMENT}}
```

Keeps configuration DRY and maintainable.

### 7. Use Conditional Deployment for Cost Optimization

```yaml
modules:
  - path: expensive-monitoring.tf
    environments:
      prod: true  # Only deploy in prod
```

Reduces costs in non-production environments.

## Example: Complete Advanced Configuration

```yaml
# runway.yml
variables:
  namespace: myapp
  regions:
    dev:
      - us-east-1
    prod:
      - us-east-1
      - us-west-2
  instance_types:
    dev: t3.micro
    prod: t3.large
  deploy_roles:
    dev: arn:aws:iam::111111111111:role/DevDeployRole
    prod: arn:aws:iam::333333333333:role/ProdDeployRole

deployments:
  # Core infrastructure
  - name: core
    modules:
      - path: networking.tf
        tags:
          - layer:network
          - critical:true
        parameters:
          namespace: ${var namespace}-${env DEPLOY_ENVIRONMENT}
          vpc_cidr: ${ssm /myapp/${env DEPLOY_ENVIRONMENT}/vpc-cidr}
      
      - parallel:
          - path: database.tf
            tags:
              - layer:data
              - critical:true
            parameters:
              vpc_id: ${output networking.vpc_id}
              db_password: ${ssm /myapp/${env DEPLOY_ENVIRONMENT}/db-password}
          
          - path: cache.tf
            tags:
              - layer:data
            parameters:
              vpc_id: ${output networking.vpc_id}
    
    assume_role:
      arn: ${var deploy_roles.${env DEPLOY_ENVIRONMENT}}
      duration: 3600
    
    regions: ${var regions.${env DEPLOY_ENVIRONMENT}}
    
    environments:
      dev: true
      prod: 333333333333

  # Applications
  - name: applications
    modules:
      - parallel:
          - path: api.sls
            tags:
              - layer:application
              - team:backend
            parameters:
              vpc_id: ${output networking.vpc_id}
              db_endpoint: ${output database.endpoint}
          
          - path: worker.sls
            tags:
              - layer:application
              - team:backend
            parameters:
              queue_url: ${output queue.url}
          
          - path: frontend.web
            tags:
              - layer:application
              - team:frontend
            parameters:
              api_url: ${output api.url}
    
    assume_role:
      arn: ${var deploy_roles.${env DEPLOY_ENVIRONMENT}}
      duration: 3600
    
    regions: ${var regions.${env DEPLOY_ENVIRONMENT}}
    
    environments:
      dev: true
      prod: 333333333333

  # Monitoring (prod only)
  - name: monitoring
    modules:
      - path: monitoring.tf
        tags:
          - layer:monitoring
        parameters:
          namespace: ${var namespace}-${env DEPLOY_ENVIRONMENT}
        environments:
          prod: true
    
    assume_role:
      arn: ${var deploy_roles.${env DEPLOY_ENVIRONMENT}}
      duration: 3600
    
    regions:
      - us-east-1
    
    environments:
      prod: 333333333333
```

This configuration demonstrates:

- Multiple deployments with different purposes
- Parallel module deployment
- Conditional deployment (monitoring only in prod)
- Lookups for dynamic values
- IAM role assumption for cross-account deployment
- Tags for selective deployment
- Environment-specific configuration via variables
- Module dependencies via outputs
