#!/usr/bin/env python3
"""
Validation script for SAM deploy hook.
This script performs basic validation of the SAM deploy hook functionality.
"""

import argparse
import os
import sys
import tempfile
from pathlib import Path

# Add the hooks directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hooks.aws_sam import SAMDeployHook, SAMDeployError


def create_test_template():
    """Create a minimal test SAM template."""
    template_content = """
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: Test SAM template for validation

Parameters:
  Environment:
    Type: String
    Default: test

Resources:
  TestFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: .
      Handler: index.handler
      Runtime: python3.12
      Environment:
        Variables:
          ENVIRONMENT: !Ref Environment

Outputs:
  TestFunctionArn:
    Description: Test Function ARN
    Value: !GetAtt TestFunction.Arn
"""
    
    # Create temporary template file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(template_content)
        return f.name


def create_test_handler():
    """Create a minimal test Lambda handler."""
    handler_content = """
def handler(event, context):
    return {
        'statusCode': 200,
        'body': 'Hello from test function!'
    }
"""
    
    # Create temporary handler file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(handler_content)
        return f.name


def validate_hook_initialization():
    """Validate hook can be initialized."""
    print("✓ Testing hook initialization...")
    try:
        hook = SAMDeployHook()
        assert hook.cloudformation is None
        print("  ✓ Hook initialized successfully")
        return True
    except Exception as e:
        print(f"  ✗ Hook initialization failed: {e}")
        return False


def validate_sam_cli_check():
    """Validate SAM CLI check functionality."""
    print("✓ Testing SAM CLI check...")
    try:
        hook = SAMDeployHook()
        result = hook._check_sam_cli()
        if result:
            print("  ✓ SAM CLI is available")
        else:
            print("  ⚠ SAM CLI is not available (this is expected if not installed)")
        return True
    except Exception as e:
        print(f"  ✗ SAM CLI check failed: {e}")
        return False


def validate_command_building():
    """Validate SAM command building."""
    print("✓ Testing SAM command building...")
    try:
        hook = SAMDeployHook()
        
        # Test basic command
        cmd = hook._build_sam_command(
            template_file='template.yaml',
            stack_name='test-stack'
        )
        
        expected_parts = ['sam', 'deploy', '--template-file', 'template.yaml', '--stack-name', 'test-stack']
        for part in expected_parts:
            assert part in cmd, f"Missing expected part: {part}"
        
        print("  ✓ Basic command building works")
        
        # Test command with parameters
        cmd = hook._build_sam_command(
            template_file='template.yaml',
            stack_name='test-stack',
            parameters={'Environment': 'test', 'BucketName': 'test-bucket'},
            capabilities=['CAPABILITY_IAM']
        )
        
        assert '--parameter-overrides' in cmd
        assert 'Environment=test' in cmd
        assert 'BucketName=test-bucket' in cmd
        assert '--capabilities' in cmd
        assert 'CAPABILITY_IAM' in cmd
        
        print("  ✓ Command building with parameters works")
        return True
        
    except Exception as e:
        print(f"  ✗ Command building failed: {e}")
        return False


def validate_template_validation():
    """Validate template file validation."""
    print("✓ Testing template validation...")
    try:
        hook = SAMDeployHook()
        
        # Test with non-existent template
        try:
            hook.deploy_sam_template(
                template_file='nonexistent.yaml',
                stack_name='test-stack'
            )
            print("  ✗ Should have failed with non-existent template")
            return False
        except SAMDeployError as e:
            if "not found" in str(e):
                print("  ✓ Correctly detects non-existent template")
            else:
                print(f"  ✗ Unexpected error: {e}")
                return False
        
        return True
        
    except Exception as e:
        print(f"  ✗ Template validation failed: {e}")
        return False


def validate_cfngin_hook():
    """Validate CFNgin hook function."""
    print("✓ Testing CFNgin hook function...")
    try:
        from hooks.aws_sam import cfngin_hook
        
        # Mock context and provider
        class MockProvider:
            region = 'us-east-1'
        
        class MockContext:
            pass
        
        # This should fail because template doesn't exist, but we're testing the hook wrapper
        try:
            cfngin_hook(
                context=MockContext(),
                provider=MockProvider(),
                template_file='nonexistent.yaml',
                stack_name='test-stack'
            )
            print("  ✗ Should have failed with non-existent template")
            return False
        except SAMDeployError:
            print("  ✓ CFNgin hook properly handles errors")
            return True
        
    except Exception as e:
        print(f"  ✗ CFNgin hook validation failed: {e}")
        return False


def main():
    """Main validation function."""
    parser = argparse.ArgumentParser(description='Validate SAM deploy hook')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    args = parser.parse_args()
    
    print("SAM Deploy Hook Validation")
    print("=" * 50)
    
    tests = [
        validate_hook_initialization,
        validate_sam_cli_check,
        validate_command_building,
        validate_template_validation,
        validate_cfngin_hook
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  ✗ Test {test.__name__} crashed: {e}")
            failed += 1
        print()
    
    print("=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All validations passed!")
        return 0
    else:
        print("❌ Some validations failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
