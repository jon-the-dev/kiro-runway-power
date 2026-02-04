# AWS CDK Modules Guide

Complete guide for configuring and deploying AWS CDK applications with Runway.

## Overview

Runway integrates with AWS CDK (Cloud Development Kit) to deploy infrastructure defined in TypeScript, Python, Java, or other supported languages. Runway handles npm dependency installation and passes environment context to your CDK application.

## Prerequisites

- **npm installed** - Required for CDK
- **CDK as dev dependency**: `npm install --save-dev aws-cdk`
- **CDK application initialized**: `cdk init app --language typescript` (or your preferred language)

## Configuration Files

CDK modules use these configuration files:

- **`cdk.json`** (REQUIRED) - CDK application configuration
- **`package.json`** (REQUIRED for TypeScript/JavaScript) - npm dependencies including CDK
- **`app.py`** or **`app.ts`** - CDK application entry point
- No environment files needed - use Runway's `environments` configuration

## Basic CDK Module Structure

### TypeScript CDK Module

```
myapp.cdk/
├── cdk.json
├── package.json
├── package-lock.json
├── tsconfig.json
├── bin/
│   └── app.ts
├── lib/
│   └── stack.ts
└── node_modules/
```

### Python CDK Module

```
myapp.cdk/
├── cdk.json
├── package.json
├── requirements.txt
├── app.py
└── stacks/
    └── stack.py
```

## CDK Configuration

### cdk.json

```json
{
  "app": "npx ts-node --prefer-ts-exts bin/app.ts",
  "context": {
    "@aws-cdk/core:enableStackNameDuplicates": false,
    "aws-cdk:enableDiffNoFail": true,
    "@aws-cdk/core:stackRelativeExports": true
  }
}
```

**Recommended Feature Flag**:

```json
{
  "context": {
    "aws-cdk:enableDiffNoFail": true
  }
}
```

This prevents CDK diff failures from blocking deployments.

### package.json for TypeScript

```json
{
  "name": "myapp-cdk",
  "version": "1.0.0",
  "scripts": {
    "build": "tsc",
    "watch": "tsc -w",
    "cdk": "cdk"
  },
  "devDependencies": {
    "@types/node": "^20.10.0",
    "aws-cdk": "^2.114.0",
    "ts-node": "^10.9.2",
    "typescript": "^5.3.3"
  },
  "dependencies": {
    "aws-cdk-lib": "^2.114.0",
    "constructs": "^10.3.0"
  }
}
```

### requirements.txt for Python

```
aws-cdk-lib==2.114.0
constructs>=10.0.0
```

## Runway Configuration for CDK

### Simple Configuration

```yaml
# runway.yml
deployments:
  - modules:
      - path: myapp.cdk
    regions:
      - us-east-1
    environments:
      dev: true
      prod: true
```

### Advanced Configuration

```yaml
deployments:
  - modules:
      - path: myapp.cdk
        options:
          skip_npm_ci: false
          build_steps:
            - npx tsc
            - npm run build
          args:
            - '--require-approval'
            - 'never'
        parameters:
          namespace: myapp-${env DEPLOY_ENVIRONMENT}
        environments:
          dev: true
          prod: 123456789012  # AWS Account ID
    regions:
      - us-east-1
      - us-west-2
```

## CDK Application Code

### TypeScript Example

**bin/app.ts:**

```typescript
#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { MyStack } from '../lib/stack';

const app = new cdk.App();

// Get environment from context
const environment = app.node.tryGetContext('environment') || 'dev';
const region = app.node.tryGetContext('region') || 'us-east-1';

new MyStack(app, `MyStack-${environment}`, {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: region
  },
  environment: environment
});

app.synth();
```

**lib/stack.ts:**

```typescript
import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';

interface MyStackProps extends cdk.StackProps {
  environment: string;
}

export class MyStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: MyStackProps) {
    super(scope, id, props);

    // Lambda function
    const handler = new lambda.Function(this, 'Handler', {
      runtime: lambda.Runtime.NODEJS_18_X,
      code: lambda.Code.fromAsset('lambda'),
      handler: 'index.handler',
      environment: {
        ENVIRONMENT: props.environment
      }
    });

    // API Gateway
    new apigateway.LambdaRestApi(this, 'Api', {
      handler: handler,
      restApiName: `myapp-${props.environment}-api`
    });
  }
}
```

### Python Example

**app.py:**

```python
#!/usr/bin/env python3
import os
from aws_cdk import App, Environment
from stacks.stack import MyStack

app = App()

# Get environment from context
environment = app.node.try_get_context("environment") or "dev"
region = app.node.try_get_context("region") or "us-east-1"

MyStack(
    app,
    f"MyStack-{environment}",
    env=Environment(
        account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
        region=region
    ),
    environment=environment
)

app.synth()
```

**stacks/stack.py:**

```python
from aws_cdk import Stack, aws_lambda as lambda_, aws_apigateway as apigw
from constructs import Construct

class MyStack(Stack):
    def __init__(self, scope: Construct, id: str, environment: str, **kwargs):
        super().__init__(scope, id, **kwargs)
        
        # Lambda function
        handler = lambda_.Function(
            self, "Handler",
            runtime=lambda_.Runtime.PYTHON_3_11,
            code=lambda_.Code.from_asset("lambda"),
            handler="index.handler",
            environment={
                "ENVIRONMENT": environment
            }
        )
        
        # API Gateway
        apigw.LambdaRestApi(
            self, "Api",
            handler=handler,
            rest_api_name=f"myapp-{environment}-api"
        )
```

## Accessing Runway Environment in CDK

Runway passes the deployment environment to CDK via context:

```typescript
// In your CDK app
const environment = app.node.tryGetContext('environment');
const region = app.node.tryGetContext('region');
```

Or in Python:

```python
environment = app.node.try_get_context("environment")
region = app.node.try_get_context("region")
```

## Build Steps

If your CDK app requires compilation or build steps:

```yaml
modules:
  - path: myapp.cdk
    options:
      build_steps:
        - npx tsc
        - npm run build
        - python -m pip install -r requirements.txt
```

Build steps run before CDK deployment.

## Skipping npm ci

If you manage dependencies separately:

```yaml
modules:
  - path: myapp.cdk
    options:
      skip_npm_ci: true
```

## Custom CDK Arguments

Pass additional arguments to CDK CLI:

```yaml
modules:
  - path: myapp.cdk
    options:
      args:
        - '--require-approval'
        - 'never'
        - '--verbose'
        - '--outputs-file'
        - 'outputs.json'
```

Common arguments:

- `--require-approval never` - Skip approval prompts
- `--verbose` - Detailed output
- `--outputs-file FILE` - Save stack outputs to file
- `--exclusively` - Only deploy specified stacks

## Multi-Stack CDK Applications

Deploy multiple stacks from one CDK app:

**app.ts:**

```typescript
const app = new cdk.App();
const environment = app.node.tryGetContext('environment') || 'dev';

// Network stack
const networkStack = new NetworkStack(app, `Network-${environment}`, {
  environment: environment
});

// Application stack (depends on network)
new ApplicationStack(app, `Application-${environment}`, {
  environment: environment,
  vpc: networkStack.vpc
});

app.synth();
```

CDK automatically handles stack dependencies.

## Environment-Specific Configuration

Use CDK context for environment-specific values:

**cdk.json:**

```json
{
  "app": "npx ts-node bin/app.ts",
  "context": {
    "dev": {
      "instanceType": "t3.micro",
      "minCapacity": 1,
      "maxCapacity": 2
    },
    "prod": {
      "instanceType": "t3.large",
      "minCapacity": 3,
      "maxCapacity": 10
    }
  }
}
```

**app.ts:**

```typescript
const environment = app.node.tryGetContext('environment') || 'dev';
const config = app.node.tryGetContext(environment);

new MyStack(app, `MyStack-${environment}`, {
  instanceType: config.instanceType,
  minCapacity: config.minCapacity,
  maxCapacity: config.maxCapacity
});
```

## CDK Outputs

Export stack outputs for use by other modules:

**stack.ts:**

```typescript
export class MyStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: cdk.StackProps) {
    super(scope, id, props);

    const api = new apigateway.RestApi(this, 'Api');

    // Export API URL
    new cdk.CfnOutput(this, 'ApiUrl', {
      value: api.url,
      exportName: `${this.stackName}-ApiUrl`
    });
  }
}
```

Reference in other Runway modules:

```yaml
deployments:
  - modules:
      - path: myapp.cdk
      - path: integration-tests.sls
        parameters:
          api_url: ${cfn MyStack-dev.ApiUrl}
```

## CDK Bootstrap

CDK requires bootstrapping the AWS environment:

```bash
# Bootstrap once per account/region
cdk bootstrap aws://ACCOUNT-ID/REGION

# Or let Runway handle it on first deployment
runway deploy
```

## Troubleshooting

### Error: CDK command not found

**Cause**: CDK not installed in node_modules

**Solution**:

```bash
cd myapp.cdk
npm install --save-dev aws-cdk
git add package.json package-lock.json
git commit -m "Add CDK dependency"
```

### Error: TypeScript compilation failed

**Cause**: TypeScript errors in CDK code

**Solution**:

1. Run TypeScript compiler to see errors:

   ```bash
   npx tsc
   ```

2. Fix TypeScript errors
3. Ensure `tsconfig.json` is properly configured

### Error: CDK bootstrap required

**Cause**: AWS environment not bootstrapped for CDK

**Solution**:

```bash
cdk bootstrap aws://ACCOUNT-ID/REGION
```

Or add to runway.yml:

```yaml
modules:
  - path: myapp.cdk
    options:
      args:
        - '--require-approval'
        - 'never'
```

### Error: Stack already exists

**Cause**: Stack name conflict

**Solution**:

1. Use unique stack names per environment:

   ```typescript
   new MyStack(app, `MyStack-${environment}`, {});
   ```

2. Or destroy existing stack:

   ```bash
   runway destroy
   ```

### Error: npm ci failed

**Cause**: package-lock.json missing or out of sync

**Solution**:

```bash
cd myapp.cdk
rm -rf node_modules package-lock.json
npm install
git add package-lock.json
git commit -m "Update package-lock.json"
```

### Error: Python dependencies not found

**Cause**: Python packages not installed

**Solution**:

```bash
cd myapp.cdk
python -m pip install -r requirements.txt
```

Or add build step:

```yaml
modules:
  - path: myapp.cdk
    options:
      build_steps:
        - python -m pip install -r requirements.txt
```

## Best Practices

1. **Use CDK v2** - CDK v2 consolidates all constructs into `aws-cdk-lib`
2. **Enable enableDiffNoFail** - Prevents diff failures from blocking deployments
3. **Commit package-lock.json** - Ensures consistent dependency versions
4. **Use environment-specific stack names** - Avoid conflicts between environments
5. **Export important outputs** - Make values available to other modules
6. **Use CDK context for config** - Keep environment-specific values in cdk.json
7. **Bootstrap once per account/region** - Required for CDK deployments
8. **Use constructs for reusability** - Create custom constructs for common patterns
9. **Test CDK synth locally** - Run `cdk synth` before deploying
10. **Use CDK aspects for cross-cutting concerns** - Apply tags, security policies, etc.

## Example: Complete CDK Module

**Directory structure:**

```
infrastructure.cdk/
├── cdk.json
├── package.json
├── package-lock.json
├── tsconfig.json
├── bin/
│   └── app.ts
└── lib/
    ├── network-stack.ts
    └── application-stack.ts
```

**cdk.json:**

```json
{
  "app": "npx ts-node --prefer-ts-exts bin/app.ts",
  "context": {
    "aws-cdk:enableDiffNoFail": true,
    "dev": {
      "vpcCidr": "10.0.0.0/16",
      "instanceType": "t3.micro"
    },
    "prod": {
      "vpcCidr": "10.1.0.0/16",
      "instanceType": "t3.large"
    }
  }
}
```

**package.json:**

```json
{
  "name": "infrastructure-cdk",
  "version": "1.0.0",
  "scripts": {
    "build": "tsc",
    "cdk": "cdk"
  },
  "devDependencies": {
    "@types/node": "^20.10.0",
    "aws-cdk": "^2.114.0",
    "ts-node": "^10.9.2",
    "typescript": "^5.3.3"
  },
  "dependencies": {
    "aws-cdk-lib": "^2.114.0",
    "constructs": "^10.3.0"
  }
}
```

**bin/app.ts:**

```typescript
#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { NetworkStack } from '../lib/network-stack';
import { ApplicationStack } from '../lib/application-stack';

const app = new cdk.App();

const environment = app.node.tryGetContext('environment') || 'dev';
const region = app.node.tryGetContext('region') || 'us-east-1';
const config = app.node.tryGetContext(environment);

const networkStack = new NetworkStack(app, `Network-${environment}`, {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: region
  },
  vpcCidr: config.vpcCidr
});

new ApplicationStack(app, `Application-${environment}`, {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: region
  },
  vpc: networkStack.vpc,
  instanceType: config.instanceType
});

app.synth();
```

**runway.yml:**

```yaml
deployments:
  - modules:
      - path: infrastructure.cdk
        options:
          build_steps:
            - npx tsc
          args:
            - '--require-approval'
            - 'never'
    regions:
      - us-east-1
    environments:
      dev: true
      prod: 123456789012
```

This configuration provides a complete, production-ready CDK module setup with Runway.
