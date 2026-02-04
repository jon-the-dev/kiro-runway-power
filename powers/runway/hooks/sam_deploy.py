#!/usr/bin/env python3
"""
CFNgin hook for deploying AWS SAM templates.

This hook can be used as a pre_deploy or post_deploy hook to deploy SAM applications
using the AWS SAM CLI. It supports custom configuration files and environment-specific
parameters.

Usage as CFNgin Hook:
    pre_hooks:
      - path: hooks.sam_deploy.cfngin_hook
        required: true
        args:
          template_file: template.yaml
          stack_name: my-sam-stack
          config_file: samconfig.toml
          env: dev
          parameters:
            Environment: dev
            BucketName: my-bucket
          param_file: parameters.json
          capabilities:
            - CAPABILITY_IAM
          wait: true
          skip_build: false  # Set to true to skip sam build step

Usage as CLI:
    python hooks/sam_deploy.py --template template.yaml --stack-name my-stack --env dev
    python hooks/sam_deploy.py --template template.yaml --stack-name my-stack --param-file parameters.json
    python hooks/sam_deploy.py --template template.yaml --stack-name my-stack --skip-build
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SAMDeployError(Exception):
    """Custom exception for SAM deployment errors."""
    pass


class SAMDeployHook:
    """Hook for deploying AWS SAM templates."""
    
    def __init__(self):
        """Initialize the SAM deploy hook."""
        self.cloudformation = None
        
    def _get_cloudformation_client(self, region: str = 'us-east-1') -> boto3.client:
        """Get CloudFormation client."""
        if not self.cloudformation:
            try:
                self.cloudformation = boto3.client('cloudformation', region_name=region)
            except NoCredentialsError as e:
                raise SAMDeployError(f"AWS credentials not configured: {e}")
        return self.cloudformation
    
    def _check_and_handle_failed_stack(self, stack_name: str, region: str = 'us-east-1') -> bool:
        """
        Check if stack is in a failed state and delete it if necessary.
        
        Args:
            stack_name: CloudFormation stack name
            region: AWS region
            
        Returns:
            True if stack was deleted or doesn't exist, False if stack exists and is healthy
        """
        cf_client = self._get_cloudformation_client(region)
        
        try:
            response = cf_client.describe_stacks(StackName=stack_name)
            if not response['Stacks']:
                logger.info(f"Stack {stack_name} does not exist")
                return True
                
            stack = response['Stacks'][0]
            stack_status = stack.get('StackStatus', '')
            
            # Define failed states that require deletion
            failed_states = {
                'ROLLBACK_COMPLETE',
                'ROLLBACK_FAILED', 
                'CREATE_FAILED',
                'DELETE_FAILED',
                'UPDATE_ROLLBACK_FAILED'
            }
            
            if stack_status in failed_states:
                logger.warning(f"Stack {stack_name} is in failed state: {stack_status}")
                
                # Check if we're in CI mode
                is_ci = os.getenv('CI') is not None
                
                if is_ci:
                    logger.info(f"CI mode detected - automatically deleting failed stack {stack_name}")
                    should_delete = True
                else:
                    # Ask user for confirmation
                    print(f"\n⚠️  Stack '{stack_name}' is in failed state: {stack_status}")
                    print("This stack needs to be deleted before redeployment can proceed.")
                    
                    while True:
                        response = input("Do you want to delete this stack and continue? (y/n): ").lower().strip()
                        if response in ['y', 'yes']:
                            should_delete = True
                            break
                        elif response in ['n', 'no']:
                            should_delete = False
                            break
                        else:
                            print("Please enter 'y' for yes or 'n' for no.")
                
                if not should_delete:
                    logger.info("User chose not to delete the failed stack. Deployment aborted.")
                    raise SAMDeployError(f"Stack {stack_name} is in failed state {stack_status} and user declined deletion")
                
                logger.info(f"Deleting failed stack {stack_name} before redeployment")
                
                # Delete the failed stack
                cf_client.delete_stack(StackName=stack_name)
                
                # Wait for deletion to complete
                logger.info(f"Waiting for stack {stack_name} deletion to complete...")
                waiter = cf_client.get_waiter('stack_delete_complete')
                
                try:
                    waiter.wait(
                        StackName=stack_name,
                        WaiterConfig={
                            'Delay': 30,
                            'MaxAttempts': 60  # 30 minutes max
                        }
                    )
                    logger.info(f"Stack {stack_name} deleted successfully")
                    return True
                    
                except Exception as e:
                    logger.error(f"Failed to wait for stack deletion: {e}")
                    raise SAMDeployError(f"Stack deletion failed: {e}")
            
            else:
                logger.info(f"Stack {stack_name} is in healthy state: {stack_status}")
                return False
                
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            
            if error_code == 'ValidationError' and 'does not exist' in str(e):
                logger.info(f"Stack {stack_name} does not exist")
                return True
            else:
                logger.error(f"Error checking stack status: {e}")
                raise SAMDeployError(f"Failed to check stack status: {e}")
        
        except Exception as e:
            logger.error(f"Unexpected error checking stack status: {e}")
            raise SAMDeployError(f"Failed to check stack status: {e}")
    
    def delete_sam_stack(
        self,
        stack_name: str,
        region: str = 'us-east-1',
        wait: bool = True,
        timeout: int = 1800,
        retain_resources: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Delete a SAM/CloudFormation stack.
        
        Args:
            stack_name: CloudFormation stack name
            region: AWS region
            wait: Whether to wait for deletion completion
            timeout: Timeout in seconds for waiting
            retain_resources: List of logical resource IDs to retain during deletion
            
        Returns:
            Dictionary with deletion results
        """
        logger.info(f"Starting stack deletion for: {stack_name}")
        
        cf_client = self._get_cloudformation_client(region)
        
        try:
            # Check if stack exists first
            try:
                response = cf_client.describe_stacks(StackName=stack_name)
                if not response['Stacks']:
                    logger.info(f"Stack {stack_name} does not exist")
                    return {
                        'success': True,
                        'stack_name': stack_name,
                        'region': region,
                        'message': 'Stack does not exist'
                    }
                
                stack = response['Stacks'][0]
                current_status = stack.get('StackStatus', '')
                
                # Check if stack is already being deleted
                if current_status in ['DELETE_IN_PROGRESS']:
                    logger.info(f"Stack {stack_name} is already being deleted")
                    if wait:
                        logger.info(f"Waiting for existing deletion to complete...")
                        waiter = cf_client.get_waiter('stack_delete_complete')
                        waiter.wait(
                            StackName=stack_name,
                            WaiterConfig={
                                'Delay': 30,
                                'MaxAttempts': timeout // 30
                            }
                        )
                    return {
                        'success': True,
                        'stack_name': stack_name,
                        'region': region,
                        'message': 'Stack deletion already in progress'
                    }
                
                # Check if stack is in a state that can't be deleted
                if current_status in ['DELETE_COMPLETE']:
                    logger.info(f"Stack {stack_name} is already deleted")
                    return {
                        'success': True,
                        'stack_name': stack_name,
                        'region': region,
                        'message': 'Stack already deleted'
                    }
                
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')
                if error_code == 'ValidationError' and 'does not exist' in str(e):
                    logger.info(f"Stack {stack_name} does not exist")
                    return {
                        'success': True,
                        'stack_name': stack_name,
                        'region': region,
                        'message': 'Stack does not exist'
                    }
                else:
                    raise
            
            # Prepare delete parameters
            delete_params = {'StackName': stack_name}
            if retain_resources:
                delete_params['RetainResources'] = retain_resources
                logger.info(f"Retaining resources: {retain_resources}")
            
            # Delete the stack
            logger.info(f"Deleting stack {stack_name}...")
            cf_client.delete_stack(**delete_params)
            
            # Wait for deletion if requested
            if wait:
                logger.info(f"Waiting for stack {stack_name} deletion to complete...")
                waiter = cf_client.get_waiter('stack_delete_complete')
                
                try:
                    waiter.wait(
                        StackName=stack_name,
                        WaiterConfig={
                            'Delay': 30,
                            'MaxAttempts': timeout // 30
                        }
                    )
                    logger.info(f"Stack {stack_name} deleted successfully")
                    
                except Exception as e:
                    logger.error(f"Failed to wait for stack deletion: {e}")
                    raise SAMDeployError(f"Stack deletion wait failed: {e}")
            
            return {
                'success': True,
                'stack_name': stack_name,
                'region': region,
                'message': 'Stack deletion initiated' if not wait else 'Stack deleted successfully'
            }
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            error_msg = f"Failed to delete stack {stack_name}: {e}"
            logger.error(error_msg)
            raise SAMDeployError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error deleting stack {stack_name}: {e}"
            logger.error(error_msg)
            raise SAMDeployError(error_msg)
    
    def _check_sam_cli(self) -> bool:
        """Check if SAM CLI is installed and available."""
        try:
            result = subprocess.run(
                ['sam', '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                logger.info(f"SAM CLI version: {result.stdout.strip()}")
                return True
            else:
                logger.error(f"SAM CLI check failed: {result.stderr}")
                return False
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.error(f"SAM CLI not found or timeout: {e}")
            return False
    
    def _build_sam_command(
        self,
        template_file: str,
        stack_name: str,
        config_file: Optional[str] = None,
        env: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        capabilities: Optional[List[str]] = None,
        region: str = 'us-east-1',
        guided: bool = False,
        confirm_changeset: bool = False,
        resolve_s3: bool = True,
        resolve_image_repos: bool = True
    ) -> List[str]:
        """Build the SAM deploy command."""
        cmd = [
            'sam', 'deploy',
            '--template-file', template_file,
            '--stack-name', stack_name,
            '--region', region
        ]
        
        # Add config file if specified
        if config_file and os.path.exists(config_file):
            cmd.extend(['--config-file', config_file])
        
        # Add environment if specified
        if env:
            cmd.extend(['--config-env', env])
        
        # Add parameters
        if parameters:
            param_overrides = []
            for key, value in parameters.items():
                param_overrides.append(f"{key}={value}")
            if param_overrides:
                cmd.extend(['--parameter-overrides'] + param_overrides)
        
        # Add capabilities
        if capabilities:
            cmd.extend(['--capabilities'] + capabilities)
        else:
            # Default capabilities for most SAM applications
            cmd.extend(['--capabilities', 'CAPABILITY_IAM', 'CAPABILITY_NAMED_IAM'])
        
        # Add other options
        if guided:
            cmd.append('--guided')
        
        if not confirm_changeset:
            cmd.append('--no-confirm-changeset')
        
        if resolve_s3:
            cmd.append('--resolve-s3')
            
        if resolve_image_repos:
            cmd.append('--resolve-image-repos')
        
        return cmd
    
    def deploy_sam_template(
        self,
        template_file: str,
        stack_name: str,
        config_file: Optional[str] = None,
        env: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        param_file: Optional[str] = None,
        capabilities: Optional[List[str]] = None,
        region: str = 'us-east-1',
        wait: bool = True,
        timeout: int = 1800,
        working_directory: Optional[str] = None,
        skip_build: bool = False,
        resolve_image_repos: bool = True
    ) -> Dict[str, Any]:
        """
        Deploy SAM template.
        
        Args:
            template_file: Path to SAM template file
            stack_name: CloudFormation stack name
            config_file: Path to SAM config file (samconfig.toml)
            env: Environment name for config
            parameters: Dictionary of parameter overrides
            param_file: Path to JSON file containing parameter key-value pairs
            capabilities: List of IAM capabilities
            region: AWS region
            wait: Whether to wait for deployment completion
            timeout: Timeout in seconds
            working_directory: Directory to run SAM command from
            skip_build: Skip the sam build step (default: False)
            
        Returns:
            Dictionary with deployment results
        """
        logger.info(f"Starting SAM deployment for stack: {stack_name}")
        
        # Load parameters from JSON file if specified
        final_parameters = {}
        if param_file:
            param_file_path = Path(param_file)
            if working_directory:
                param_file_path = Path(working_directory) / param_file_path
            
            if param_file_path.exists():
                try:
                    with open(param_file_path, 'r') as f:
                        file_parameters = json.load(f)
                    
                    if not isinstance(file_parameters, dict):
                        raise SAMDeployError(f"Parameter file {param_file_path} must contain a JSON object with key-value pairs")
                    
                    final_parameters.update(file_parameters)
                    logger.info(f"Loaded {len(file_parameters)} parameters from {param_file_path}")
                    
                except json.JSONDecodeError as e:
                    raise SAMDeployError(f"Invalid JSON in parameter file {param_file_path}: {e}")
                except Exception as e:
                    raise SAMDeployError(f"Error reading parameter file {param_file_path}: {e}")
            else:
                raise SAMDeployError(f"Parameter file not found: {param_file_path}")
        
        # Merge with inline parameters (inline parameters take precedence)
        if parameters:
            final_parameters.update(parameters)
            logger.info(f"Merged with {len(parameters)} inline parameters")
        
        # Use final_parameters for the deployment
        parameters = final_parameters if final_parameters else None
        
        # Check if SAM CLI is available
        if not self._check_sam_cli():
            raise SAMDeployError("SAM CLI is not installed or not available in PATH")
        
        # Check for failed stack states and delete if necessary
        logger.info(f"Checking stack {stack_name} for failed states...")
        self._check_and_handle_failed_stack(stack_name, region)
        
        # Validate template file exists
        template_path = Path(template_file)
        if working_directory:
            template_path = Path(working_directory) / template_path
        
        if not template_path.exists():
            raise SAMDeployError(f"SAM template file not found: {template_path}")
        
        # Build SAM command
        cmd = self._build_sam_command(
            template_file=template_file,
            stack_name=stack_name,
            config_file=config_file,
            env=env,
            parameters=parameters,
            capabilities=capabilities,
            region=region,
            resolve_image_repos=resolve_image_repos
        )
        
        logger.info(f"Executing SAM command: {' '.join(cmd)}")
        
        try:
            # Change to working directory if specified
            original_cwd = None
            if working_directory:
                original_cwd = os.getcwd()
                os.chdir(working_directory)
                logger.info(f"Changed working directory to: {working_directory}")
            
            # Execute SAM build command first (unless skipped)
            if not skip_build:
                build_cmd = ['sam', 'build', '--template-file', template_file]
                logger.info(f"Building SAM application: {' '.join(build_cmd)}")
                
                build_result = subprocess.run(
                    build_cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout // 2  # Use half the timeout for build
                )
                
                if build_result.returncode != 0:
                    error_msg = f"SAM build failed with return code {build_result.returncode}"
                    if build_result.stderr:
                        error_msg += f": {build_result.stderr}"
                    logger.error(error_msg)
                    logger.error(f"Build command output: {build_result.stdout}")
                    raise SAMDeployError(error_msg)
                
                logger.info("SAM build completed successfully")
                logger.debug(f"Build command output: {build_result.stdout}")
            else:
                logger.info("Skipping SAM build step")
            
            # Execute SAM deploy command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            # Restore original working directory
            if original_cwd:
                os.chdir(original_cwd)
            
            # Handle SAM CLI return codes
            # SAM CLI returns exit code 1 when there are no changes to deploy, but this should be treated as success
            if result.returncode != 0:
                # Check if this is a "no changes to deploy" case, which should be treated as success
                output_text = result.stdout + (result.stderr or "")
                if "No changes to deploy" in output_text and "is up to date" in output_text:
                    logger.info("SAM deployment completed - no changes to deploy (stack is up to date)")
                    logger.info(f"Command output: {result.stdout}")
                else:
                    error_msg = f"SAM deploy failed with return code {result.returncode}"
                    if result.stderr:
                        error_msg += f": {result.stderr}"
                    logger.error(error_msg)
                    logger.error(f"Command output: {result.stdout}")
                    raise SAMDeployError(error_msg)
            
            # Log success message based on whether changes were deployed
            output_text = result.stdout + (result.stderr or "")
            if "No changes to deploy" in output_text and "is up to date" in output_text:
                logger.info("SAM deployment completed - no changes to deploy (stack is up to date)")
            else:
                logger.info("SAM deployment completed successfully")
            logger.info(f"Command output: {result.stdout}")
            
            # Get stack information if wait is enabled
            stack_info = {}
            if wait:
                try:
                    cf_client = self._get_cloudformation_client(region)
                    response = cf_client.describe_stacks(StackName=stack_name)
                    if response['Stacks']:
                        stack = response['Stacks'][0]
                        stack_info = {
                            'StackId': stack.get('StackId'),
                            'StackName': stack.get('StackName'),
                            'StackStatus': stack.get('StackStatus'),
                            'Outputs': {
                                output['OutputKey']: output['OutputValue']
                                for output in stack.get('Outputs', [])
                            }
                        }
                        logger.info(f"Stack status: {stack_info['StackStatus']}")
                except ClientError as e:
                    logger.warning(f"Could not retrieve stack information: {e}")
            
            return {
                'success': True,
                'stack_name': stack_name,
                'region': region,
                'command_output': result.stdout,
                'stack_info': stack_info
            }
            
        except subprocess.TimeoutExpired:
            error_msg = f"SAM deploy timed out after {timeout} seconds"
            logger.error(error_msg)
            raise SAMDeployError(error_msg)
        except Exception as e:
            logger.error(f"Unexpected error during SAM deployment: {e}")
            raise SAMDeployError(f"SAM deployment failed: {e}")


def cfngin_hook(
    context: Any,
    provider: Any,
    template_file: str,
    stack_name: str,
    config_file: Optional[str] = None,
    env: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None,
    param_file: Optional[str] = None,
    capabilities: Optional[List[str]] = None,
    region: Optional[str] = None,
    wait: bool = True,
    timeout: int = 1800,
    working_directory: Optional[str] = None,
    skip_build: bool = False,
    resolve_image_repos: bool = True,
    **kwargs
) -> Dict[str, Any]:
    """
    CFNgin hook for deploying SAM templates.
    
    Args:
        context: CFNgin context object
        provider: CFNgin provider object
        template_file: Path to SAM template file
        stack_name: CloudFormation stack name
        config_file: Path to SAM config file (samconfig.toml)
        env: Environment name for config
        parameters: Dictionary of parameter overrides
        param_file: Path to JSON file containing parameter key-value pairs
        capabilities: List of IAM capabilities
        region: AWS region (defaults to provider region)
        wait: Whether to wait for deployment completion
        timeout: Timeout in seconds
        working_directory: Directory to run SAM command from
        skip_build: Skip the sam build step (default: False)
        **kwargs: Additional arguments
        
    Returns:
        Dictionary with deployment results
    """
    # Use provider region if not specified
    if not region:
        region = getattr(provider, 'region', 'us-east-1')
    
    logger.info(f"CFNgin SAM deploy hook called for stack: {stack_name}")
    
    hook = SAMDeployHook()
    
    try:
        result = hook.deploy_sam_template(
            template_file=template_file,
            stack_name=stack_name,
            config_file=config_file,
            env=env,
            parameters=parameters,
            param_file=param_file,
            capabilities=capabilities,
            region=region,
            wait=wait,
            timeout=timeout,
            working_directory=working_directory,
            skip_build=skip_build,
            resolve_image_repos=resolve_image_repos
        )
        
        logger.info(f"SAM deployment successful for stack: {stack_name}")
        return result
        
    except SAMDeployError as e:
        logger.error(f"SAM deployment failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in SAM deploy hook: {e}")
        raise SAMDeployError(f"Hook execution failed: {e}")


def cfngin_delete_hook(
    context: Any,
    provider: Any,
    stack_name: str,
    region: Optional[str] = None,
    wait: bool = True,
    timeout: int = 1800,
    retain_resources: Optional[List[str]] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    CFNgin hook for deleting SAM/CloudFormation stacks.
    
    Args:
        context: CFNgin context object
        provider: CFNgin provider object
        stack_name: CloudFormation stack name
        region: AWS region (defaults to provider region)
        wait: Whether to wait for deletion completion
        timeout: Timeout in seconds
        retain_resources: List of logical resource IDs to retain during deletion
        **kwargs: Additional arguments
        
    Returns:
        Dictionary with deletion results
    """
    # Use provider region if not specified
    if not region:
        region = getattr(provider, 'region', 'us-east-1')
    
    logger.info(f"CFNgin SAM delete hook called for stack: {stack_name}")
    
    hook = SAMDeployHook()
    
    try:
        result = hook.delete_sam_stack(
            stack_name=stack_name,
            region=region,
            wait=wait,
            timeout=timeout,
            retain_resources=retain_resources
        )
        
        logger.info(f"SAM stack deletion successful for stack: {stack_name}")
        return result
        
    except SAMDeployError as e:
        logger.error(f"SAM stack deletion failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in SAM delete hook: {e}")
        raise SAMDeployError(f"Delete hook execution failed: {e}")


def main():
    """Command line interface for SAM deployment and deletion."""
    parser = argparse.ArgumentParser(
        description='Deploy or delete AWS SAM templates',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Deploy operations
  python sam_deploy.py deploy --template template.yaml --stack-name my-stack

  # With config file and environment
  python sam_deploy.py deploy --template template.yaml --stack-name my-stack \\
                       --config-file samconfig.toml --env dev

  # With parameter overrides
  python sam_deploy.py deploy --template template.yaml --stack-name my-stack \\
                       --parameters Environment=dev BucketName=my-bucket

  # With parameter file
  python sam_deploy.py deploy --template template.yaml --stack-name my-stack \\
                       --param-file parameters.json

  # With both parameter file and overrides (overrides take precedence)
  python sam_deploy.py deploy --template template.yaml --stack-name my-stack \\
                       --param-file parameters.json --parameters Environment=prod

  # Skip build step (use existing build artifacts)
  python sam_deploy.py deploy --template template.yaml --stack-name my-stack \\
                       --skip-build

  # Delete operations
  python sam_deploy.py delete --stack-name my-stack

  # Delete with resource retention
  python sam_deploy.py delete --stack-name my-stack \\
                       --retain-resources MyS3Bucket MyDynamoTable
        """
    )
    
    # Add subcommands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Deploy subcommand
    deploy_parser = subparsers.add_parser('deploy', help='Deploy SAM template')
    deploy_parser.add_argument(
        '--template', '--template-file',
        required=True,
        help='Path to SAM template file'
    )
    
    deploy_parser.add_argument(
        '--stack-name',
        required=True,
        help='CloudFormation stack name'
    )
    
    deploy_parser.add_argument(
        '--config-file',
        help='Path to SAM config file (samconfig.toml)'
    )
    
    deploy_parser.add_argument(
        '--env',
        help='Environment name for config'
    )
    
    deploy_parser.add_argument(
        '--parameters',
        nargs='*',
        help='Parameter overrides in key=value format'
    )
    
    deploy_parser.add_argument(
        '--param-file',
        help='Path to JSON file containing parameter key-value pairs'
    )
    
    deploy_parser.add_argument(
        '--capabilities',
        nargs='*',
        help='IAM capabilities (default: CAPABILITY_IAM CAPABILITY_NAMED_IAM)'
    )
    
    deploy_parser.add_argument(
        '--region',
        default='us-east-1',
        help='AWS region (default: us-east-1)'
    )
    
    deploy_parser.add_argument(
        '--no-wait',
        action='store_true',
        help='Do not wait for deployment completion'
    )
    
    deploy_parser.add_argument(
        '--timeout',
        type=int,
        default=1800,
        help='Timeout in seconds (default: 1800)'
    )
    
    deploy_parser.add_argument(
        '--working-directory',
        help='Directory to run SAM command from'
    )
    
    deploy_parser.add_argument(
        '--skip-build',
        action='store_true',
        help='Skip the sam build step'
    )
    
    # Delete subcommand
    delete_parser = subparsers.add_parser('delete', help='Delete SAM stack')
    delete_parser.add_argument(
        '--stack-name',
        required=True,
        help='CloudFormation stack name'
    )
    
    delete_parser.add_argument(
        '--region',
        default='us-east-1',
        help='AWS region (default: us-east-1)'
    )
    
    delete_parser.add_argument(
        '--no-wait',
        action='store_true',
        help='Do not wait for deletion completion'
    )
    
    delete_parser.add_argument(
        '--timeout',
        type=int,
        default=1800,
        help='Timeout in seconds (default: 1800)'
    )
    
    delete_parser.add_argument(
        '--retain-resources',
        nargs='*',
        help='Logical resource IDs to retain during deletion'
    )
    
    # Common arguments
    for subparser in [deploy_parser, delete_parser]:
        subparser.add_argument(
            '--verbose', '-v',
            action='store_true',
            help='Enable verbose logging'
        )
    
    # Handle legacy usage (backward compatibility)
    if len(sys.argv) > 1 and sys.argv[1] not in ['deploy', 'delete']:
        # Legacy mode - assume deploy command
        legacy_parser = argparse.ArgumentParser(
            description='Deploy AWS SAM templates (legacy mode)',
            formatter_class=argparse.RawDescriptionHelpFormatter
        )
        
        legacy_parser.add_argument(
            '--template', '--template-file',
            required=True,
            help='Path to SAM template file'
        )
        
        legacy_parser.add_argument(
            '--stack-name',
            required=True,
            help='CloudFormation stack name'
        )
        
        legacy_parser.add_argument(
            '--config-file',
            help='Path to SAM config file (samconfig.toml)'
        )
        
        legacy_parser.add_argument(
            '--env',
            help='Environment name for config'
        )
        
        legacy_parser.add_argument(
            '--parameters',
            nargs='*',
            help='Parameter overrides in key=value format'
        )
        
        legacy_parser.add_argument(
            '--param-file',
            help='Path to JSON file containing parameter key-value pairs'
        )
        
        legacy_parser.add_argument(
            '--capabilities',
            nargs='*',
            help='IAM capabilities (default: CAPABILITY_IAM CAPABILITY_NAMED_IAM)'
        )
        
        legacy_parser.add_argument(
            '--region',
            default='us-east-1',
            help='AWS region (default: us-east-1)'
        )
        
        legacy_parser.add_argument(
            '--no-wait',
            action='store_true',
            help='Do not wait for deployment completion'
        )
        
        legacy_parser.add_argument(
            '--timeout',
            type=int,
            default=1800,
            help='Timeout in seconds (default: 1800)'
        )
        
        legacy_parser.add_argument(
            '--working-directory',
            help='Directory to run SAM command from'
        )
        
        legacy_parser.add_argument(
            '--skip-build',
            action='store_true',
            help='Skip the sam build step'
        )
        
        legacy_parser.add_argument(
            '--verbose', '-v',
            action='store_true',
            help='Enable verbose logging'
        )
        
        args = legacy_parser.parse_args()
        args.command = 'deploy'  # Set command for legacy mode
    else:
        args = parser.parse_args()
    
    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Handle missing command
    if not hasattr(args, 'command') or not args.command:
        parser.print_help()
        return 1
    
    try:
        hook = SAMDeployHook()
        
        if args.command == 'deploy':
            # Parse parameters
            parameters = {}
            if hasattr(args, 'parameters') and args.parameters:
                for param in args.parameters:
                    if '=' in param:
                        key, value = param.split('=', 1)
                        parameters[key] = value
                    else:
                        logger.warning(f"Invalid parameter format: {param} (expected key=value)")
            
            result = hook.deploy_sam_template(
                template_file=args.template,
                stack_name=args.stack_name,
                config_file=getattr(args, 'config_file', None),
                env=getattr(args, 'env', None),
                parameters=parameters if parameters else None,
                param_file=getattr(args, 'param_file', None),
                capabilities=getattr(args, 'capabilities', None),
                region=args.region,
                wait=not args.no_wait,
                timeout=args.timeout,
                working_directory=getattr(args, 'working_directory', None),
                skip_build=getattr(args, 'skip_build', False)
            )
            
            print(f"✅ SAM deployment successful!")
            print(f"Stack Name: {result['stack_name']}")
            print(f"Region: {result['region']}")
            
            if result.get('stack_info', {}).get('Outputs'):
                print("\nStack Outputs:")
                for key, value in result['stack_info']['Outputs'].items():
                    print(f"  {key}: {value}")
        
        elif args.command == 'delete':
            result = hook.delete_sam_stack(
                stack_name=args.stack_name,
                region=args.region,
                wait=not args.no_wait,
                timeout=args.timeout,
                retain_resources=getattr(args, 'retain_resources', None)
            )
            
            print(f"✅ SAM stack deletion successful!")
            print(f"Stack Name: {result['stack_name']}")
            print(f"Region: {result['region']}")
            print(f"Message: {result['message']}")
        
        return 0
        
    except SAMDeployError as e:
        logger.error(f"SAM operation failed: {e}")
        return 1
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
