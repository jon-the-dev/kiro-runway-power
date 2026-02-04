# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added

- Pre-commit configuration with Python linting, formatting, type checking, and testing
  - Ruff for linting and formatting
  - mypy for type checking
  - pytest for running tests
  - General file hygiene checks (trailing whitespace, EOF, YAML validation, etc.)
- Created Runway power with comprehensive documentation
  - POWER.md with overview, onboarding, common workflows, and troubleshooting
  - mcp.json with AWS documentation MCP server integration
  - Steering files for module-specific guides:
    - terraform-modules.md - Complete Terraform configuration guide
    - cloudformation-modules.md - CFNgin and CloudFormation guide
    - serverless-modules.md - Serverless Framework integration guide
    - cdk-modules.md - AWS CDK deployment guide
    - advanced-features.md - Parallel deployments, lookups, and remote modules
    - hooks.md - Custom hooks guide with examples and best practices
- Reviewed and documented existing custom hooks:
  - cloudfront_invalidation.py - CloudFront cache invalidation
  - docker_build_push.py - Docker image builds and ECR pushes
  - docker_compose_integration.py - Docker Compose lifecycle management
  - env_file_generator.py - Environment file generation from stack outputs
  - npm_build.py - Next.js/Node.js builds and S3 sync
  - sam_deploy.py - AWS SAM template deployment and deletion
