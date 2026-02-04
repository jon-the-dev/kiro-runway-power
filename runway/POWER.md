---
name: "runway"
displayName: "Runway"
description: "Lightweight infrastructure deployment tool that unifies AWS CDK, Serverless Framework, CloudFormation, Terraform, and static sites with GitOps best practices."
keywords: ["runway", "infrastructure", "deployment", "terraform", "cdk", "serverless", "cloudformation", "iac"]
author: "Jon Price"
---

# Runway

## Overview

Runway is a lightweight integration app designed to ease management of infrastructure tools. It encourages GitOps best-practices, avoids convoluted Makefiles/scripts, and enables developers/admins to use the best tool for any given job.

Runway provides a unified interface for deploying infrastructure across multiple tools, managing tool versions automatically, and supporting environment-specific configurations. Whether you're deploying Terraform modules, CDK stacks, Serverless functions, or static sites, Runway simplifies the process with a single configuration file.

This power includes access to AWS documentation through the MCP server to help you reference AWS services while working with Runway deployments.

## Available Steering Files

This power includes detailed guides for specific module types and advanced topics:

- **terraform-modules.md** - Complete guide for Terraform module configuration, variables, and backend setup
- **cloudformation-modules.md** - CFNgin configuration, stack dependencies, and CloudFormation best practices
- **serverless-modules.md** - Serverless Framework integration, stage mapping, and npm configuration
- **cdk-modules.md** - AWS CDK module setup, build steps, and feature flags
- **advanced-features.md** - Parallel deployments, conditional deployment, lookups, and remote modules
- **hooks.md** - Custom hooks guide with examples for CloudFront invalidation, Docker builds, SAM deployment, and more

Read specific steering files as needed using the readSteering action.

## Supported Deployment Tools

- **AWS CDK** - Cloud Development Kit
- **Serverless Framework** - Lambda functions and serverless applications
- **CFNgin (CloudFormation)** - CloudFormation stacks with Troposphere support
- **Terraform** - Infrastructure as code
- **Static Sites** - S3 + CloudFront deployments

## Onboarding

### Prerequisites

- **Python 3.8+** - Runway is a Python application
- **Git** - For GitOps workflows and environment detection
- **AWS CLI configured** - With appropriate credentials
- **Module-specific tools**:
  - npm (for CDK and Serverless modules)
  - Terraform (managed by Runway, but can be pre-installed)

### Installation

#### Recommended: Poetry (per-project)

```bash
poetry add --group deploy runway
# or
poetry add runway
```

#### Alternative: pip

```bash
pip install --user runway
# or
pip install runway
```

### Verification

```bash
# With poetry
poetry run runway --help

# With pip
runway --help

# Expected output: Runway command help and available commands
```

### Basic Configuration

Create a `runway.yml` file in your project root:

```yaml
# runway.yml
deployments:
  - modules:
      - path: module-name.tf
    regions:
      - us-east-1
    environments:
      dev: true
      prod: true
```

## Core Concepts

### 1. Runway Config File

- **Location**: Root of project repository
- **Name**: `runway.yml` or `runway.yaml`
- **Purpose**: Defines modules and deployment configuration

### 2. Deployments

A deployment contains:

- List of modules to deploy
- Options that apply to all modules in the deployment
- Regions to deploy to
- Environment-specific settings

### 3. Modules

A module is a directory containing infrastructure as code. Runway detects module type by file extension:

- **`.cdk`** - AWS CDK modules
- **`.cfn`** - CloudFormation/Troposphere modules
- **`.sls`** - Serverless Framework modules
- **`.tf`** - Terraform modules
- **`.web`** - Static site modules

### 4. Deploy Environment

Determined by (in order of precedence):

1. `DEPLOY_ENVIRONMENT` environment variable
2. Git branch name (e.g., `ENV-dev` → `dev`)
3. Parent directory name

The environment name is available as `DEPLOY_ENVIRONMENT` environment variable to all modules.

## Common Workflows

### Workflow 1: Initialize a New Runway Project

**Goal**: Set up a new infrastructure project with Runway

**Steps:**

```bash
# 1. Create project directory
mkdir my-infrastructure && cd my-infrastructure

# 2. Initialize git with environment branch
git init
git checkout -b ENV-dev

# 3. Install Runway
poetry init
poetry add --group deploy runway

# 4. Generate Runway config
poetry run runway new

# 5. Generate sample module (choose one)
poetry run runway gen-sample cfn        # CloudFormation
poetry run runway gen-sample sls-py     # Serverless Python
poetry run runway gen-sample cdk-py     # CDK Python
poetry run runway gen-sample terraform  # Terraform
```

**Result**: Project structure with runway.yml and sample module ready for customization.

### Workflow 2: Deploy Infrastructure

**Goal**: Deploy your infrastructure to AWS

**Steps:**

```bash
# 1. Preview changes (recommended)
poetry run runway plan

# 2. Deploy interactively
poetry run runway deploy

# 3. Or deploy non-interactively (CI/CD)
poetry run runway deploy --ci --deploy-environment dev

# 4. Deploy specific tagged modules only
poetry run runway deploy --tag app:myapp
```

**Common Options:**

- `--ci` - Non-interactive mode for CI/CD pipelines
- `--deploy-environment ENV` - Explicitly set environment
- `--tag KEY:VALUE` - Deploy only modules with specific tag

### Workflow 3: Manage Multiple Environments

**Goal**: Deploy the same infrastructure to dev, staging, and prod

**Configuration:**

```yaml
# runway.yml
variables:
  namespace: myapp
  regions:
    dev:
      - us-east-1
    staging:
      - us-east-1
    prod:
      - us-east-1
      - us-west-2

deployments:
  - modules:
      - myapp.tf
    parameters:
      namespace: ${var namespace}-${env DEPLOY_ENVIRONMENT}
    regions: ${var regions.${env DEPLOY_ENVIRONMENT}}
    environments:
      dev: true
      staging: 123456789012  # AWS Account ID
      prod: 987654321098     # AWS Account ID
```

**Deploy to specific environment:**

```bash
# Deploy to dev
git checkout ENV-dev
poetry run runway deploy

# Deploy to prod
git checkout ENV-prod
poetry run runway deploy --ci
```

### Workflow 4: Destroy Infrastructure

**Goal**: Tear down deployed infrastructure

**Steps:**

```bash
# 1. Destroy interactively (with confirmation)
poetry run runway destroy

# 2. Destroy non-interactively (CI/CD)
poetry run runway destroy --ci --deploy-environment dev

# 3. Check current environment first
poetry run runway whichenv
```

**Warning**: Always verify the environment before destroying to avoid accidentally removing production resources.

### Workflow 5: Using Lookups for Dynamic Values

**Goal**: Reference values from SSM, CloudFormation outputs, or environment variables

**Configuration:**

```yaml
deployments:
  - modules:
      - myapp.tf
    parameters:
      vpc_id: ${cfn vpc-stack.VpcId}
      db_password: ${ssm /myapp/${env DEPLOY_ENVIRONMENT}/db-password}
      namespace: ${var namespace}-${env DEPLOY_ENVIRONMENT}
      api_key: ${env API_KEY}
```

**Available Lookups:**

- `${env VAR_NAME}` - Environment variable
- `${var variable.path}` - Variable from runway.yml
- `${output stack.OutputName}` - CloudFormation stack output (CFNgin)
- `${ssm /path/to/parameter}` - AWS SSM Parameter Store
- `${cfn stack-name.OutputName}` - CloudFormation stack output

## Essential Commands

### Project Management

```bash
runway new              # Initialize new Runway project
runway init             # Initialize modules (npm install, terraform init)
runway whichenv         # Show current deploy environment
runway envvars          # Show environment variables
```

### Deployment Commands

```bash
runway plan             # Preview changes (dry-run)
runway deploy           # Deploy infrastructure
runway destroy          # Destroy infrastructure
```

### Module Generation

```bash
runway gen-sample cfn       # CloudFormation sample
runway gen-sample sls-py    # Serverless Python sample
runway gen-sample cdk-py    # CDK Python sample
runway gen-sample terraform # Terraform sample
```

### Terraform-Specific

```bash
runway tfenv install    # Install specific Terraform version
```

## Best Practices

### 1. Version Locking

Lock Runway version per-project in `pyproject.toml`:

```toml
[tool.poetry.dependencies]
runway = "^2.0.0"
```

### 2. Git Branch Strategy

Use branch names to indicate environment:

- `ENV-dev` → dev environment
- `ENV-staging` → staging environment
- `ENV-prod` → prod environment

Or set `DEPLOY_ENVIRONMENT` explicitly in CI/CD.

### 3. Module Organization

```
project/
├── runway.yml
├── networking.tf/
│   ├── main.tf
│   ├── dev.tfvars
│   └── prod.tfvars
├── app.sls/
│   ├── serverless.yml
│   ├── package.json
│   └── env/
│       ├── dev.yml
│       └── prod.yml
└── frontend.web/
    └── ...
```

### 4. CI/CD Integration

Always use `--ci` flag in CI/CD pipelines:

```bash
export CI=1  # or use --ci flag
runway deploy --deploy-environment ${ENV}
```

### 5. Always Plan Before Deploy

Run `runway plan` to preview changes before deploying:

```bash
runway plan --ci --deploy-environment prod
# Review output carefully
runway deploy --ci --deploy-environment prod
```

### 6. Use Remote Modules for Shared Infrastructure

```yaml
deployments:
  - modules:
      - path: git::https://github.com/org/repo.git//path/to/module?branch=main
```

### 7. Security Best Practices

- Never commit secrets - use SSM Parameter Store or Secrets Manager
- Use IAM roles with `assume_role` for cross-account deployments
- Enable termination protection for production stacks (CFNgin)
- Review changes with `runway plan` before deploying
- Use protected stacks for critical infrastructure (CFNgin)

## Troubleshooting

### Error: "EOF when reading a line"

**Cause**: Runway is trying to prompt for input in a non-interactive environment

**Solution**:

```bash
# Set CI environment variable
export CI=1
runway deploy

# Or use --ci flag
runway deploy --ci
```

### Error: Module not detected

**Symptoms**: Runway doesn't recognize your module

**Solutions**:

1. Ensure proper file extension (`.tf`, `.cfn`, `.sls`, `.cdk`, `.web`)
2. Check that required config files exist:
   - Terraform: `*.tf` files
   - CFNgin: `config.yml` or `config.yaml`
   - Serverless: `serverless.yml`
   - CDK: `cdk.json`

### Error: Environment not found

**Cause**: Runway can't determine the deployment environment

**Solutions**:

1. Set `DEPLOY_ENVIRONMENT` explicitly:

   ```bash
   export DEPLOY_ENVIRONMENT=dev
   runway deploy
   ```

2. Use git branch naming convention:

   ```bash
   git checkout -b ENV-dev
   ```

3. Check that environment files exist for the module type

### Error: Terraform version issues

**Cause**: Wrong Terraform version or version not found

**Solution**:

```yaml
# Specify version in runway.yml
modules:
  - path: myapp.tf
    options:
      terraform_version: "1.5.0"
```

Runway will automatically download and cache the specified version.

### Error: npm/node issues with CDK or Serverless

**Symptoms**: Module fails to initialize or deploy

**Solutions**:

1. Ensure npm is installed: `npm --version`
2. Check `package.json` includes required dependencies
3. Commit `package-lock.json` to repository
4. Run `runway init` to install dependencies

### Debug Mode

Enable debug logging for detailed troubleshooting:

```bash
runway deploy --debug
```

## Module-Specific Configuration

For detailed configuration guides for each module type, read the appropriate steering file:

- **Terraform**: Read `terraform-modules.md` steering file
- **CloudFormation/CFNgin**: Read `cloudformation-modules.md` steering file
- **Serverless Framework**: Read `serverless-modules.md` steering file
- **AWS CDK**: Read `cdk-modules.md` steering file
- **Advanced Features**: Read `advanced-features.md` steering file

## Additional Resources

- Official Documentation: <https://runway.readthedocs.io>
- GitHub Repository: <https://github.com/rackspace/runway>
- Quickstart Guides: <https://runway.readthedocs.io/page/quickstart/index.html>

---

**CLI Tool**: `runway`
**Installation**: `poetry add --group deploy runway` or `pip install runway`
