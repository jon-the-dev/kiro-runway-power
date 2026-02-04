#!/usr/bin/env python3
"""
Unit tests for SAM deploy hook.
"""

import json
import os
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, Mock, patch
from pathlib import Path

# Add the hooks directory to the path
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sam_deploy import SAMDeployHook, SAMDeployError, cfngin_hook


class TestSAMDeployHook(unittest.TestCase):
    """Test cases for SAMDeployHook class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.hook = SAMDeployHook()
        self.test_template_content = """
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: Test SAM template

Parameters:
  Environment:
    Type: String
    Default: dev

Resources:
  TestFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: src/
      Handler: app.lambda_handler
      Runtime: python3.12
      Environment:
        Variables:
          ENVIRONMENT: !Ref Environment

Outputs:
  TestFunctionArn:
    Description: Test Function ARN
    Value: !GetAtt TestFunction.Arn
"""
    
    def test_init(self):
        """Test hook initialization."""
        hook = SAMDeployHook()
        self.assertIsNone(hook.cloudformation)
    
    @patch('boto3.client')
    def test_get_cloudformation_client(self, mock_boto_client):
        """Test CloudFormation client creation."""
        mock_client = Mock()
        mock_boto_client.return_value = mock_client
        
        client = self.hook._get_cloudformation_client('us-west-2')
        
        self.assertEqual(client, mock_client)
        mock_boto_client.assert_called_once_with('cloudformation', region_name='us-west-2')
    
    @patch('boto3.client')
    def test_get_cloudformation_client_no_credentials(self, mock_boto_client):
        """Test CloudFormation client creation with no credentials."""
        from botocore.exceptions import NoCredentialsError
        mock_boto_client.side_effect = NoCredentialsError()
        
        with self.assertRaises(SAMDeployError) as context:
            self.hook._get_cloudformation_client()
        
        self.assertIn("AWS credentials not configured", str(context.exception))
    
    @patch('subprocess.run')
    def test_check_sam_cli_success(self, mock_run):
        """Test successful SAM CLI check."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "SAM CLI, version 1.100.0"
        mock_run.return_value = mock_result
        
        result = self.hook._check_sam_cli()
        
        self.assertTrue(result)
        mock_run.assert_called_once_with(
            ['sam', '--version'],
            capture_output=True,
            text=True,
            timeout=10
        )
    
    @patch('subprocess.run')
    def test_check_sam_cli_failure(self, mock_run):
        """Test failed SAM CLI check."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "Command not found"
        mock_run.return_value = mock_result
        
        result = self.hook._check_sam_cli()
        
        self.assertFalse(result)
    
    @patch('subprocess.run')
    def test_check_sam_cli_not_found(self, mock_run):
        """Test SAM CLI not found."""
        mock_run.side_effect = FileNotFoundError()
        
        result = self.hook._check_sam_cli()
        
        self.assertFalse(result)
    
    def test_build_sam_command_basic(self):
        """Test building basic SAM command."""
        cmd = self.hook._build_sam_command(
            template_file='template.yaml',
            stack_name='test-stack'
        )
        
        expected = [
            'sam', 'deploy',
            '--template-file', 'template.yaml',
            '--stack-name', 'test-stack',
            '--region', 'us-east-1',
            '--capabilities', 'CAPABILITY_IAM', 'CAPABILITY_NAMED_IAM',
            '--no-confirm-changeset',
            '--resolve-s3',
            '--resolve-image-repos'
        ]
        
        self.assertEqual(cmd, expected)
    
    def test_build_sam_command_full(self):
        """Test building full SAM command with all options."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write('[default]\n')
            config_file = f.name
        
        try:
            cmd = self.hook._build_sam_command(
                template_file='template.yaml',
                stack_name='test-stack',
                config_file=config_file,
                env='dev',
                parameters={'Environment': 'dev', 'BucketName': 'test-bucket'},
                capabilities=['CAPABILITY_IAM'],
                region='us-west-2',
                guided=True,
                confirm_changeset=False,
                resolve_s3=False
            )
            
            expected = [
                'sam', 'deploy',
                '--template-file', 'template.yaml',
                '--stack-name', 'test-stack',
                '--region', 'us-west-2',
                '--config-file', config_file,
                '--config-env', 'dev',
                '--parameter-overrides', 'Environment=dev', 'BucketName=test-bucket',
                '--capabilities', 'CAPABILITY_IAM',
                '--guided',
                '--no-confirm-changeset',
                '--resolve-image-repos'
            ]
            
            self.assertEqual(cmd, expected)
        finally:
            os.unlink(config_file)
    
    @patch('subprocess.run')
    @patch.object(SAMDeployHook, '_check_sam_cli')
    def test_deploy_sam_template_success(self, mock_check_sam, mock_run):
        """Test successful SAM template deployment."""
        # Setup mocks
        mock_check_sam.return_value = True
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Successfully deployed stack test-stack"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        # Create temporary template file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(self.test_template_content)
            template_file = f.name
        
        try:
            result = self.hook.deploy_sam_template(
                template_file=template_file,
                stack_name='test-stack',
                wait=False
            )
            
            self.assertTrue(result['success'])
            self.assertEqual(result['stack_name'], 'test-stack')
            self.assertEqual(result['region'], 'us-east-1')
            self.assertIn("Successfully deployed", result['command_output'])
        finally:
            os.unlink(template_file)
    
    @patch('subprocess.run')
    @patch.object(SAMDeployHook, '_check_sam_cli')
    def test_deploy_sam_template_failure(self, mock_check_sam, mock_run):
        """Test failed SAM template deployment."""
        # Setup mocks
        mock_check_sam.return_value = True
        
        # Mock successful build, failed deploy
        build_result = Mock()
        build_result.returncode = 0
        build_result.stdout = "Build completed successfully"
        build_result.stderr = ""
        
        deploy_result = Mock()
        deploy_result.returncode = 1
        deploy_result.stdout = "Deployment output"
        deploy_result.stderr = "Deployment failed"
        
        mock_run.side_effect = [build_result, deploy_result]
        
        # Create temporary template file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(self.test_template_content)
            template_file = f.name
        
        try:
            with self.assertRaises(SAMDeployError) as context:
                self.hook.deploy_sam_template(
                    template_file=template_file,
                    stack_name='test-stack'
                )
            
            self.assertIn("SAM deploy failed", str(context.exception))
        finally:
            os.unlink(template_file)
    
    @patch('subprocess.run')
    @patch.object(SAMDeployHook, '_check_sam_cli')
    def test_deploy_sam_template_no_changes(self, mock_check_sam, mock_run):
        """Test deployment when there are no changes to deploy (should be treated as success)."""
        # Setup mocks
        mock_check_sam.return_value = True
        
        # Mock successful build, no changes to deploy
        build_result = Mock()
        build_result.returncode = 0
        build_result.stdout = "Build completed successfully"
        build_result.stderr = ""
        
        deploy_result = Mock()
        deploy_result.returncode = 1  # SAM CLI returns 1 for no changes
        deploy_result.stdout = "No changes to deploy. Stack test-stack is up to date"
        deploy_result.stderr = ""
        
        mock_run.side_effect = [build_result, deploy_result]
        
        # Create temporary template file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(self.test_template_content)
            template_file = f.name
        
        try:
            # Should not raise an exception
            result = self.hook.deploy_sam_template(
                template_file=template_file,
                stack_name='test-stack'
            )
            
            # Verify result
            self.assertTrue(result['success'])
            self.assertEqual(result['stack_name'], 'test-stack')
            self.assertIn("No changes to deploy", result['command_output'])
            
        finally:
            os.unlink(template_file)
    
    @patch.object(SAMDeployHook, '_check_sam_cli')
    def test_deploy_sam_template_no_cli(self, mock_check_sam):
        """Test deployment when SAM CLI is not available."""
        mock_check_sam.return_value = False
        
        with self.assertRaises(SAMDeployError) as context:
            self.hook.deploy_sam_template(
                template_file='template.yaml',
                stack_name='test-stack'
            )
        
        self.assertIn("SAM CLI is not installed", str(context.exception))
    
    def test_deploy_sam_template_no_template(self):
        """Test deployment with non-existent template file."""
        with self.assertRaises(SAMDeployError) as context:
            self.hook.deploy_sam_template(
                template_file='nonexistent.yaml',
                stack_name='test-stack'
            )
        
        self.assertIn("SAM template file not found", str(context.exception))
    
    @patch('subprocess.run')
    @patch.object(SAMDeployHook, '_check_sam_cli')
    def test_deploy_sam_template_timeout(self, mock_check_sam, mock_run):
        """Test deployment timeout."""
        mock_check_sam.return_value = True
        mock_run.side_effect = subprocess.TimeoutExpired(['sam', 'deploy'], 10)
        
        # Create temporary template file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(self.test_template_content)
            template_file = f.name
        
        try:
            with self.assertRaises(SAMDeployError) as context:
                self.hook.deploy_sam_template(
                    template_file=template_file,
                    stack_name='test-stack',
                    timeout=10
                )
            
            self.assertIn("timed out", str(context.exception))
        finally:
            os.unlink(template_file)
    
    @patch('subprocess.run')
    @patch.object(SAMDeployHook, '_check_sam_cli')
    @patch.object(SAMDeployHook, '_get_cloudformation_client')
    def test_deploy_sam_template_with_wait(self, mock_get_cf_client, mock_check_sam, mock_run):
        """Test deployment with wait for completion."""
        # Setup mocks
        mock_check_sam.return_value = True
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Successfully deployed stack test-stack"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        mock_cf_client = Mock()
        mock_cf_client.describe_stacks.return_value = {
            'Stacks': [{
                'StackId': 'arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack/12345',
                'StackName': 'test-stack',
                'StackStatus': 'CREATE_COMPLETE',
                'Outputs': [
                    {'OutputKey': 'TestOutput', 'OutputValue': 'test-value'}
                ]
            }]
        }
        mock_get_cf_client.return_value = mock_cf_client
        
        # Create temporary template file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(self.test_template_content)
            template_file = f.name
        
        try:
            result = self.hook.deploy_sam_template(
                template_file=template_file,
                stack_name='test-stack',
                wait=True
            )
            
            self.assertTrue(result['success'])
            self.assertEqual(result['stack_info']['StackStatus'], 'CREATE_COMPLETE')
            self.assertEqual(result['stack_info']['Outputs']['TestOutput'], 'test-value')
        finally:
            os.unlink(template_file)

    @patch('sam_deploy.boto3.client')
    def test_check_and_handle_failed_stack_rollback_complete(self, mock_boto3_client):
        """Test handling of ROLLBACK_COMPLETE stack."""
        # Mock CloudFormation client
        mock_cf_client = Mock()
        mock_boto3_client.return_value = mock_cf_client
        
        # Mock describe_stacks response for ROLLBACK_COMPLETE
        mock_cf_client.describe_stacks.return_value = {
            'Stacks': [{
                'StackName': 'test-stack',
                'StackStatus': 'ROLLBACK_COMPLETE'
            }]
        }
        
        # Mock waiter
        mock_waiter = Mock()
        mock_cf_client.get_waiter.return_value = mock_waiter
        
        result = self.hook._check_and_handle_failed_stack('test-stack', 'us-east-1')
        
        # Verify stack was deleted
        mock_cf_client.delete_stack.assert_called_once_with(StackName='test-stack')
        mock_cf_client.get_waiter.assert_called_once_with('stack_delete_complete')
        mock_waiter.wait.assert_called_once()
        self.assertTrue(result)
    
    @patch('sam_deploy.boto3.client')
    def test_check_and_handle_failed_stack_create_failed(self, mock_boto3_client):
        """Test handling of CREATE_FAILED stack."""
        # Mock CloudFormation client
        mock_cf_client = Mock()
        mock_boto3_client.return_value = mock_cf_client
        
        # Mock describe_stacks response for CREATE_FAILED
        mock_cf_client.describe_stacks.return_value = {
            'Stacks': [{
                'StackName': 'test-stack',
                'StackStatus': 'CREATE_FAILED'
            }]
        }
        
        # Mock waiter
        mock_waiter = Mock()
        mock_cf_client.get_waiter.return_value = mock_waiter
        
        result = self.hook._check_and_handle_failed_stack('test-stack', 'us-east-1')
        
        # Verify stack was deleted
        mock_cf_client.delete_stack.assert_called_once_with(StackName='test-stack')
        self.assertTrue(result)
    
    @patch('sam_deploy.boto3.client')
    def test_check_and_handle_failed_stack_healthy_state(self, mock_boto3_client):
        """Test handling of healthy stack state."""
        # Mock CloudFormation client
        mock_cf_client = Mock()
        mock_boto3_client.return_value = mock_cf_client
        
        # Mock describe_stacks response for healthy state
        mock_cf_client.describe_stacks.return_value = {
            'Stacks': [{
                'StackName': 'test-stack',
                'StackStatus': 'CREATE_COMPLETE'
            }]
        }
        
        result = self.hook._check_and_handle_failed_stack('test-stack', 'us-east-1')
        
        # Verify stack was NOT deleted
        mock_cf_client.delete_stack.assert_not_called()
        self.assertFalse(result)
    
    @patch('sam_deploy.boto3.client')
    def test_check_and_handle_failed_stack_does_not_exist(self, mock_boto3_client):
        """Test handling of non-existent stack."""
        # Mock CloudFormation client
        mock_cf_client = Mock()
        mock_boto3_client.return_value = mock_cf_client
        
        # Mock ClientError for non-existent stack
        from botocore.exceptions import ClientError
        error_response = {
            'Error': {
                'Code': 'ValidationError',
                'Message': 'Stack with id test-stack does not exist'
            }
        }
        mock_cf_client.describe_stacks.side_effect = ClientError(error_response, 'DescribeStacks')
        
        result = self.hook._check_and_handle_failed_stack('test-stack', 'us-east-1')
        
        # Verify no deletion attempted
        mock_cf_client.delete_stack.assert_not_called()
        self.assertTrue(result)
    
    @patch('sam_deploy.boto3.client')
    def test_check_and_handle_failed_stack_deletion_timeout(self, mock_boto3_client):
        """Test handling of stack deletion timeout."""
        # Mock CloudFormation client
        mock_cf_client = Mock()
        mock_boto3_client.return_value = mock_cf_client
        
        # Mock describe_stacks response for failed state
        mock_cf_client.describe_stacks.return_value = {
            'Stacks': [{
                'StackName': 'test-stack',
                'StackStatus': 'ROLLBACK_COMPLETE'
            }]
        }
        
        # Mock waiter that raises exception
        mock_waiter = Mock()
        mock_waiter.wait.side_effect = Exception("Waiter timeout")
        mock_cf_client.get_waiter.return_value = mock_waiter
        
        with self.assertRaises(SAMDeployError) as context:
            self.hook._check_and_handle_failed_stack('test-stack', 'us-east-1')
        
        self.assertIn("Stack deletion failed", str(context.exception))
    
    @patch('sam_deploy.boto3.client')
    def test_check_and_handle_failed_stack_all_failed_states(self, mock_boto3_client):
        """Test all failed states are handled correctly."""
        # Mock CloudFormation client
        mock_cf_client = Mock()
        mock_boto3_client.return_value = mock_cf_client
        
        # Mock waiter
        mock_waiter = Mock()
        mock_cf_client.get_waiter.return_value = mock_waiter
        
        failed_states = [
            'ROLLBACK_COMPLETE',
            'ROLLBACK_FAILED', 
            'CREATE_FAILED',
            'DELETE_FAILED',
            'UPDATE_ROLLBACK_FAILED'
        ]
        
        for state in failed_states:
            with self.subTest(state=state):
                # Reset mock
                mock_cf_client.reset_mock()
                mock_waiter.reset_mock()
                
                # Mock describe_stacks response
                mock_cf_client.describe_stacks.return_value = {
                    'Stacks': [{
                        'StackName': 'test-stack',
                        'StackStatus': state
                    }]
                }
                
                result = self.hook._check_and_handle_failed_stack('test-stack', 'us-east-1')
                
                # Verify stack was deleted for all failed states
                mock_cf_client.delete_stack.assert_called_once_with(StackName='test-stack')
                self.assertTrue(result)

    @patch('subprocess.run')
    @patch.object(SAMDeployHook, '_check_sam_cli')
    @patch.object(SAMDeployHook, '_check_and_handle_failed_stack')
    def test_deploy_sam_template_with_failed_stack_check(self, mock_check_failed, mock_check_sam, mock_run):
        """Test deployment with failed stack check integration."""
        # Setup mocks
        mock_check_sam.return_value = True
        mock_check_failed.return_value = True  # Stack was deleted
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Successfully deployed stack test-stack"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        # Create temporary template file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(self.test_template_content)
            template_file = f.name
        
        try:
            result = self.hook.deploy_sam_template(
                template_file=template_file,
                stack_name='test-stack',
                region='us-west-2'
            )
            
            # Verify failed stack check was called
            mock_check_failed.assert_called_once_with('test-stack', 'us-west-2')
            
            self.assertTrue(result['success'])
            self.assertEqual(result['stack_name'], 'test-stack')
            self.assertEqual(result['region'], 'us-west-2')
        finally:
            os.unlink(template_file)

    @patch('sam_deploy.boto3.client')
    def test_delete_sam_stack_success(self, mock_boto3_client):
        """Test successful stack deletion."""
        # Mock CloudFormation client
        mock_cf_client = Mock()
        mock_boto3_client.return_value = mock_cf_client
        
        # Mock describe_stacks response
        mock_cf_client.describe_stacks.return_value = {
            'Stacks': [{
                'StackName': 'test-stack',
                'StackStatus': 'CREATE_COMPLETE'
            }]
        }
        
        # Mock waiter
        mock_waiter = Mock()
        mock_cf_client.get_waiter.return_value = mock_waiter
        
        result = self.hook.delete_sam_stack('test-stack', 'us-east-1')
        
        # Verify deletion was called
        mock_cf_client.delete_stack.assert_called_once_with(StackName='test-stack')
        mock_cf_client.get_waiter.assert_called_once_with('stack_delete_complete')
        mock_waiter.wait.assert_called_once()
        
        self.assertTrue(result['success'])
        self.assertEqual(result['stack_name'], 'test-stack')
        self.assertEqual(result['region'], 'us-east-1')
    
    @patch('sam_deploy.boto3.client')
    def test_delete_sam_stack_does_not_exist(self, mock_boto3_client):
        """Test deletion of non-existent stack."""
        # Mock CloudFormation client
        mock_cf_client = Mock()
        mock_boto3_client.return_value = mock_cf_client
        
        # Mock ClientError for non-existent stack
        from botocore.exceptions import ClientError
        error_response = {
            'Error': {
                'Code': 'ValidationError',
                'Message': 'Stack with id test-stack does not exist'
            }
        }
        mock_cf_client.describe_stacks.side_effect = ClientError(error_response, 'DescribeStacks')
        
        result = self.hook.delete_sam_stack('test-stack', 'us-east-1')
        
        # Verify no deletion attempted
        mock_cf_client.delete_stack.assert_not_called()
        
        self.assertTrue(result['success'])
        self.assertEqual(result['message'], 'Stack does not exist')
    
    @patch('sam_deploy.boto3.client')
    def test_delete_sam_stack_already_deleted(self, mock_boto3_client):
        """Test deletion of already deleted stack."""
        # Mock CloudFormation client
        mock_cf_client = Mock()
        mock_boto3_client.return_value = mock_cf_client
        
        # Mock describe_stacks response for already deleted stack
        mock_cf_client.describe_stacks.return_value = {
            'Stacks': [{
                'StackName': 'test-stack',
                'StackStatus': 'DELETE_COMPLETE'
            }]
        }
        
        result = self.hook.delete_sam_stack('test-stack', 'us-east-1')
        
        # Verify no deletion attempted
        mock_cf_client.delete_stack.assert_not_called()
        
        self.assertTrue(result['success'])
        self.assertEqual(result['message'], 'Stack already deleted')
    
    @patch('sam_deploy.boto3.client')
    def test_delete_sam_stack_deletion_in_progress(self, mock_boto3_client):
        """Test deletion when stack is already being deleted."""
        # Mock CloudFormation client
        mock_cf_client = Mock()
        mock_boto3_client.return_value = mock_cf_client
        
        # Mock describe_stacks response for deletion in progress
        mock_cf_client.describe_stacks.return_value = {
            'Stacks': [{
                'StackName': 'test-stack',
                'StackStatus': 'DELETE_IN_PROGRESS'
            }]
        }
        
        # Mock waiter
        mock_waiter = Mock()
        mock_cf_client.get_waiter.return_value = mock_waiter
        
        result = self.hook.delete_sam_stack('test-stack', 'us-east-1')
        
        # Verify no new deletion initiated but waiter was called
        mock_cf_client.delete_stack.assert_not_called()
        mock_waiter.wait.assert_called_once()
        
        self.assertTrue(result['success'])
        self.assertEqual(result['message'], 'Stack deletion already in progress')
    
    @patch('sam_deploy.boto3.client')
    def test_delete_sam_stack_with_retain_resources(self, mock_boto3_client):
        """Test stack deletion with resource retention."""
        # Mock CloudFormation client
        mock_cf_client = Mock()
        mock_boto3_client.return_value = mock_cf_client
        
        # Mock describe_stacks response
        mock_cf_client.describe_stacks.return_value = {
            'Stacks': [{
                'StackName': 'test-stack',
                'StackStatus': 'CREATE_COMPLETE'
            }]
        }
        
        # Mock waiter
        mock_waiter = Mock()
        mock_cf_client.get_waiter.return_value = mock_waiter
        
        retain_resources = ['MyS3Bucket', 'MyDynamoTable']
        result = self.hook.delete_sam_stack(
            'test-stack', 
            'us-east-1',
            retain_resources=retain_resources
        )
        
        # Verify deletion was called with retain resources
        mock_cf_client.delete_stack.assert_called_once_with(
            StackName='test-stack',
            RetainResources=retain_resources
        )
        
        self.assertTrue(result['success'])
    
    @patch('sam_deploy.boto3.client')
    def test_delete_sam_stack_no_wait(self, mock_boto3_client):
        """Test stack deletion without waiting."""
        # Mock CloudFormation client
        mock_cf_client = Mock()
        mock_boto3_client.return_value = mock_cf_client
        
        # Mock describe_stacks response
        mock_cf_client.describe_stacks.return_value = {
            'Stacks': [{
                'StackName': 'test-stack',
                'StackStatus': 'CREATE_COMPLETE'
            }]
        }
        
        result = self.hook.delete_sam_stack('test-stack', 'us-east-1', wait=False)
        
        # Verify deletion was called but no waiter
        mock_cf_client.delete_stack.assert_called_once_with(StackName='test-stack')
        mock_cf_client.get_waiter.assert_not_called()
        
        self.assertTrue(result['success'])
        self.assertEqual(result['message'], 'Stack deletion initiated')
    
    @patch('sam_deploy.boto3.client')
    def test_delete_sam_stack_waiter_timeout(self, mock_boto3_client):
        """Test stack deletion with waiter timeout."""
        # Mock CloudFormation client
        mock_cf_client = Mock()
        mock_boto3_client.return_value = mock_cf_client
        
        # Mock describe_stacks response
        mock_cf_client.describe_stacks.return_value = {
            'Stacks': [{
                'StackName': 'test-stack',
                'StackStatus': 'CREATE_COMPLETE'
            }]
        }
        
        # Mock waiter that raises exception
        mock_waiter = Mock()
        mock_waiter.wait.side_effect = Exception("Waiter timeout")
        mock_cf_client.get_waiter.return_value = mock_waiter
        
        with self.assertRaises(SAMDeployError) as context:
            self.hook.delete_sam_stack('test-stack', 'us-east-1')
        
        self.assertIn("Stack deletion wait failed", str(context.exception))


class TestCFNginHook(unittest.TestCase):
    """Test cases for CFNgin hook function."""
    
    @patch.object(SAMDeployHook, 'deploy_sam_template')
    def test_cfngin_hook_success(self, mock_deploy):
        """Test successful CFNgin hook execution."""
        mock_deploy.return_value = {
            'success': True,
            'stack_name': 'test-stack',
            'region': 'us-east-1'
        }
        
        # Mock context and provider
        context = Mock()
        provider = Mock()
        provider.region = 'us-east-1'
        
        result = cfngin_hook(
            context=context,
            provider=provider,
            template_file='template.yaml',
            stack_name='test-stack'
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['stack_name'], 'test-stack')
        mock_deploy.assert_called_once()
    
    @patch.object(SAMDeployHook, 'deploy_sam_template')
    def test_cfngin_hook_failure(self, mock_deploy):
        """Test failed CFNgin hook execution."""
        mock_deploy.side_effect = SAMDeployError("Deployment failed")
        
        # Mock context and provider
        context = Mock()
        provider = Mock()
        provider.region = 'us-east-1'
        
        with self.assertRaises(SAMDeployError):
            cfngin_hook(
                context=context,
                provider=provider,
                template_file='template.yaml',
                stack_name='test-stack'
            )
    
    @patch.object(SAMDeployHook, 'deploy_sam_template')
    def test_cfngin_hook_with_parameters(self, mock_deploy):
        """Test CFNgin hook with all parameters."""
        mock_deploy.return_value = {
            'success': True,
            'stack_name': 'test-stack',
            'region': 'us-west-2'
        }
        
        # Mock context and provider
        context = Mock()
        provider = Mock()
        provider.region = 'us-east-1'
        
        result = cfngin_hook(
            context=context,
            provider=provider,
            template_file='template.yaml',
            stack_name='test-stack',
            config_file='samconfig.toml',
            env='dev',
            parameters={'Environment': 'dev'},
            capabilities=['CAPABILITY_IAM'],
            region='us-west-2',
            wait=True,
            timeout=1200,
            working_directory='/tmp'
        )
        
        self.assertTrue(result['success'])
        mock_deploy.assert_called_once_with(
            template_file='template.yaml',
            stack_name='test-stack',
            config_file='samconfig.toml',
            env='dev',
            parameters={'Environment': 'dev'},
            param_file=None,
            capabilities=['CAPABILITY_IAM'],
            region='us-west-2',
            wait=True,
            timeout=1200,
            working_directory='/tmp',
            skip_build=False,
            resolve_image_repos=True
        )


class TestCFNginDeleteHook(unittest.TestCase):
    """Test cases for CFNgin delete hook function."""
    
    @patch.object(SAMDeployHook, 'delete_sam_stack')
    def test_cfngin_delete_hook_success(self, mock_delete):
        """Test successful CFNgin delete hook execution."""
        mock_delete.return_value = {
            'success': True,
            'stack_name': 'test-stack',
            'region': 'us-east-1',
            'message': 'Stack deleted successfully'
        }
        
        # Mock context and provider
        context = Mock()
        provider = Mock()
        provider.region = 'us-east-1'
        
        from sam_deploy import cfngin_delete_hook
        result = cfngin_delete_hook(
            context=context,
            provider=provider,
            stack_name='test-stack'
        )
        
        self.assertTrue(result['success'])
        mock_delete.assert_called_once_with(
            stack_name='test-stack',
            region='us-east-1',
            wait=True,
            timeout=1800,
            retain_resources=None
        )
    
    @patch.object(SAMDeployHook, 'delete_sam_stack')
    def test_cfngin_delete_hook_with_options(self, mock_delete):
        """Test CFNgin delete hook with all options."""
        mock_delete.return_value = {
            'success': True,
            'stack_name': 'test-stack',
            'region': 'us-west-2',
            'message': 'Stack deletion initiated'
        }
        
        # Mock context and provider
        context = Mock()
        provider = Mock()
        provider.region = 'us-east-1'  # Should be overridden
        
        from sam_deploy import cfngin_delete_hook
        result = cfngin_delete_hook(
            context=context,
            provider=provider,
            stack_name='test-stack',
            region='us-west-2',
            wait=False,
            timeout=900,
            retain_resources=['MyBucket', 'MyTable']
        )
        
        self.assertTrue(result['success'])
        mock_delete.assert_called_once_with(
            stack_name='test-stack',
            region='us-west-2',
            wait=False,
            timeout=900,
            retain_resources=['MyBucket', 'MyTable']
        )
    
    @patch.object(SAMDeployHook, 'delete_sam_stack')
    def test_cfngin_delete_hook_failure(self, mock_delete):
        """Test CFNgin delete hook failure."""
        mock_delete.side_effect = SAMDeployError("Deletion failed")
        
        # Mock context and provider
        context = Mock()
        provider = Mock()
        provider.region = 'us-east-1'
        
        from sam_deploy import cfngin_delete_hook
        with self.assertRaises(SAMDeployError):
            cfngin_delete_hook(
                context=context,
                provider=provider,
                stack_name='test-stack'
            )


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)
