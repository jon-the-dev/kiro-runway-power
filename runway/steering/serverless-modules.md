# Serverless Framework Modules Guide

Complete guide for configuring and deploying Serverless Framework applications with Runway.

## Overview

Runway integrates seamlessly with Serverless Framework for deploying Lambda functions and serverless applications. Runway's deploy environment maps 1-to-1 with Serverless stages, making multi-environment deployments straightforward.

## Prerequisites

- **npm installed** - Required for Serverless Framework
- **Serverless as dev dependency**: `npm install --save-dev serverless`

## Configuration Files

Serverless modules use these configuration files:

- **`serverless.yml`** (REQUIRED) - Standard Serverless Framework configuration
- **`package.json`** (REQUIRED) - npm dependencies including Serverless
- **`env/STAGE-REGION.yml`** or **`config-STAGE-REGION.yml`** - Region-specific config
- **`env/STAGE.yml`** or **`config-STAGE.yml`** - Stage-wide config

## Basic Serverless Module Structure

```
myapp.sls/
├── serverless.yml
├── package.json
├── package-lock.json
├── handler.js
├── env/
│   ├── dev.yml
│   ├── dev-us-east-1.yml
│   ├── prod.yml
│   └── prod-us-east-1.yml
└── node_modules/
```

## Serverless Configuration

### Basic serverless.yml

```yaml
# serverless.yml
service: myapp

provider:
  name: aws
  runtime: nodejs18.x
  stage: ${opt:stage, 'dev'}
  region: ${opt:region, 'us-east-1'}
  environment:
    STAGE: ${self:provider.stage}
    REGION: ${self:provider.region}

functions:
  hello:
    handler: handler.hello
    events:
      - http:
          path: hello
          method: get
```

### With Environment-Specific Configuration

```yaml
# serverless.yml
service: myapp

custom:
  # Load environment-specific config
  config: ${file(env/${opt:stage}.yml)}

provider:
  name: aws
  runtime: nodejs18.x
  stage: ${opt:stage, 'dev'}
  region: ${opt:region, 'us-east-1'}
  environment:
    STAGE: ${self:provider.stage}
    TABLE_NAME: ${self:custom.config.tableName}
    API_KEY: ${self:custom.config.apiKey}

functions:
  api:
    handler: handler.api
    memorySize: ${self:custom.config.memorySize}
    timeout: ${self:custom.config.timeout}
    events:
      - http:
          path: api/{proxy+}
          method: ANY
```

**env/dev.yml:**

```yaml
tableName: myapp-dev-table
apiKey: dev-api-key
memorySize: 256
timeout: 10
```

**env/prod.yml:**

```yaml
tableName: myapp-prod-table
apiKey: ${ssm:/myapp/prod/api-key}
memorySize: 1024
timeout: 30
```

## package.json Configuration

**package.json:**

```json
{
  "name": "myapp-sls",
  "version": "1.0.0",
  "description": "Serverless application",
  "scripts": {
    "deploy": "serverless deploy"
  },
  "devDependencies": {
    "serverless": "^3.38.0"
  },
  "dependencies": {
    "aws-sdk": "^2.1467.0"
  }
}
```

**Important**: Always commit `package-lock.json` to ensure consistent deployments.

## Runway Configuration for Serverless

### Simple Configuration

```yaml
# runway.yml
deployments:
  - modules:
      - path: myapp.sls
    regions:
      - us-east-1
    environments:
      dev: true
      prod: true
```

Runway automatically:

- Runs `npm ci` to install dependencies
- Passes environment as `--stage` to Serverless
- Passes region as `--region` to Serverless

### Advanced Configuration

```yaml
deployments:
  - modules:
      - path: myapp.sls
        options:
          skip_npm_ci: false  # Set true to skip npm ci
          args:
            - '--verbose'
            - '--config'
            - 'custom-serverless.yml'
          extend_serverless_yml:
            custom:
              env:
                memorySize: 512
        parameters:
          namespace: myapp-${env DEPLOY_ENVIRONMENT}
    regions:
      - us-east-1
      - us-west-2
    environments:
      dev: true
      prod: 123456789012  # AWS Account ID
```

## Stage and Environment Mapping

**Key Concept**: Runway's `DEPLOY_ENVIRONMENT` maps directly to Serverless `stage`.

```
Runway Environment → Serverless Stage
dev                → dev
staging            → staging
prod               → prod
```

This means:

- `runway deploy` with `DEPLOY_ENVIRONMENT=dev` → `serverless deploy --stage dev`
- Git branch `ENV-prod` → `serverless deploy --stage prod`

## Environment Configuration Files

### File Naming Conventions

Runway looks for environment files in this order:

1. `env/STAGE-REGION.yml` (highest priority)
2. `config-STAGE-REGION.yml`
3. `env/STAGE.yml`
4. `config-STAGE.yml`

### Example Configuration

**env/dev.yml:**

```yaml
# Development environment config
tableName: myapp-dev-table
bucketName: myapp-dev-bucket
logLevel: debug
memorySize: 256
timeout: 10
```

**env/prod.yml:**

```yaml
# Production environment config
tableName: myapp-prod-table
bucketName: myapp-prod-bucket
logLevel: info
memorySize: 1024
timeout: 30
```

**env/prod-us-west-2.yml:**

```yaml
# Production US West 2 specific overrides
tableName: myapp-prod-usw2-table
bucketName: myapp-prod-usw2-bucket
```

## Serverless Plugins

### Installing Plugins

**package.json:**

```json
{
  "devDependencies": {
    "serverless": "^3.38.0",
    "serverless-offline": "^13.3.0",
    "serverless-plugin-typescript": "^2.1.5"
  }
}
```

**serverless.yml:**

```yaml
plugins:
  - serverless-offline
  - serverless-plugin-typescript

custom:
  serverless-offline:
    httpPort: 3000
```

### Common Plugins

- **serverless-offline** - Local development server
- **serverless-plugin-typescript** - TypeScript support
- **serverless-webpack** - Webpack bundling
- **serverless-python-requirements** - Python dependencies
- **serverless-domain-manager** - Custom domain management

## Skipping npm ci

If you manage dependencies separately or want faster deployments:

```yaml
modules:
  - path: myapp.sls
    options:
      skip_npm_ci: true
```

**Use cases**:

- Dependencies already installed
- Using Docker for builds
- Custom dependency management

## Extending serverless.yml

Override Serverless configuration from Runway:

```yaml
modules:
  - path: myapp.sls
    options:
      extend_serverless_yml:
        provider:
          environment:
            CUSTOM_VAR: custom-value
        custom:
          webpack:
            includeModules: true
```

This merges with your `serverless.yml` at deployment time.

## Custom Serverless Arguments

Pass additional arguments to Serverless CLI:

```yaml
modules:
  - path: myapp.sls
    options:
      args:
        - '--verbose'
        - '--aws-profile'
        - 'myprofile'
        - '--param'
        - 'key=value'
```

## Multi-Region Deployment

Deploy the same Serverless app to multiple regions:

```yaml
deployments:
  - modules:
      - path: myapp.sls
    regions:
      - us-east-1
      - us-west-2
      - eu-west-1
```

Runway deploys to each region sequentially, using region-specific config files.

## Using SSM Parameters

Reference AWS SSM parameters in your configuration:

**serverless.yml:**

```yaml
provider:
  environment:
    DB_PASSWORD: ${ssm:/myapp/${opt:stage}/db-password}
    API_KEY: ${ssm:/myapp/${opt:stage}/api-key~true}  # ~true for encrypted
```

**env/prod.yml:**

```yaml
dbEndpoint: ${ssm:/myapp/prod/db-endpoint}
```

## Python Serverless Applications

### Directory Structure

```
myapp.sls/
├── serverless.yml
├── package.json
├── requirements.txt
├── handler.py
└── env/
    ├── dev.yml
    └── prod.yml
```

### serverless.yml for Python

```yaml
service: myapp-python

provider:
  name: aws
  runtime: python3.11
  stage: ${opt:stage, 'dev'}
  region: ${opt:region, 'us-east-1'}

functions:
  api:
    handler: handler.main
    events:
      - http:
          path: api/{proxy+}
          method: ANY

plugins:
  - serverless-python-requirements

custom:
  pythonRequirements:
    dockerizePip: true
```

### package.json for Python

```json
{
  "name": "myapp-python-sls",
  "devDependencies": {
    "serverless": "^3.38.0",
    "serverless-python-requirements": "^6.1.0"
  }
}
```

## Troubleshooting

### Error: Serverless command not found

**Cause**: Serverless not installed or not in node_modules

**Solution**:

```bash
cd myapp.sls
npm install --save-dev serverless
# Commit package.json and package-lock.json
```

### Error: npm ci failed

**Cause**: package-lock.json missing or out of sync

**Solution**:

```bash
cd myapp.sls
rm -rf node_modules package-lock.json
npm install
git add package-lock.json
git commit -m "Update package-lock.json"
```

### Error: Stage not found

**Cause**: Environment config file missing

**Solution**:

1. Create `env/STAGE.yml` file
2. Or set default stage in serverless.yml:

   ```yaml
   provider:
     stage: ${opt:stage, 'dev'}
   ```

### Error: Function deployment failed

**Cause**: Function package too large or timeout

**Solution**:

1. Use webpack or esbuild to reduce package size
2. Exclude dev dependencies:

   ```yaml
   package:
     patterns:
       - '!node_modules/aws-sdk/**'
       - '!.git/**'
   ```

3. Increase timeout in serverless.yml

### Error: IAM permissions denied

**Cause**: Insufficient AWS permissions for deployment

**Solution**:

1. Verify AWS credentials: `aws sts get-caller-identity`
2. Ensure IAM user/role has required permissions:
   - CloudFormation
   - Lambda
   - API Gateway
   - S3 (for deployment artifacts)
   - IAM (for creating function roles)

## Best Practices

1. **Always use package-lock.json** - Commit it to ensure consistent deployments
2. **Use environment config files** - Separate config from code
3. **Reference SSM for secrets** - Never hardcode sensitive values
4. **Set appropriate memory and timeout** - Optimize for cost and performance
5. **Use Serverless plugins** - Leverage ecosystem for common tasks
6. **Test locally with serverless-offline** - Before deploying to AWS
7. **Use layers for shared dependencies** - Reduce deployment package size
8. **Enable X-Ray tracing** - For production debugging
9. **Set up proper IAM roles** - Follow least privilege principle
10. **Use CloudWatch Logs** - Monitor function execution

## Example: Complete Serverless Module

**Directory structure:**

```
api.sls/
├── serverless.yml
├── package.json
├── package-lock.json
├── handler.js
└── env/
    ├── dev.yml
    └── prod.yml
```

**serverless.yml:**

```yaml
service: myapp-api

custom:
  config: ${file(env/${opt:stage}.yml)}

provider:
  name: aws
  runtime: nodejs18.x
  stage: ${opt:stage, 'dev'}
  region: ${opt:region, 'us-east-1'}
  environment:
    STAGE: ${self:provider.stage}
    TABLE_NAME: ${self:custom.config.tableName}
  iamRoleStatements:
    - Effect: Allow
      Action:
        - dynamodb:Query
        - dynamodb:GetItem
        - dynamodb:PutItem
      Resource: !GetAtt Table.Arn

functions:
  api:
    handler: handler.api
    memorySize: ${self:custom.config.memorySize}
    timeout: ${self:custom.config.timeout}
    events:
      - http:
          path: api/{proxy+}
          method: ANY
          cors: true

resources:
  Resources:
    Table:
      Type: AWS::DynamoDB::Table
      Properties:
        TableName: ${self:custom.config.tableName}
        BillingMode: PAY_PER_REQUEST
        AttributeDefinitions:
          - AttributeName: id
            AttributeType: S
        KeySchema:
          - AttributeName: id
            KeyType: HASH
```

**package.json:**

```json
{
  "name": "myapp-api",
  "version": "1.0.0",
  "devDependencies": {
    "serverless": "^3.38.0"
  },
  "dependencies": {
    "aws-sdk": "^2.1467.0"
  }
}
```

**env/dev.yml:**

```yaml
tableName: myapp-dev-table
memorySize: 256
timeout: 10
```

**env/prod.yml:**

```yaml
tableName: myapp-prod-table
memorySize: 1024
timeout: 30
```

**runway.yml:**

```yaml
deployments:
  - modules:
      - path: api.sls
    regions:
      - us-east-1
    environments:
      dev: true
      prod: 123456789012
```

This configuration provides a complete, production-ready Serverless module setup with Runway.
