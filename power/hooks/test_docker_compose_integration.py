#!/usr/bin/env python3
"""
Test script for Docker Compose integration hooks.

This script tests the Docker Compose integration functionality without
requiring actual CFNgin context or deployed infrastructure.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add hooks directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from docker_compose_integration import (
    DockerComposeIntegration,
    DockerComposeError,
    start_containers_hook,
    stop_containers_hook
)


class TestDockerComposeIntegration(unittest.TestCase):
    """Test cases for Docker Compose integration."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.compose_file = "docker-compose.yml"
        self.compose_path = Path(self.temp_dir) / self.compose_file
        
        # Create a minimal docker-compose.yml for testing
        compose_content = """
version: '3.8'
services:
  test-service:
    image: nginx:alpine
    ports:
      - "8080:80"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:80"]
      interval: 30s
      timeout: 10s
      retries: 3
"""
        self.compose_path.write_text(compose_content)
        
        self.integration = DockerComposeIntegration(
            compose_file=self.compose_file,
            working_directory=self.temp_dir
        )
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_initialization(self):
        """Test DockerComposeIntegration initialization."""
        self.assertEqual(self.integration.compose_file, self.compose_file)
        self.assertEqual(self.integration.working_directory, self.temp_dir)
        self.assertTrue(self.integration.compose_path.exists())
    
    @patch('subprocess.run')
    def test_check_docker_compose_available(self, mock_run):
        """Test Docker Compose availability check."""
        # Mock successful docker compose version check
        mock_run.return_value = Mock(returncode=0, stdout="Docker Compose version v2.0.0")
        
        result = self.integration._check_docker_compose()
        self.assertTrue(result)
        
        # Verify the command was called
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertEqual(args[:3], ['docker', 'compose', 'version'])
    
    @patch('subprocess.run')
    def test_check_docker_compose_unavailable(self, mock_run):
        """Test Docker Compose unavailable."""
        # Mock failed docker compose check
        mock_run.side_effect = FileNotFoundError("docker not found")
        
        result = self.integration._check_docker_compose()
        self.assertFalse(result)
    
    @patch('subprocess.run')
    def test_get_compose_command_new_version(self, mock_run):
        """Test getting docker compose command (new version)."""
        # Mock successful docker compose version check
        mock_run.return_value = Mock(returncode=0, stdout="Docker Compose version v2.0.0")
        
        cmd = self.integration._get_compose_command()
        self.assertEqual(cmd, ['docker', 'compose'])
    
    @patch('subprocess.run')
    def test_get_compose_command_legacy_version(self, mock_run):
        """Test getting docker-compose command (legacy version)."""
        # Mock failed docker compose but successful docker-compose
        def side_effect(*args, **kwargs):
            if args[0][:3] == ['docker', 'compose', 'version']:
                return Mock(returncode=1, stderr="command not found")
            elif args[0][:2] == ['docker-compose', '--version']:
                return Mock(returncode=0, stdout="docker-compose version 1.29.0")
            else:
                raise FileNotFoundError()
        
        mock_run.side_effect = side_effect
        
        cmd = self.integration._get_compose_command()
        self.assertEqual(cmd, ['docker-compose'])
    
    @patch('subprocess.run')
    def test_get_compose_command_unavailable(self, mock_run):
        """Test getting compose command when unavailable."""
        # Mock both commands failing
        mock_run.side_effect = FileNotFoundError("command not found")
        
        with self.assertRaises(DockerComposeError):
            self.integration._get_compose_command()
    
    def test_check_env_file_exists(self):
        """Test environment file existence check."""
        # Create test env file
        env_file = ".env.test"
        env_path = Path(self.temp_dir) / env_file
        env_path.write_text("TEST_VAR=test_value\n")
        
        result = self.integration._check_env_file(env_file)
        self.assertTrue(result)
    
    def test_check_env_file_missing(self):
        """Test environment file missing."""
        result = self.integration._check_env_file(".env.missing")
        self.assertFalse(result)
    
    def test_check_env_file_none(self):
        """Test environment file check with None."""
        result = self.integration._check_env_file(None)
        self.assertTrue(result)
    
    @patch.object(DockerComposeIntegration, '_check_docker_compose')
    @patch.object(DockerComposeIntegration, '_run_compose_command')
    def test_start_containers_success(self, mock_run_command, mock_check_compose):
        """Test successful container start."""
        # Mock prerequisites
        mock_check_compose.return_value = True
        mock_run_command.return_value = Mock(
            returncode=0,
            stdout="Container started successfully",
            stderr=""
        )
        
        result = self.integration.start_containers(
            services=['test-service'],
            health_check=False  # Skip health check for this test
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['services'], ['test-service'])
        self.assertIn('started successfully', result['message'])
    
    @patch.object(DockerComposeIntegration, '_check_docker_compose')
    @patch.object(DockerComposeIntegration, '_run_compose_command')
    def test_start_containers_with_build(self, mock_run_command, mock_check_compose):
        """Test container start with build."""
        # Mock prerequisites
        mock_check_compose.return_value = True
        mock_run_command.return_value = Mock(
            returncode=0,
            stdout="Build and start successful",
            stderr=""
        )
        
        result = self.integration.start_containers(
            services=['test-service'],
            build=True,
            health_check=False
        )
        
        self.assertTrue(result['success'])
        # Should have called build and up commands
        self.assertEqual(mock_run_command.call_count, 2)
    
    @patch.object(DockerComposeIntegration, '_check_docker_compose')
    @patch.object(DockerComposeIntegration, '_run_compose_command')
    def test_start_containers_failure(self, mock_run_command, mock_check_compose):
        """Test container start failure."""
        # Mock prerequisites
        mock_check_compose.return_value = True
        mock_run_command.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="Container start failed"
        )
        
        with self.assertRaises(DockerComposeError):
            self.integration.start_containers(services=['test-service'])
    
    @patch.object(DockerComposeIntegration, '_check_docker_compose')
    @patch.object(DockerComposeIntegration, '_run_compose_command')
    def test_stop_containers_success(self, mock_run_command, mock_check_compose):
        """Test successful container stop."""
        # Mock prerequisites
        mock_check_compose.return_value = True
        mock_run_command.return_value = Mock(
            returncode=0,
            stdout="Containers stopped successfully",
            stderr=""
        )
        
        result = self.integration.stop_containers(
            services=['test-service'],
            cleanup=False
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['services'], ['test-service'])
        self.assertFalse(result['cleanup'])
    
    @patch.object(DockerComposeIntegration, '_check_docker_compose')
    @patch.object(DockerComposeIntegration, '_run_compose_command')
    def test_stop_containers_with_cleanup(self, mock_run_command, mock_check_compose):
        """Test container stop with cleanup."""
        # Mock prerequisites
        mock_check_compose.return_value = True
        mock_run_command.return_value = Mock(
            returncode=0,
            stdout="Containers stopped and removed",
            stderr=""
        )
        
        result = self.integration.stop_containers(
            cleanup=True,
            remove_volumes=True
        )
        
        self.assertTrue(result['success'])
        self.assertTrue(result['cleanup'])
        
        # Verify down command was used
        mock_run_command.assert_called_once()
        args = mock_run_command.call_args[0][0]
        self.assertIn('down', args)
        self.assertIn('-v', args)
    
    @patch.object(DockerComposeIntegration, '_check_docker_compose')
    @patch.object(DockerComposeIntegration, '_run_compose_command')
    def test_get_container_status_success(self, mock_run_command, mock_check_compose):
        """Test getting container status."""
        # Mock prerequisites
        mock_check_compose.return_value = True
        mock_run_command.return_value = Mock(
            returncode=0,
            stdout='{"Name": "test-container", "State": "running", "Health": "healthy"}',
            stderr=""
        )
        
        result = self.integration.get_container_status()
        
        self.assertTrue(result['success'])
        self.assertEqual(result['count'], 1)
        self.assertEqual(len(result['containers']), 1)
    
    def test_cfngin_hooks(self):
        """Test CFNgin hook functions."""
        # Mock context
        mock_context = Mock()
        
        # Test start hook
        with patch.object(DockerComposeIntegration, 'start_containers') as mock_start:
            mock_start.return_value = {'success': True, 'message': 'Started'}
            
            result = start_containers_hook(
                context=mock_context,
                compose_file="docker-compose.yml",
                services=['test-service']
            )
            
            self.assertTrue(result['success'])
            mock_start.assert_called_once()
        
        # Test stop hook
        with patch.object(DockerComposeIntegration, 'stop_containers') as mock_stop:
            mock_stop.return_value = {'success': True, 'message': 'Stopped'}
            
            result = stop_containers_hook(
                context=mock_context,
                compose_file="docker-compose.yml",
                cleanup=True
            )
            
            self.assertTrue(result['success'])
            mock_stop.assert_called_once()


class TestDockerComposeIntegrationLive(unittest.TestCase):
    """Live tests that require Docker to be available."""
    
    def setUp(self):
        """Set up live test environment."""
        # Skip if Docker is not available
        try:
            import subprocess
            result = subprocess.run(['docker', '--version'], capture_output=True, timeout=5)
            if result.returncode != 0:
                self.skipTest("Docker not available")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self.skipTest("Docker not available")
        
        self.temp_dir = tempfile.mkdtemp()
        self.compose_file = "docker-compose.yml"
        self.compose_path = Path(self.temp_dir) / self.compose_file
        
        # Create a minimal docker-compose.yml for testing
        compose_content = """
version: '3.8'
services:
  test-nginx:
    image: nginx:alpine
    ports:
      - "18080:80"
    healthcheck:
      test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost:80"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 10s
"""
        self.compose_path.write_text(compose_content)
        
        self.integration = DockerComposeIntegration(
            compose_file=self.compose_file,
            working_directory=self.temp_dir
        )
    
    def tearDown(self):
        """Clean up live test environment."""
        # Stop any running containers
        try:
            self.integration.stop_containers(cleanup=True)
        except:
            pass
        
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_live_docker_compose_check(self):
        """Test live Docker Compose availability check."""
        result = self.integration._check_docker_compose()
        self.assertTrue(result, "Docker Compose should be available for live tests")
    
    def test_live_get_compose_command(self):
        """Test live compose command detection."""
        cmd = self.integration._get_compose_command()
        self.assertIn(cmd, [['docker', 'compose'], ['docker-compose']])
    
    def test_live_container_lifecycle(self):
        """Test live container start/stop lifecycle."""
        # Start containers
        result = self.integration.start_containers(
            services=['test-nginx'],
            health_check=True,
            wait_timeout=60
        )
        self.assertTrue(result['success'], f"Container start failed: {result}")
        
        # Check status
        status = self.integration.get_container_status()
        self.assertTrue(status['success'])
        self.assertGreater(status['count'], 0)
        
        # Stop containers
        result = self.integration.stop_containers(
            services=['test-nginx'],
            cleanup=True
        )
        self.assertTrue(result['success'], f"Container stop failed: {result}")


def main():
    """Run the tests."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add unit tests (always run)
    suite.addTests(loader.loadTestsFromTestCase(TestDockerComposeIntegration))
    
    # Add live tests only if --live flag is provided
    if '--live' in sys.argv:
        suite.addTests(loader.loadTestsFromTestCase(TestDockerComposeIntegrationLive))
        sys.argv.remove('--live')
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return appropriate exit code
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    exit(main())