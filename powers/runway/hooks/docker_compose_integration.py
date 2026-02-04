#!/usr/bin/env python3
"""
CFNgin hook for Docker Compose integration with Runway deployments.

This hook provides integration between Runway infrastructure deployments and
Docker Compose local development environments. It can start containers after
infrastructure deployment and stop/cleanup containers during infrastructure
destruction.

Usage in CFNgin:
    pre_deploy:
      - path: hooks.docker_compose_integration.start_containers
        args:
          compose_file: docker-compose.yml
          env_file: .env.local
          services: ["api-public", "api-internal", "registration-site"]
          wait_timeout: 300
          health_check: true

    post_destroy:
      - path: hooks.docker_compose_integration.stop_containers
        args:
          compose_file: docker-compose.yml
          cleanup: true
          remove_volumes: false

Command Line Usage:
    python hooks/docker_compose_integration.py start --compose-file docker-compose.yml
    python hooks/docker_compose_integration.py stop --compose-file docker-compose.yml --cleanup
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

try:
    import docker
    DOCKER_CLIENT_AVAILABLE = True
except ImportError:
    DOCKER_CLIENT_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DockerComposeError(Exception):
    """Custom exception for Docker Compose integration errors."""
    pass


class DockerComposeIntegration:
    """Docker Compose integration for Runway deployments."""
    
    def __init__(self, compose_file: str = "docker-compose.yml", 
                 working_directory: Optional[str] = None):
        """
        Initialize Docker Compose integration.
        
        Args:
            compose_file: Path to docker-compose.yml file
            working_directory: Directory to run docker-compose commands from
        """
        self.compose_file = compose_file
        self.working_directory = working_directory or os.getcwd()
        self.compose_path = Path(self.working_directory) / compose_file
        
        # Initialize Docker client if available
        self.docker_client = None
        if DOCKER_CLIENT_AVAILABLE:
            try:
                self.docker_client = docker.from_env()
            except Exception as e:
                logger.warning(f"Could not initialize Docker client: {e}")
    
    def _check_docker_compose(self) -> bool:
        """Check if Docker Compose is installed and available."""
        try:
            # Try docker compose (newer version)
            result = subprocess.run(
                ['docker', 'compose', 'version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                logger.info(f"Docker Compose version: {result.stdout.strip()}")
                return True
            
            # Try docker-compose (legacy version)
            result = subprocess.run(
                ['docker-compose', '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                logger.info(f"Docker Compose version: {result.stdout.strip()}")
                return True
            
            return False
            
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.error(f"Docker Compose not found or timeout: {e}")
            return False
    
    def _get_compose_command(self) -> List[str]:
        """Get the appropriate docker-compose command."""
        # Try docker compose first (newer version)
        try:
            result = subprocess.run(
                ['docker', 'compose', 'version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return ['docker', 'compose']
        except:
            pass
        
        # Fall back to docker-compose (legacy version)
        try:
            result = subprocess.run(
                ['docker-compose', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return ['docker-compose']
        except:
            pass
        
        raise DockerComposeError("Neither 'docker compose' nor 'docker-compose' command is available")
    
    def _run_compose_command(self, command: List[str], timeout: int = 300) -> subprocess.CompletedProcess:
        """Run a docker-compose command."""
        compose_cmd = self._get_compose_command()
        full_cmd = compose_cmd + ['-f', self.compose_file] + command
        
        logger.info(f"Executing: {' '.join(full_cmd)}")
        
        # Change to working directory
        original_cwd = os.getcwd()
        try:
            os.chdir(self.working_directory)
            
            result = subprocess.run(
                full_cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            return result
            
        finally:
            os.chdir(original_cwd)
    
    def _check_env_file(self, env_file: Optional[str] = None) -> bool:
        """Check if required environment file exists."""
        if not env_file:
            return True
        
        env_path = Path(self.working_directory) / env_file
        if not env_path.exists():
            logger.warning(f"Environment file not found: {env_path}")
            return False
        
        logger.info(f"Environment file found: {env_path}")
        return True
    
    def _wait_for_services(self, services: Optional[List[str]] = None, 
                          timeout: int = 300) -> bool:
        """Wait for services to be healthy."""
        if not services:
            logger.info("No specific services to wait for")
            return True
        
        logger.info(f"Waiting for services to be healthy: {services}")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # Check service health using docker-compose ps
                result = self._run_compose_command(['ps', '--format', 'json'], timeout=30)
                
                if result.returncode != 0:
                    logger.warning(f"Failed to get service status: {result.stderr}")
                    time.sleep(10)
                    continue
                
                # Parse service status
                all_healthy = True
                service_statuses = {}
                
                # Handle both single JSON object and JSON lines format
                output = result.stdout.strip()
                if not output:
                    logger.warning("No service status output")
                    time.sleep(10)
                    continue
                
                # Try to parse as JSON lines first
                try:
                    for line in output.split('\n'):
                        if line.strip():
                            service_info = json.loads(line)
                            service_name = service_info.get('Service', service_info.get('Name', ''))
                            service_state = service_info.get('State', '')
                            service_health = service_info.get('Health', '')
                            
                            # Extract service name from container name if needed
                            if not service_name and 'Name' in service_info:
                                container_name = service_info['Name']
                                # Extract service name from container name (e.g., cmm-api-public -> api-public)
                                if container_name.startswith('cmm-'):
                                    service_name = container_name[4:]  # Remove 'cmm-' prefix
                            
                            service_statuses[service_name] = {
                                'state': service_state,
                                'health': service_health
                            }
                except json.JSONDecodeError:
                    # Try parsing as single JSON object
                    try:
                        services_data = json.loads(output)
                        if isinstance(services_data, list):
                            for service_info in services_data:
                                service_name = service_info.get('Service', service_info.get('Name', ''))
                                service_state = service_info.get('State', '')
                                service_health = service_info.get('Health', '')
                                
                                service_statuses[service_name] = {
                                    'state': service_state,
                                    'health': service_health
                                }
                    except json.JSONDecodeError:
                        logger.warning(f"Could not parse service status output: {output}")
                        time.sleep(10)
                        continue
                
                # Check if all requested services are healthy
                for service in services:
                    status = service_statuses.get(service, {})
                    state = status.get('state', '').lower()
                    health = status.get('health', '').lower()
                    
                    if 'running' not in state:
                        logger.info(f"Service {service} not running (state: {state})")
                        all_healthy = False
                        break
                    
                    # If health check is defined, wait for it to be healthy
                    if health and health not in ['healthy', '']:
                        logger.info(f"Service {service} not healthy (health: {health})")
                        all_healthy = False
                        break
                
                if all_healthy:
                    logger.info("All services are healthy")
                    return True
                
                logger.info(f"Waiting for services... ({int(time.time() - start_time)}s elapsed)")
                time.sleep(10)
                
            except Exception as e:
                logger.warning(f"Error checking service health: {e}")
                time.sleep(10)
        
        logger.error(f"Timeout waiting for services to be healthy after {timeout}s")
        return False
    
    def start_containers(
        self,
        services: Optional[List[str]] = None,
        env_file: Optional[str] = None,
        detached: bool = True,
        build: bool = False,
        wait_timeout: int = 300,
        health_check: bool = True
    ) -> Dict[str, Any]:
        """
        Start Docker Compose containers.
        
        Args:
            services: List of specific services to start (None for all)
            env_file: Environment file to check for existence
            detached: Run containers in detached mode
            build: Build images before starting
            wait_timeout: Timeout for waiting for services to be healthy
            health_check: Whether to wait for health checks
            
        Returns:
            Dictionary with operation results
        """
        logger.info("Starting Docker Compose containers")
        
        # Check prerequisites
        if not self._check_docker_compose():
            raise DockerComposeError("Docker Compose is not available")
        
        if not self.compose_path.exists():
            raise DockerComposeError(f"Docker Compose file not found: {self.compose_path}")
        
        if not self._check_env_file(env_file):
            logger.warning("Environment file missing - containers may not start properly")
        
        try:
            # Build images if requested
            if build:
                logger.info("Building Docker images...")
                build_cmd = ['build']
                if services:
                    build_cmd.extend(services)
                
                result = self._run_compose_command(build_cmd, timeout=600)
                if result.returncode != 0:
                    logger.error(f"Build failed: {result.stderr}")
                    raise DockerComposeError(f"Docker build failed: {result.stderr}")
                
                logger.info("Docker images built successfully")
            
            # Start containers
            up_cmd = ['up']
            if detached:
                up_cmd.append('-d')
            if services:
                up_cmd.extend(services)
            
            logger.info(f"Starting containers: {services or 'all services'}")
            result = self._run_compose_command(up_cmd, timeout=wait_timeout)
            
            if result.returncode != 0:
                logger.error(f"Container startup failed: {result.stderr}")
                raise DockerComposeError(f"Failed to start containers: {result.stderr}")
            
            logger.info("Containers started successfully")
            logger.info(f"Command output: {result.stdout}")
            
            # Wait for services to be healthy if requested
            if health_check and detached:
                if not self._wait_for_services(services, wait_timeout):
                    logger.warning("Some services may not be healthy, but continuing...")
            
            return {
                'success': True,
                'services': services or 'all',
                'message': 'Containers started successfully',
                'command_output': result.stdout
            }
            
        except subprocess.TimeoutExpired:
            error_msg = f"Container startup timed out after {wait_timeout} seconds"
            logger.error(error_msg)
            raise DockerComposeError(error_msg)
        except Exception as e:
            logger.error(f"Unexpected error starting containers: {e}")
            raise DockerComposeError(f"Failed to start containers: {e}")
    
    def stop_containers(
        self,
        services: Optional[List[str]] = None,
        cleanup: bool = False,
        remove_volumes: bool = False,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """
        Stop Docker Compose containers.
        
        Args:
            services: List of specific services to stop (None for all)
            cleanup: Whether to remove containers after stopping
            remove_volumes: Whether to remove volumes during cleanup
            timeout: Timeout for stopping containers
            
        Returns:
            Dictionary with operation results
        """
        logger.info("Stopping Docker Compose containers")
        
        # Check prerequisites
        if not self._check_docker_compose():
            raise DockerComposeError("Docker Compose is not available")
        
        try:
            # Stop containers
            if cleanup:
                # Use down command for cleanup
                down_cmd = ['down']
                if remove_volumes:
                    down_cmd.append('-v')
                down_cmd.extend(['--timeout', str(timeout)])
                
                logger.info("Stopping and removing containers...")
                result = self._run_compose_command(down_cmd, timeout=timeout + 60)
                
            else:
                # Use stop command to just stop containers
                stop_cmd = ['stop']
                if services:
                    stop_cmd.extend(services)
                stop_cmd.extend(['--timeout', str(timeout)])
                
                logger.info(f"Stopping containers: {services or 'all services'}")
                result = self._run_compose_command(stop_cmd, timeout=timeout + 60)
            
            if result.returncode != 0:
                logger.warning(f"Stop command completed with warnings: {result.stderr}")
                # Don't raise error for stop operations as containers might already be stopped
            
            logger.info("Containers stopped successfully")
            if result.stdout:
                logger.info(f"Command output: {result.stdout}")
            
            return {
                'success': True,
                'services': services or 'all',
                'cleanup': cleanup,
                'message': 'Containers stopped successfully',
                'command_output': result.stdout
            }
            
        except subprocess.TimeoutExpired:
            error_msg = f"Container stop timed out after {timeout + 60} seconds"
            logger.error(error_msg)
            raise DockerComposeError(error_msg)
        except Exception as e:
            logger.error(f"Unexpected error stopping containers: {e}")
            raise DockerComposeError(f"Failed to stop containers: {e}")
    
    def get_container_status(self) -> Dict[str, Any]:
        """Get status of Docker Compose containers."""
        logger.info("Getting container status")
        
        try:
            result = self._run_compose_command(['ps', '--format', 'json'], timeout=30)
            
            if result.returncode != 0:
                logger.warning(f"Failed to get container status: {result.stderr}")
                return {'success': False, 'error': result.stderr}
            
            # Parse container status
            containers = []
            output = result.stdout.strip()
            
            if output:
                try:
                    # Try parsing as JSON lines
                    for line in output.split('\n'):
                        if line.strip():
                            container_info = json.loads(line)
                            containers.append(container_info)
                except json.JSONDecodeError:
                    # Try parsing as single JSON object
                    try:
                        containers_data = json.loads(output)
                        if isinstance(containers_data, list):
                            containers = containers_data
                    except json.JSONDecodeError:
                        logger.warning(f"Could not parse container status: {output}")
            
            return {
                'success': True,
                'containers': containers,
                'count': len(containers)
            }
            
        except Exception as e:
            logger.error(f"Error getting container status: {e}")
            return {'success': False, 'error': str(e)}


def start_containers_hook(
    context: Any,
    compose_file: str = "docker-compose.yml",
    services: Optional[List[str]] = None,
    env_file: Optional[str] = None,
    build: bool = False,
    wait_timeout: int = 300,
    health_check: bool = True,
    working_directory: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    CFNgin hook for starting Docker Compose containers.
    
    Args:
        context: CFNgin context object
        compose_file: Path to docker-compose.yml file
        services: List of specific services to start
        env_file: Environment file to check for existence
        build: Build images before starting
        wait_timeout: Timeout for waiting for services
        health_check: Whether to wait for health checks
        working_directory: Directory to run commands from
        **kwargs: Additional arguments
        
    Returns:
        Dictionary with operation results
    """
    logger.info("CFNgin Docker Compose start hook called")
    
    try:
        integration = DockerComposeIntegration(
            compose_file=compose_file,
            working_directory=working_directory
        )
        
        result = integration.start_containers(
            services=services,
            env_file=env_file,
            build=build,
            wait_timeout=wait_timeout,
            health_check=health_check
        )
        
        logger.info("Docker Compose start hook completed successfully")
        return result
        
    except DockerComposeError as e:
        logger.error(f"Docker Compose start hook failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in start hook: {e}")
        raise DockerComposeError(f"Start hook execution failed: {e}")


def stop_containers_hook(
    context: Any,
    compose_file: str = "docker-compose.yml",
    services: Optional[List[str]] = None,
    cleanup: bool = True,
    remove_volumes: bool = False,
    timeout: int = 30,
    working_directory: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    CFNgin hook for stopping Docker Compose containers.
    
    Args:
        context: CFNgin context object
        compose_file: Path to docker-compose.yml file
        services: List of specific services to stop
        cleanup: Whether to remove containers after stopping
        remove_volumes: Whether to remove volumes during cleanup
        timeout: Timeout for stopping containers
        working_directory: Directory to run commands from
        **kwargs: Additional arguments
        
    Returns:
        Dictionary with operation results
    """
    logger.info("CFNgin Docker Compose stop hook called")
    
    try:
        integration = DockerComposeIntegration(
            compose_file=compose_file,
            working_directory=working_directory
        )
        
        result = integration.stop_containers(
            services=services,
            cleanup=cleanup,
            remove_volumes=remove_volumes,
            timeout=timeout
        )
        
        logger.info("Docker Compose stop hook completed successfully")
        return result
        
    except DockerComposeError as e:
        logger.error(f"Docker Compose stop hook failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in stop hook: {e}")
        raise DockerComposeError(f"Stop hook execution failed: {e}")


def main():
    """Command line interface for Docker Compose integration."""
    parser = argparse.ArgumentParser(
        description='Docker Compose integration for Runway deployments',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start all containers
  python docker_compose_integration.py start

  # Start specific services
  python docker_compose_integration.py start --services api-public api-internal

  # Start with build
  python docker_compose_integration.py start --build --wait-timeout 600

  # Stop all containers
  python docker_compose_integration.py stop

  # Stop with cleanup
  python docker_compose_integration.py stop --cleanup --remove-volumes

  # Get container status
  python docker_compose_integration.py status
        """
    )
    
    # Add subcommands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Start subcommand
    start_parser = subparsers.add_parser('start', help='Start Docker Compose containers')
    start_parser.add_argument(
        '--compose-file', '-f',
        default='docker-compose.yml',
        help='Path to docker-compose.yml file'
    )
    start_parser.add_argument(
        '--services',
        nargs='*',
        help='Specific services to start'
    )
    start_parser.add_argument(
        '--env-file',
        help='Environment file to check for existence'
    )
    start_parser.add_argument(
        '--build',
        action='store_true',
        help='Build images before starting'
    )
    start_parser.add_argument(
        '--wait-timeout',
        type=int,
        default=300,
        help='Timeout for waiting for services (default: 300)'
    )
    start_parser.add_argument(
        '--no-health-check',
        action='store_true',
        help='Skip health check waiting'
    )
    start_parser.add_argument(
        '--working-directory', '-C',
        help='Directory to run commands from'
    )
    
    # Stop subcommand
    stop_parser = subparsers.add_parser('stop', help='Stop Docker Compose containers')
    stop_parser.add_argument(
        '--compose-file', '-f',
        default='docker-compose.yml',
        help='Path to docker-compose.yml file'
    )
    stop_parser.add_argument(
        '--services',
        nargs='*',
        help='Specific services to stop'
    )
    stop_parser.add_argument(
        '--cleanup',
        action='store_true',
        help='Remove containers after stopping'
    )
    stop_parser.add_argument(
        '--remove-volumes',
        action='store_true',
        help='Remove volumes during cleanup'
    )
    stop_parser.add_argument(
        '--timeout',
        type=int,
        default=30,
        help='Timeout for stopping containers (default: 30)'
    )
    stop_parser.add_argument(
        '--working-directory', '-C',
        help='Directory to run commands from'
    )
    
    # Status subcommand
    status_parser = subparsers.add_parser('status', help='Get container status')
    status_parser.add_argument(
        '--compose-file', '-f',
        default='docker-compose.yml',
        help='Path to docker-compose.yml file'
    )
    status_parser.add_argument(
        '--working-directory', '-C',
        help='Directory to run commands from'
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        integration = DockerComposeIntegration(
            compose_file=args.compose_file,
            working_directory=args.working_directory
        )
        
        if args.command == 'start':
            result = integration.start_containers(
                services=args.services,
                env_file=args.env_file,
                build=args.build,
                wait_timeout=args.wait_timeout,
                health_check=not args.no_health_check
            )
            
        elif args.command == 'stop':
            result = integration.stop_containers(
                services=args.services,
                cleanup=args.cleanup,
                remove_volumes=args.remove_volumes,
                timeout=args.timeout
            )
            
        elif args.command == 'status':
            result = integration.get_container_status()
            
        else:
            logger.error(f"Unknown command: {args.command}")
            return 1
        
        if result.get('success'):
            logger.info(f"Operation completed successfully: {result.get('message', '')}")
            return 0
        else:
            logger.error(f"Operation failed: {result.get('error', 'Unknown error')}")
            return 1
            
    except DockerComposeError as e:
        logger.error(f"Docker Compose error: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1


if __name__ == '__main__':
    exit(main())