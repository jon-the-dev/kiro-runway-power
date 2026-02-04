#!/usr/bin/env python3
"""
Docker Build and Push Hook for Runway/CFNgin

This hook builds Docker images and pushes them to ECR repositories,
replacing the need for manual shell scripts in container-based Lambda deployments.
"""

import argparse
import json
import os
import subprocess
import sys
from typing import Dict, Any, Optional

import boto3
from botocore.exceptions import ClientError


class DockerBuildPushError(Exception):
    """Custom exception for Docker build and push operations."""
    pass


class DockerBuildPushHook:
    """Hook for building and pushing Docker images to ECR."""
    
    def __init__(self, context: Any = None, provider: Any = None):
        """Initialize the hook with CFNgin context and provider."""
        self.context = context
        self.provider = provider
        self.logger = context.logger if context else None
        
        # AWS clients
        self.ecr_client = None
        self.sts_client = None
        
    def _get_aws_clients(self, region: str):
        """Initialize AWS clients."""
        if not self.ecr_client:
            self.ecr_client = boto3.client('ecr', region_name=region)
        if not self.sts_client:
            self.sts_client = boto3.client('sts', region_name=region)
    
    def _log(self, message: str, level: str = "info"):
        """Log a message using the CFNgin logger or print."""
        if self.logger:
            getattr(self.logger, level)(message)
        else:
            print(f"[{level.upper()}] {message}")
    
    def _run_command(self, command: list, cwd: str = None) -> tuple:
        """Run a shell command and return (success, stdout, stderr)."""
        try:
            self._log(f"Running command: {' '.join(command)}")
            result = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                self._log(f"Command succeeded: {result.stdout.strip()}")
                return True, result.stdout.strip(), result.stderr.strip()
            else:
                self._log(f"Command failed: {result.stderr.strip()}", "error")
                return False, result.stdout.strip(), result.stderr.strip()
                
        except Exception as e:
            self._log(f"Command execution error: {str(e)}", "error")
            return False, "", str(e)
    
    def _ensure_ecr_repository(self, repository_name: str, region: str, environment: str) -> str:
        """Ensure ECR repository exists and return its URI."""
        self._get_aws_clients(region)
        
        try:
            # Check if repository exists
            response = self.ecr_client.describe_repositories(
                repositoryNames=[repository_name]
            )
            repository_uri = response['repositories'][0]['repositoryUri']
            self._log(f"ECR repository exists: {repository_uri}")
            return repository_uri
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'RepositoryNotFoundException':
                # Create repository
                self._log(f"Creating ECR repository: {repository_name}")
                try:
                    response = self.ecr_client.create_repository(
                        repositoryName=repository_name,
                        imageScanningConfiguration={'scanOnPush': True},
                        tags=[
                            {'Key': 'Environment', 'Value': environment},
                            {'Key': 'Application', 'Value': 'cmm-internal-api'},
                            {'Key': 'ManagedBy', 'Value': 'runway-cfngin'}
                        ]
                    )
                    repository_uri = response['repository']['repositoryUri']
                    self._log(f"ECR repository created: {repository_uri}")
                    return repository_uri
                    
                except ClientError as create_error:
                    raise DockerBuildPushError(f"Failed to create ECR repository: {str(create_error)}")
            else:
                raise DockerBuildPushError(f"Failed to check ECR repository: {str(e)}")
    
    def _get_ecr_login_token(self, region: str) -> str:
        """Get ECR login token."""
        self._get_aws_clients(region)
        
        try:
            response = self.ecr_client.get_authorization_token()
            token = response['authorizationData'][0]['authorizationToken']
            return token
        except ClientError as e:
            raise DockerBuildPushError(f"Failed to get ECR login token: {str(e)}")
    
    def _docker_login(self, region: str, account_id: str):
        """Login to ECR using Docker CLI."""
        self._log("🔐 Logging into ECR...")
        
        # Get login password
        success, password, error = self._run_command([
            'aws', 'ecr', 'get-login-password', '--region', region
        ])
        
        if not success:
            raise DockerBuildPushError(f"Failed to get ECR login password: {error}")
        
        # Docker login with password via stdin
        registry_url = f"{account_id}.dkr.ecr.{region}.amazonaws.com"
        self._log(f"Logging into Docker registry: {registry_url}")
        
        process = subprocess.Popen(
            ['docker', 'login', '--username', 'AWS', '--password-stdin', registry_url],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate(input=password)
        
        if process.returncode != 0:
            raise DockerBuildPushError(f"Docker login failed: {stderr}")
        
        self._log("✅ Docker login successful")
    
    def _build_docker_image(self, dockerfile_path: str, image_name: str, image_tag: str, build_context: str):
        """Build Docker image."""
        self._log(f"🔨 Building Docker image: {image_name}:{image_tag}")
        
        command = [
            'docker', 'build',
            '--platform', 'linux/amd64',
            '-t', f"{image_name}:{image_tag}",
            '-f', dockerfile_path,
            build_context
        ]
        
        success, stdout, error = self._run_command(command)
        
        if not success:
            raise DockerBuildPushError(f"Docker build failed: {error}")
        
        self._log("✅ Docker build successful")
    
    def _tag_and_push_image(self, local_image: str, ecr_uri: str):
        """Tag and push image to ECR."""
        self._log(f"🏷️  Tagging image: {ecr_uri}")
        
        # Tag image
        success, stdout, error = self._run_command([
            'docker', 'tag', local_image, ecr_uri
        ])
        
        if not success:
            raise DockerBuildPushError(f"Docker tag failed: {error}")
        
        # Push image
        self._log(f"📤 Pushing image to ECR: {ecr_uri}")
        success, stdout, error = self._run_command([
            'docker', 'push', ecr_uri
        ])
        
        if not success:
            raise DockerBuildPushError(f"Docker push failed: {error}")
        
        self._log("✅ Docker push successful")
    
    def build_and_push(
        self,
        repository_name: str,
        image_tag: str,
        dockerfile_path: str = "Dockerfile",
        build_context: str = ".",
        region: str = "us-east-1",
        environment: str = "dev",
        working_directory: str = None
    ) -> Dict[str, str]:
        """
        Build and push Docker image to ECR.
        
        Args:
            repository_name: ECR repository name
            image_tag: Image tag (usually environment name)
            dockerfile_path: Path to Dockerfile relative to build_context
            build_context: Docker build context directory
            region: AWS region
            environment: Environment name (dev/prod)
            working_directory: Directory to run commands from
            
        Returns:
            Dictionary with image URI and other metadata
        """
        try:
            # Change to working directory if specified
            original_cwd = os.getcwd()
            if working_directory:
                os.chdir(working_directory)
                self._log(f"Changed to working directory: {working_directory}")
            
            # Get AWS account ID
            self._get_aws_clients(region)
            account_id = self.sts_client.get_caller_identity()['Account']
            
            self._log(f"🚀 Building and pushing Docker image...")
            self._log(f"Repository: {repository_name}")
            self._log(f"Tag: {image_tag}")
            self._log(f"Region: {region}")
            self._log(f"Account: {account_id}")
            
            # Ensure ECR repository exists
            repository_uri = self._ensure_ecr_repository(repository_name, region, environment)
            
            # Login to ECR
            self._docker_login(region, account_id)
            
            # Build Docker image
            local_image = f"{repository_name}:{image_tag}"
            self._build_docker_image(dockerfile_path, repository_name, image_tag, build_context)
            
            # Tag and push to ECR
            ecr_image_uri = f"{repository_uri}:{image_tag}"
            self._tag_and_push_image(local_image, ecr_image_uri)
            
            self._log(f"✅ Docker build and push completed successfully!")
            self._log(f"📋 Image URI: {ecr_image_uri}")
            
            return {
                "success": True,
                "image_uri": ecr_image_uri,
                "repository_uri": repository_uri,
                "account_id": account_id,
                "region": region,
                "tag": image_tag
            }
            
        except Exception as e:
            self._log(f"❌ Docker build and push failed: {str(e)}", "error")
            raise DockerBuildPushError(f"Docker build and push failed: {str(e)}")
        
        finally:
            # Restore original working directory
            if working_directory:
                os.chdir(original_cwd)


def cfngin_hook(context, provider, **kwargs) -> bool:
    """
    CFNgin hook entry point for building and pushing Docker images.
    
    Args:
        context: CFNgin context
        provider: CFNgin provider
        **kwargs: Hook arguments
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        hook = DockerBuildPushHook(context, provider)
        
        # Extract parameters
        repository_name = kwargs.get('repository_name')
        image_tag = kwargs.get('image_tag', 'latest')
        dockerfile_path = kwargs.get('dockerfile_path', 'Dockerfile')
        build_context = kwargs.get('build_context', '.')
        region = kwargs.get('region', 'us-east-1')
        environment = kwargs.get('environment', 'dev')
        working_directory = kwargs.get('working_directory')
        
        if not repository_name:
            raise DockerBuildPushError("repository_name is required")
        
        # Build and push image
        result = hook.build_and_push(
            repository_name=repository_name,
            image_tag=image_tag,
            dockerfile_path=dockerfile_path,
            build_context=build_context,
            region=region,
            environment=environment,
            working_directory=working_directory
        )
        
        # Store result in context for other hooks to use
        if context:
            if not hasattr(context, 'hook_data'):
                context.hook_data = {}
            context.hook_data['docker_build_push'] = result
        
        return True
        
    except Exception as e:
        if context and context.logger:
            context.logger.error(f"Docker build and push hook failed: {str(e)}")
        else:
            print(f"ERROR: Docker build and push hook failed: {str(e)}")
        return False


def main():
    """Command line interface for testing the hook."""
    parser = argparse.ArgumentParser(description="Build and push Docker image to ECR")
    parser.add_argument('repository_name', help='ECR repository name')
    parser.add_argument('--image-tag', default='latest', help='Image tag')
    parser.add_argument('--dockerfile-path', default='Dockerfile', help='Path to Dockerfile')
    parser.add_argument('--build-context', default='.', help='Docker build context')
    parser.add_argument('--region', default='us-east-1', help='AWS region')
    parser.add_argument('--environment', default='dev', help='Environment name')
    parser.add_argument('--working-directory', help='Working directory')
    
    args = parser.parse_args()
    
    try:
        hook = DockerBuildPushHook()
        result = hook.build_and_push(
            repository_name=args.repository_name,
            image_tag=args.image_tag,
            dockerfile_path=args.dockerfile_path,
            build_context=args.build_context,
            region=args.region,
            environment=args.environment,
            working_directory=args.working_directory
        )
        
        print(f"✅ Success! Image URI: {result['image_uri']}")
        return 0
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
