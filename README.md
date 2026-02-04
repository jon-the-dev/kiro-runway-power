# Runway Power for Kiro

A comprehensive Kiro power that provides AI-assisted infrastructure deployment using Runway - a lightweight integration tool that unifies AWS CDK, Serverless Framework, CloudFormation, Terraform, and static sites with GitOps best practices.

## What is This Power?

This power equips Kiro with deep knowledge of Runway infrastructure deployment workflows, including:

- Complete Runway configuration and deployment guidance
- Module-specific expertise (Terraform, CDK, Serverless, CloudFormation, Static Sites)
- Custom deployment hooks for advanced workflows
- AWS documentation access through integrated MCP server
- Environment-specific configuration management
- Multi-tool infrastructure orchestration

## What Does It Do?

The Runway power enables Kiro to help you with:

### Core Runway Operations

- Initialize new Runway projects with proper structure
- Configure runway.yml for multi-module deployments
- Set up environment-specific configurations (dev, staging, prod)
- Deploy, plan, and destroy infrastructure across multiple tools
- Manage dependencies between infrastructure modules
- Handle cross-account deployments with IAM role assumption

### Module-Specific Support

- **Terraform**: Variable files, backend configuration, version management
- **CloudFormation/CFNgin**: Stack dependencies, blueprints, environment files
- **Serverless Framework**: Stage mapping, npm configuration, custom variables
- **AWS CDK**: Build steps, feature flags, TypeScript/Python setup
- **Static Sites**: S3 + CloudFront deployments with cache invalidation

### Advanced Features

- **Custom Hooks**: Pre-built hooks for common deployment tasks
  - CloudFront cache invalidation
  - Docker image builds and ECR pushes
  - SAM template deployments
  - Docker Compose integration for local development
  - Environment file generation
  - NPM build automation

- **Dynamic Lookups**: Reference values from SSM, CloudFormation outputs, environment variables
- **Parallel Deployments**: Deploy multiple modules simultaneously
- **Conditional Deployment**: Environment-specific module deployment
- **Remote Modules**: Use shared infrastructure modules from git repositories

### AWS Documentation Access

Through the integrated AWS documentation MCP server, Kiro can:

- Look up AWS service documentation while configuring infrastructure
- Reference API specifications and CloudFormation resource types
- Provide context-aware AWS best practices

## How to Use It

### Activating the Power

The power is automatically available when installed. Kiro will use Runway knowledge when you mention keywords like:

- runway, infrastructure, deployment
- terraform, cdk, serverless, cloudformation
- iac (infrastructure as code)

### Common Use Cases

#### 1. Starting a New Infrastructure Project

```
"Help me set up a new Runway project with Terraform modules for dev and prod environments"
```

Kiro will guide you through:

- Installing Runway with Poetry or pip
- Creating runway.yml configuration
- Setting up environment-specific .tfvars files
- Configuring git branch strategy for environments

#### 2. Deploying Multi-Tool Infrastructure

```
"I need to deploy a Terraform VPC, then a Serverless API, then a CDK frontend stack"
```

Kiro will help you:

- Structure modules with proper dependencies
- Configure runway.yml with correct module order
- Set up environment files for each module type
- Handle outputs/inputs between modules

#### 3. Adding Custom Deployment Hooks

```
"Add a CloudFront invalidation hook after my static site deploys"
```

Kiro will:

- Configure the pre-built cloudfront_invalidation.py hook
- Add it to your CFNgin configuration
- Set up proper parameters and timing

#### 4. Troubleshooting Deployments

```
"My Terraform module isn't being detected by Runway"
```

Kiro will:

- Check file extensions and structure
- Verify required configuration files exist
- Suggest fixes for common issues
- Help with debug mode and logging

#### 5. Environment Management

```
"Set up different AWS accounts for dev and prod with proper IAM role assumption"
```

Kiro will:

- Configure assume_role in runway.yml
- Set up account IDs per environment
- Configure cross-account deployment workflows

### Available Steering Files

For detailed guidance on specific topics, Kiro can reference:

- **terraform-modules.md** - Terraform configuration, variables, backends
- **cloudformation-modules.md** - CFNgin stacks, dependencies, blueprints
- **serverless-modules.md** - Serverless Framework integration
- **cdk-modules.md** - AWS CDK setup and configuration
- **advanced-features.md** - Parallel deployments, lookups, remote modules
- **hooks.md** - Custom hooks with examples

### Custom Hooks Included

This power includes production-ready hooks in the `hooks/` directory:

1. **cloudfront_invalidation.py** - Invalidate CloudFront distributions after deployment
2. **docker_build_push.py** - Build and push Docker images to ECR
3. **docker_compose_integration.py** - Start/stop Docker Compose for local development
4. **sam_deploy.py** - Deploy AWS SAM templates
5. **env_file_generator.py** - Generate environment files from AWS resources
6. **npm_build.py** - Run npm build steps during deployment

Each hook includes:

- Comprehensive error handling
- CLI interface for testing
- CFNgin integration
- Unit tests

### Example Interactions

**Simple deployment:**

```
User: "Deploy my infrastructure to dev"
Kiro: [Checks runway.yml, verifies environment, runs: poetry run runway deploy --deploy-environment dev]
```

**Complex setup:**

```
User: "I need a Terraform VPC that outputs the VPC ID, then a Serverless API that uses that VPC ID"
Kiro: [Creates runway.yml with proper module order, sets up CFNgin lookups, configures environment files]
```

**Hook integration:**

```
User: "After deploying my frontend, invalidate the CloudFront cache"
Kiro: [Adds post_deploy hook to CFNgin config with cloudfront_invalidation.py]
```

## Installation

This power is installed as a Kiro power package. Once installed:

1. Kiro automatically has access to all Runway knowledge
2. The AWS documentation MCP server is available for lookups
3. Custom hooks are available in the power's hooks directory
4. Steering files provide detailed module-specific guidance

## Prerequisites

To use Runway deployments, you'll need:

- Python 3.8+ (for Runway itself)
- AWS CLI configured with credentials
- Git (for GitOps workflows)
- Module-specific tools:
  - npm (for CDK and Serverless modules)
  - Terraform (managed by Runway, but can be pre-installed)

## Power Structure

```
powers/runway/
├── POWER.md                    # Power metadata and overview
├── mcp.json                    # AWS documentation MCP server config
├── steering/                   # Detailed module guides
│   ├── terraform-modules.md
│   ├── cloudformation-modules.md
│   ├── serverless-modules.md
│   ├── cdk-modules.md
│   ├── advanced-features.md
│   └── hooks.md
└── hooks/                      # Custom deployment hooks
    ├── cloudfront_invalidation.py
    ├── docker_build_push.py
    ├── docker_compose_integration.py
    ├── sam_deploy.py
    ├── env_file_generator.py
    ├── npm_build.py
    └── [test files and examples]
```

## Benefits

- **Unified Interface**: One configuration file for multiple IaC tools
- **GitOps Ready**: Environment detection from git branches
- **Version Management**: Automatic Terraform version management
- **Dependency Handling**: Deploy modules in correct order with proper dependencies
- **Environment Isolation**: Separate configurations for dev/staging/prod
- **Extensible**: Custom hooks for any deployment workflow
- **AI-Assisted**: Kiro provides intelligent guidance and troubleshooting

## Resources

- [Runway Official Documentation](https://runway.readthedocs.io)
- [Runway GitHub Repository](https://github.com/rackspace/runway)
- [Runway Quickstart Guides](https://runway.readthedocs.io/page/quickstart/index.html)

## Contributing

To add new hooks or improve existing ones:

1. Add hook files to `powers/runway/hooks/`
2. Include unit tests following the existing pattern
3. Update `hooks.md` steering file with usage examples
4. Test with both CLI and CFNgin integration

## License

See LICENSE file for details.
