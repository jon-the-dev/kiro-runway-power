# Terraform Modules Guide

Complete guide for configuring and deploying Terraform modules with Runway.

## Overview

Runway provides seamless Terraform integration with automatic version management, environment-specific variable files, and remote state configuration. No separate Terraform installation required - Runway manages versions automatically.

## Prerequisites

**None** - Runway manages Terraform versions automatically. You don't need to install Terraform separately.

## Configuration Files

Terraform modules use environment and region-specific variable files:

- `ENV-REGION.tfvars` (e.g., `dev-us-east-1.tfvars`) - Highest priority
- `ENV.tfvars` (e.g., `dev.tfvars`) - Environment-wide variables
- Standard Terraform files: `*.tf`, `variables.tf`, `outputs.tf`

## Basic Terraform Module Structure

```
myapp.tf/
├── main.tf
├── variables.tf
├── outputs.tf
├── dev.tfvars
├── dev-us-east-1.tfvars
├── prod.tfvars
└── prod-us-east-1.tfvars
```

## Runway Configuration for Terraform

### Simple Configuration

```yaml
# runway.yml
deployments:
  - modules:
      - path: myapp.tf
    regions:
      - us-east-1
    environments:
      dev: true
      prod: true
```

### Advanced Configuration with Options

```yaml
deployments:
  - modules:
      - path: myapp.tf
        options:
          terraform_version: "1.5.0"  # Specify Terraform version
          terraform_backend_config:
            bucket: my-tfstate-bucket
            dynamodb_table: my-lock-table
            region: us-east-1
            key: myapp/terraform.tfstate
          args:
            - '-parallelism=25'
        parameters:
          instance_type: t3.micro
          ami_id: ami-12345678
    regions:
      - us-east-1
      - us-west-2
```

## Terraform Version Management

Runway automatically manages Terraform versions per module.

### Specify Version

```yaml
modules:
  - path: myapp.tf
    options:
      terraform_version: "1.5.0"
```

### Install Specific Version

```bash
# Runway will download and cache the version automatically
poetry run runway deploy

# Or manually install
poetry run runway tfenv install 1.5.0
```

### Version Resolution

Runway checks for Terraform version in this order:

1. `terraform_version` in runway.yml module options
2. `.terraform-version` file in module directory
3. Latest compatible version

## Variable Files

### Environment-Specific Variables

Create `.tfvars` files for each environment:

**dev.tfvars:**

```hcl
environment = "dev"
instance_type = "t3.micro"
instance_count = 1
enable_monitoring = false
```

**prod.tfvars:**

```hcl
environment = "prod"
instance_type = "t3.large"
instance_count = 3
enable_monitoring = true
```

### Region-Specific Variables

Create region-specific overrides:

**dev-us-east-1.tfvars:**

```hcl
availability_zones = ["us-east-1a", "us-east-1b"]
```

**dev-us-west-2.tfvars:**

```hcl
availability_zones = ["us-west-2a", "us-west-2b"]
```

### Variable Precedence

Variables are loaded in this order (later overrides earlier):

1. `ENV.tfvars`
2. `ENV-REGION.tfvars`
3. `parameters` from runway.yml

## Remote State Configuration

### S3 Backend with DynamoDB Locking

```yaml
modules:
  - path: myapp.tf
    options:
      terraform_backend_config:
        bucket: my-terraform-state
        key: myapp/terraform.tfstate
        region: us-east-1
        dynamodb_table: terraform-locks
        encrypt: true
```

### Backend Configuration in Terraform

**main.tf:**

```hcl
terraform {
  backend "s3" {
    # Configuration provided by Runway via terraform_backend_config
  }
}
```

Runway will inject the backend configuration at runtime.

## Passing Parameters from Runway

### Via runway.yml Parameters

```yaml
deployments:
  - modules:
      - path: myapp.tf
        parameters:
          vpc_id: vpc-12345678
          subnet_ids: ["subnet-1", "subnet-2"]
          namespace: myapp-dev
    regions:
      - us-east-1
```

These parameters are passed as Terraform variables.

### Using Lookups

```yaml
deployments:
  - modules:
      - path: myapp.tf
        parameters:
          vpc_id: ${cfn vpc-stack.VpcId}
          db_password: ${ssm /myapp/${env DEPLOY_ENVIRONMENT}/db-password}
          namespace: ${var namespace}-${env DEPLOY_ENVIRONMENT}
```

## Terraform Arguments

Pass additional Terraform CLI arguments:

```yaml
modules:
  - path: myapp.tf
    options:
      args:
        - '-parallelism=25'
        - '-lock-timeout=10m'
```

These are passed to `terraform apply` and `terraform plan`.

## Module Dependencies

Terraform modules can depend on outputs from other modules:

```yaml
deployments:
  - modules:
      - path: networking.tf
      - path: database.tf
        parameters:
          vpc_id: ${output networking.vpc_id}
          subnet_ids: ${output networking.private_subnet_ids}
      - path: application.tf
        parameters:
          vpc_id: ${output networking.vpc_id}
          db_endpoint: ${output database.endpoint}
```

Runway deploys modules in order, making outputs available to subsequent modules.

## Workspace Management

Runway doesn't use Terraform workspaces. Instead, use:

- Separate `.tfvars` files per environment
- Environment-specific state files via backend configuration
- Git branches for environment isolation

## Common Patterns

### Pattern 1: Multi-Region Deployment

```yaml
deployments:
  - modules:
      - path: myapp.tf
    regions:
      - us-east-1
      - us-west-2
      - eu-west-1
```

Runway deploys to each region sequentially, using region-specific `.tfvars` files.

### Pattern 2: Environment-Specific Module Options

```yaml
deployments:
  - modules:
      - path: myapp.tf
        options:
          terraform_version: "1.5.0"
        parameters:
          instance_type: ${var instance_types.${env DEPLOY_ENVIRONMENT}}
    environments:
      dev: true
      prod: true

variables:
  instance_types:
    dev: t3.micro
    prod: t3.large
```

### Pattern 3: Conditional Resource Deployment

Use Terraform's `count` or `for_each` with environment variables:

**variables.tf:**

```hcl
variable "environment" {
  type = string
}

variable "enable_monitoring" {
  type = bool
  default = false
}
```

**main.tf:**

```hcl
resource "aws_cloudwatch_dashboard" "main" {
  count = var.enable_monitoring ? 1 : 0
  # ...
}
```

**prod.tfvars:**

```hcl
environment = "prod"
enable_monitoring = true
```

## Troubleshooting

### Error: Backend initialization failed

**Cause**: S3 bucket or DynamoDB table doesn't exist

**Solution**:

1. Create S3 bucket for state:

   ```bash
   aws s3 mb s3://my-terraform-state --region us-east-1
   aws s3api put-bucket-versioning \
     --bucket my-terraform-state \
     --versioning-configuration Status=Enabled
   ```

2. Create DynamoDB table for locking:

   ```bash
   aws dynamodb create-table \
     --table-name terraform-locks \
     --attribute-definitions AttributeName=LockID,AttributeType=S \
     --key-schema AttributeName=LockID,KeyType=HASH \
     --billing-mode PAY_PER_REQUEST \
     --region us-east-1
   ```

### Error: Terraform version not found

**Cause**: Specified version doesn't exist or can't be downloaded

**Solution**:

1. Check available versions: <https://releases.hashicorp.com/terraform/>
2. Update `terraform_version` in runway.yml
3. Clear Runway cache: `rm -rf ~/.runway/`

### Error: Variable not defined

**Cause**: Variable used in Terraform but not provided

**Solution**:

1. Add variable to appropriate `.tfvars` file
2. Or add to `parameters` in runway.yml
3. Or define default value in `variables.tf`

### Error: State lock timeout

**Cause**: Another process holds the state lock

**Solution**:

```bash
# Check DynamoDB for lock
aws dynamodb scan --table-name terraform-locks

# Force unlock (use with caution)
cd myapp.tf
terraform force-unlock <LOCK_ID>
```

### Error: Module not found

**Cause**: Terraform module source not accessible

**Solution**:

1. Verify module source in `main.tf`
2. Ensure git credentials are configured for private repos
3. Run `terraform init` manually to test

## Best Practices

1. **Use remote state** - Always configure S3 backend with DynamoDB locking
2. **Lock Terraform version** - Specify `terraform_version` in runway.yml
3. **Separate state per environment** - Use different state keys or buckets
4. **Use `.tfvars` files** - Don't hardcode environment-specific values
5. **Enable state encryption** - Set `encrypt: true` in backend config
6. **Version control `.tfvars`** - Commit environment configs (except secrets)
7. **Use lookups for secrets** - Reference SSM parameters instead of hardcoding
8. **Plan before apply** - Always run `runway plan` before `runway deploy`
9. **Use outputs** - Export values needed by other modules
10. **Document variables** - Add descriptions to all variables in `variables.tf`

## Example: Complete Terraform Module

**Directory structure:**

```
networking.tf/
├── main.tf
├── variables.tf
├── outputs.tf
├── dev.tfvars
└── prod.tfvars
```

**main.tf:**

```hcl
terraform {
  backend "s3" {}
  required_version = ">= 1.5.0"
}

resource "aws_vpc" "main" {
  cidr_block = var.vpc_cidr
  
  tags = {
    Name        = "${var.namespace}-vpc"
    Environment = var.environment
  }
}
```

**variables.tf:**

```hcl
variable "namespace" {
  description = "Namespace for resource naming"
  type        = string
}

variable "environment" {
  description = "Deployment environment"
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
}
```

**outputs.tf:**

```hcl
output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}
```

**dev.tfvars:**

```hcl
environment = "dev"
vpc_cidr    = "10.0.0.0/16"
```

**runway.yml:**

```yaml
deployments:
  - modules:
      - path: networking.tf
        options:
          terraform_version: "1.5.0"
          terraform_backend_config:
            bucket: my-terraform-state
            key: networking/terraform.tfstate
            region: us-east-1
            dynamodb_table: terraform-locks
        parameters:
          namespace: ${var namespace}-${env DEPLOY_ENVIRONMENT}
    regions:
      - us-east-1

variables:
  namespace: myapp
```

This configuration provides a complete, production-ready Terraform module setup with Runway.
