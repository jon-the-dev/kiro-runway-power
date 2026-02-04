#!/usr/bin/env python3
"""
Unit tests for env_file_generator hook.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from env_file_generator import EnvFileGenerator, EnvFileGeneratorError, cfngin_hook


class TestEnvFileGenerator(unittest.TestCase):
    """Test cases for EnvFileGenerator class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_file = Path(self.temp_dir) / '.env.test'
        
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_basic_env_generation(self):
        """Test basic environment file generation."""
        variables = {
            'NEXT_PUBLIC_API_URL': 'https://api.example.com',
            'DATABASE_URL': 'postgres://localhost:5432/db',
            'NODE_ENV': 'production'
        }
        
        generator = EnvFileGenerator(
            output_file=str(self.temp_file),
            variables=variables,
            overwrite=True
        )
        
        success = generator.write_env_file()
        self.assertTrue(success)
        self.assertTrue(self.temp_file.exists())
        
        # Check file content
        content = self.temp_file.read_text()
        self.assertIn('NEXT_PUBLIC_API_URL=https://api.example.com', content)
        self.assertIn('DATABASE_URL=postgres://localhost:5432/db', content)
        self.assertIn('NODE_ENV=production', content)
        self.assertIn('# Environment variables generated on', content)
    
    def test_quoted_values(self):
        """Test handling of values that need quoting."""
        variables = {
            'VALUE_WITH_SPACES': 'hello world',
            'EMPTY_VALUE': '',
            'VALUE_WITH_QUOTES': 'say "hello"',
            'MULTILINE_VALUE': 'line1\nline2'
        }
        
        generator = EnvFileGenerator(
            output_file=str(self.temp_file),
            variables=variables,
            overwrite=True
        )
        
        success = generator.write_env_file()
        self.assertTrue(success)
        
        content = self.temp_file.read_text()
        self.assertIn('VALUE_WITH_SPACES="hello world"', content)
        self.assertIn('EMPTY_VALUE=""', content)
        self.assertIn("VALUE_WITH_QUOTES='say \"hello\"'", content)
        self.assertIn("MULTILINE_VALUE='line1\nline2'", content)
    
    def test_overwrite_protection(self):
        """Test overwrite protection."""
        # Create existing file
        self.temp_file.write_text('EXISTING=value')
        
        variables = {'NEW_VAR': 'new_value'}
        
        generator = EnvFileGenerator(
            output_file=str(self.temp_file),
            variables=variables,
            overwrite=False
        )
        
        with self.assertRaises(EnvFileGeneratorError):
            generator.write_env_file()
    
    def test_backup_creation(self):
        """Test backup file creation."""
        # Create existing file
        self.temp_file.write_text('EXISTING=value')
        
        variables = {'NEW_VAR': 'new_value'}
        
        generator = EnvFileGenerator(
            output_file=str(self.temp_file),
            variables=variables,
            overwrite=True,
            create_backup=True
        )
        
        success = generator.write_env_file()
        self.assertTrue(success)
        
        # Check backup was created
        backup_files = list(self.temp_file.parent.glob('*.backup_*'))
        self.assertEqual(len(backup_files), 1)
        
        # Check backup content
        backup_content = backup_files[0].read_text()
        self.assertEqual(backup_content, 'EXISTING=value')
    
    def test_directory_creation(self):
        """Test automatic directory creation."""
        nested_file = Path(self.temp_dir) / 'nested' / 'dir' / '.env'
        
        variables = {'TEST_VAR': 'test_value'}
        
        generator = EnvFileGenerator(
            output_file=str(nested_file),
            variables=variables,
            overwrite=True
        )
        
        success = generator.write_env_file()
        self.assertTrue(success)
        self.assertTrue(nested_file.exists())
    
    def test_invalid_variables(self):
        """Test validation of invalid variable names."""
        invalid_variables = {
            '': 'empty_key',
            'INVALID SPACE': 'value',
            'INVALID@SYMBOL': 'value'
        }
        
        generator = EnvFileGenerator(
            output_file=str(self.temp_file),
            variables=invalid_variables,
            overwrite=True
        )
        
        with self.assertRaises(EnvFileGeneratorError):
            generator.write_env_file()
    
    def test_empty_variables(self):
        """Test handling of empty variables dictionary."""
        generator = EnvFileGenerator(
            output_file=str(self.temp_file),
            variables={},
            overwrite=True
        )
        
        with self.assertRaises(EnvFileGeneratorError):
            generator.write_env_file()
    
    def test_variable_sorting(self):
        """Test that variables are sorted in output."""
        variables = {
            'ZEBRA': 'last',
            'ALPHA': 'first',
            'BETA': 'middle'
        }
        
        generator = EnvFileGenerator(
            output_file=str(self.temp_file),
            variables=variables,
            overwrite=True
        )
        
        success = generator.write_env_file()
        self.assertTrue(success)
        
        content = self.temp_file.read_text()
        lines = [line for line in content.split('\n') if '=' in line]
        
        # Check order
        self.assertTrue(lines[0].startswith('ALPHA='))
        self.assertTrue(lines[1].startswith('BETA='))
        self.assertTrue(lines[2].startswith('ZEBRA='))


class TestCFNginHook(unittest.TestCase):
    """Test cases for CFNgin hook function."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_file = Path(self.temp_dir) / '.env.test'
        self.mock_context = MagicMock()
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_successful_hook_execution(self):
        """Test successful CFNgin hook execution."""
        kwargs = {
            'output_file': str(self.temp_file),
            'variables': {
                'NEXT_PUBLIC_API_URL': 'https://api.example.com',
                'NODE_ENV': 'production'
            },
            'overwrite': True
        }
        
        result = cfngin_hook(self.mock_context, **kwargs)
        self.assertTrue(result)
        self.assertTrue(self.temp_file.exists())
    
    def test_missing_output_file(self):
        """Test hook with missing output_file parameter."""
        kwargs = {
            'variables': {'TEST': 'value'}
        }
        
        result = cfngin_hook(self.mock_context, **kwargs)
        self.assertFalse(result)
    
    def test_missing_variables(self):
        """Test hook with missing variables parameter."""
        kwargs = {
            'output_file': str(self.temp_file)
        }
        
        result = cfngin_hook(self.mock_context, **kwargs)
        self.assertFalse(result)
    
    def test_hook_with_cfngin_outputs(self):
        """Test hook with simulated CFNgin stack outputs."""
        # Simulate CFNgin variable resolution
        kwargs = {
            'output_file': str(self.temp_file),
            'variables': {
                'NEXT_PUBLIC_API_URL': 'https://api-dev.example.com',
                'NEXT_PUBLIC_USER_POOL_ID': 'us-east-1_ABC123DEF',
                'NEXT_PUBLIC_USER_POOL_CLIENT_ID': 'abcdef123456789',
                'ENVIRONMENT': 'dev'
            },
            'overwrite': True,
            'verbose': True
        }
        
        result = cfngin_hook(self.mock_context, **kwargs)
        self.assertTrue(result)
        
        content = self.temp_file.read_text()
        self.assertIn('NEXT_PUBLIC_API_URL=https://api-dev.example.com', content)
        self.assertIn('NEXT_PUBLIC_USER_POOL_ID=us-east-1_ABC123DEF', content)
        self.assertIn('ENVIRONMENT=dev', content)


class TestCommandLineInterface(unittest.TestCase):
    """Test cases for command line interface."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_file = Path(self.temp_dir) / '.env.test'
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('sys.argv')
    def test_cli_basic_usage(self, mock_argv):
        """Test basic CLI usage."""
        mock_argv.__getitem__.side_effect = [
            'env_file_generator.py',
            '--output-file', str(self.temp_file),
            '--variables', 'TEST_VAR=test_value', 'NODE_ENV=production',
            '--overwrite'
        ]
        
        from env_file_generator import main
        
        with patch('argparse.ArgumentParser.parse_args') as mock_parse:
            mock_args = MagicMock()
            mock_args.output_file = str(self.temp_file)
            mock_args.variables = ['TEST_VAR=test_value', 'NODE_ENV=production']
            mock_args.json_variables = None
            mock_args.overwrite = True
            mock_args.create_backup = True
            mock_args.no_backup = False
            mock_args.verbose = False
            mock_parse.return_value = mock_args
            
            result = main()
            self.assertEqual(result, 0)
    
    @patch('sys.argv')
    def test_cli_json_variables(self, mock_argv):
        """Test CLI with JSON variables."""
        from env_file_generator import main
        
        with patch('argparse.ArgumentParser.parse_args') as mock_parse:
            mock_args = MagicMock()
            mock_args.output_file = str(self.temp_file)
            mock_args.variables = []
            mock_args.json_variables = '{"API_URL": "https://api.example.com", "DEBUG": "true"}'
            mock_args.overwrite = True
            mock_args.create_backup = True
            mock_args.no_backup = False
            mock_args.verbose = False
            mock_parse.return_value = mock_args
            
            result = main()
            self.assertEqual(result, 0)
            
            content = self.temp_file.read_text()
            self.assertIn('API_URL=https://api.example.com', content)
            self.assertIn('DEBUG=true', content)


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)
