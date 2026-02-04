# CloudFormation/CFNgin Modules Guide

Complete guide for configuring and deploying CloudFormation stacks with Runway using CFNgin.

## Overview

CFNgin is Runway's CloudFormation orchestration tool that provides stack dependencies, Troposphere support, and environment-specific configurations. It simplifies complex CloudFormation deployments with a declarative configuration format.

## Prerequisites

**None** - CFNgin is included with Runway.

## Configuration Files

CFNgin modules require specific configuration files:

- **`config.yml` or `config.yaml`** (REQUIRED) - CFNgin stack configuration
- **`ENV-REGION.env`** (e.g., `dev-us-east-1.env`) - Region-specific variables
- **`ENV.env`** (e.g., `dev.env`) - Environment-wide variables
- **`blueprints/`** directory (optional) - Python Troposphere blueprints

## Basic CFNgin Module Structure

```
myapp.cfn/
├── config.yml
├── dev.env
├── prod.env
├── dev-us-east-1.env
├── prod-us-east-1.env
└── blueprints/
    ├── __init__.py
    ├── vpc.py
    └── app.py
```

## CFNgin Configuration Format

### Basic config.yml

```yaml
# config.yml
namespace: ${namespace}
cfngin_bucket: cfngin-${namespace}-${region}

stacks:
  - name: vpc
    class_path: blueprints.vpc.VPC
    variables:
      CidrBlock: 10.0.0.0/16
      
  - name: app
    class_path: blueprints.app.Application
    variables:
      InstanceType: t3.micro
```

### With Stack Dependencies

```yaml
namespace: ${namespace}
cfngin_bucket: cfngin-${namespace}-${region}

stacks:
  - name: vpc
    class_path: blueprints.vpc.VPC
    variables:
      CidrBlock: 10.0.0.0/16

  - name: database
    class_path: blueprints.rds.Database
    requires:
      - vpc
    variables:
      VpcId: ${output vpc.VpcId}
      SubnetIds: ${output vpc.PrivateSubnetIds}
      
  - name: application
    class_path: blueprints.app.Application
    requires:
      - vpc
      - database
    variables:
      VpcId: ${output vpc.VpcId}
      DbEndpoint: ${output database.Endpoint}
```

## Environment Files

Environment files use simple `key: value` format:

**dev.env:**

```
namespace: myapp-dev
environment: dev
region: us-east-1
instance_type: t3.micro
```

**prod.env:**

```
namespace: myapp-prod
environment: prod
region: us-east-1
instance_type: t3.large
```

**dev-us-east-1.env:**

```
cfngin_bucket_name: cfngin-myapp-dev-us-east-1
availability_zones: us-east-1a,us-east-1b
```

## Runway Configuration for CFNgin

### Simple Configuration

```yaml
# runway.yml
deployments:
  - modules:
      - path: myapp.cfn
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
      - path: myapp.cfn
        parameters:
          namespace: myapp-${env DEPLOY_ENVIRONMENT}
        tags:
          - app:myapp
          - team:platform
    regions:
      - us-east-1
      - us-west-2
    environments:
      dev: true
      prod: 123456789012  # AWS Account ID
```

## Using Troposphere Blueprints

Troposphere allows you to define CloudFormation templates in Python.

### Blueprint Example

**blueprints/vpc.py:**

```python
from troposphere import Template, Output, Ref, GetAtt
from troposphere.ec2 import VPC, Subnet, InternetGateway, VPCGatewayAttachment

from stacker.blueprints.base import Blueprint
from stacker.blueprints.variables.types import CFNString

class VPC(Blueprint):
    VARIABLES = {
        "CidrBlock": {
            "type": CFNString,
            "description": "CIDR block for VPC",
            "default": "10.0.0.0/16"
        }
    }
    
    def create_template(self):
        t = self.template
        variables = self.get_variables()
        
        # Create VPC
        vpc = t.add_resource(VPC(
            "VPC",
            CidrBlock=variables["CidrBlock"].ref,
            EnableDnsHostnames=True,
            EnableDnsSupport=True
        ))
        
        # Add outputs
        t.add_output(Output(
            "VpcId",
            Value=Ref(vpc)
        ))
        
        return t
```

### Using Raw CloudFormation Templates

You can also use raw CloudFormation JSON/YAML templates:

**config.yml:**

```yaml
stacks:
  - name: vpc
    template_path: templates/vpc.yaml
    variables:
      CidrBlock: 10.0.0.0/16
```

## Stack Dependencies

CFNgin automatically handles stack dependencies using `requires`:

```yaml
stacks:
  - name: networking
    class_path: blueprints.vpc.VPC
    
  - name: security
    class_path: blueprints.security.SecurityGroups
    requires:
      - networking
    variables:
      VpcId: ${output networking.VpcId}
      
  - name: compute
    class_path: blueprints.ec2.Instances
    requires:
      - networking
      - security
    variables:
      VpcId: ${output networking.VpcId}
      SecurityGroupId: ${output security.InstanceSecurityGroupId}
```

CFNgin deploys stacks in dependency order and waits for each to complete.

## Stack Outputs

Reference outputs from other stacks:

```yaml
stacks:
  - name: vpc
    class_path: blueprints.vpc.VPC
    
  - name: app
    class_path: blueprints.app.Application
    variables:
      # Reference output from vpc stack
      VpcId: ${output vpc.VpcId}
      SubnetIds: ${output vpc.PrivateSubnetIds}
```

## Protected Stacks

Mark critical stacks as protected to prevent accidental deletion:

```yaml
stacks:
  - name: production-database
    class_path: blueprints.rds.Database
    protected: true
    variables:
      # ...
```

Protected stacks cannot be destroyed without removing the `protected` flag.

## Stack Tags

Apply tags to all resources in a stack:

```yaml
stacks:
  - name: app
    class_path: blueprints.app.Application
    tags:
      Environment: ${environment}
      Application: myapp
      ManagedBy: runway
    variables:
      # ...
```

## CFNgin Bucket

CFNgin uses an S3 bucket to store templates and track stack state:

```yaml
namespace: ${namespace}
cfngin_bucket: cfngin-${namespace}-${region}
```

The bucket is created automatically if it doesn't exist.

### Custom Bucket Configuration

```yaml
cfngin_bucket: my-custom-cfngin-bucket
cfngin_bucket_region: us-east-1
```

## Lookups in CFNgin

CFNgin supports various lookups for dynamic values:

### Output Lookup

```yaml
variables:
  VpcId: ${output vpc.VpcId}
```

### SSM Parameter Lookup

```yaml
variables:
  DbPassword: ${ssm /myapp/${environment}/db-password}
```

### Environment Variable Lookup

```yaml
variables:
  ApiKey: ${env API_KEY}
```

### CloudFormation Export Lookup

```yaml
variables:
  VpcId: ${cfn shared-vpc.VpcId}
```

## Stack Policies

Protect specific resources from updates:

```yaml
stacks:
  - name: database
    class_path: blueprints.rds.Database
    stack_policy_path: policies/database-policy.json
    variables:
      # ...
```

**policies/database-policy.json:**

```json
{
  "Statement": [
    {
      "Effect": "Deny",
      "Principal": "*",
      "Action": "Update:Delete",
      "Resource": "LogicalResourceId/Database"
    },
    {
      "Effect": "Allow",
      "Principal": "*",
      "Action": "Update:*",
      "Resource": "*"
    }
  ]
}
```

## Conditional Stacks

Deploy stacks only in specific environments:

```yaml
stacks:
  - name: expensive-resources
    class_path: blueprints.compute.LargeCluster
    enabled: ${environment == "prod"}
    variables:
      # ...
```

Or use Runway's environment configuration:

```yaml
# runway.yml
deployments:
  - modules:
      - path: expensive.cfn
        environments:
          prod: true  # Only deploy in prod
```

## Troubleshooting

### Error: CFNgin bucket not accessible

**Cause**: S3 bucket doesn't exist or insufficient permissions

**Solution**:

1. Verify bucket name in config.yml
2. Check AWS credentials have S3 permissions
3. Create bucket manually if needed:

   ```bash
   aws s3 mb s3://cfngin-myapp-dev-us-east-1
   ```

### Error: Stack dependency cycle detected

**Cause**: Circular dependency in `requires` declarations

**Solution**:

1. Review stack dependencies in config.yml
2. Remove circular references
3. Restructure stacks to eliminate cycles

### Error: Output not found

**Cause**: Referenced output doesn't exist in source stack

**Solution**:

1. Verify output name in source stack blueprint
2. Check stack has been deployed successfully
3. Ensure output is exported in Troposphere:

   ```python
   t.add_output(Output("VpcId", Value=Ref(vpc)))
   ```

### Error: Blueprint import failed

**Cause**: Python blueprint has syntax errors or missing dependencies

**Solution**:

1. Check Python syntax in blueprint file
2. Verify all imports are available
3. Test blueprint independently:

   ```bash
   cd myapp.cfn
   python -c "from blueprints.vpc import VPC"
   ```

### Error: Stack rollback

**Cause**: CloudFormation stack creation/update failed

**Solution**:

1. Check CloudFormation console for specific error
2. Review stack events for failed resource
3. Fix blueprint or variables
4. Delete failed stack and retry:

   ```bash
   runway destroy
   runway deploy
   ```

## Best Practices

1. **Use Troposphere for complex templates** - Python is more maintainable than JSON/YAML
2. **Define stack dependencies explicitly** - Use `requires` for proper ordering
3. **Protect production stacks** - Set `protected: true` for critical infrastructure
4. **Use outputs for inter-stack communication** - Don't hardcode resource IDs
5. **Version control blueprints** - Commit all blueprint code
6. **Use environment files** - Separate configuration from code
7. **Tag all stacks** - Include environment, application, and ownership tags
8. **Test blueprints independently** - Validate Python syntax before deploying
9. **Use stack policies** - Protect critical resources from accidental updates
10. **Document variables** - Add descriptions to all blueprint variables

## Example: Complete CFNgin Module

**Directory structure:**

```
infrastructure.cfn/
├── config.yml
├── dev.env
├── prod.env
└── blueprints/
    ├── __init__.py
    ├── vpc.py
    └── app.py
```

**config.yml:**

```yaml
namespace: ${namespace}
cfngin_bucket: cfngin-${namespace}-${region}

stacks:
  - name: vpc
    class_path: blueprints.vpc.VPC
    variables:
      CidrBlock: ${vpc_cidr}
    tags:
      Environment: ${environment}
      
  - name: application
    class_path: blueprints.app.Application
    requires:
      - vpc
    variables:
      VpcId: ${output vpc.VpcId}
      SubnetIds: ${output vpc.PrivateSubnetIds}
      InstanceType: ${instance_type}
    tags:
      Environment: ${environment}
```

**dev.env:**

```
namespace: myapp-dev
environment: dev
vpc_cidr: 10.0.0.0/16
instance_type: t3.micro
```

**prod.env:**

```
namespace: myapp-prod
environment: prod
vpc_cidr: 10.1.0.0/16
instance_type: t3.large
```

**runway.yml:**

```yaml
deployments:
  - modules:
      - path: infrastructure.cfn
    regions:
      - us-east-1
    environments:
      dev: true
      prod: 123456789012
```

This configuration provides a complete, production-ready CFNgin module setup with Runway.
