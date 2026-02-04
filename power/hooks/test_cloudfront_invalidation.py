#!/usr/bin/env python3
"""
Test script for CloudFront invalidation hook.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add the hooks directory to the path
sys.path.insert(0, os.path.dirname(__file__))

from cloudfront_invalidation import (
    create_invalidation,
    wait_for_invalidation,
    cfngin_hook,
    CloudFrontInvalidationError
)


class TestCloudFrontInvalidation(unittest.TestCase):
    """Test cases for CloudFront invalidation hook."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.distribution_id = "E1234567890ABC"
        self.invalidation_id = "I1234567890DEF"
        
    @patch('cloudfront_invalidation.boto3.client')
    def test_create_invalidation_success(self, mock_boto3_client):
        """Test successful invalidation creation."""
        # Mock CloudFront client
        mock_client = Mock()
        mock_boto3_client.return_value = mock_client
        
        # Mock response
        mock_response = {
            'Invalidation': {
                'Id': self.invalidation_id,
                'Status': 'InProgress'
            }
        }
        mock_client.create_invalidation.return_value = mock_response
        
        # Test the function
        result = create_invalidation(self.distribution_id)
        
        # Assertions
        self.assertEqual(result['invalidation_id'], self.invalidation_id)
        self.assertEqual(result['status'], 'InProgress')
        self.assertEqual(result['distribution_id'], self.distribution_id)
        self.assertEqual(result['paths'], ['/*'])
        
        # Verify the client was called correctly
        mock_client.create_invalidation.assert_called_once()
        call_args = mock_client.create_invalidation.call_args[1]
        self.assertEqual(call_args['DistributionId'], self.distribution_id)
        self.assertEqual(call_args['InvalidationBatch']['Paths']['Items'], ['/*'])
    
    @patch('cloudfront_invalidation.boto3.client')
    def test_create_invalidation_custom_paths(self, mock_boto3_client):
        """Test invalidation creation with custom paths."""
        # Mock CloudFront client
        mock_client = Mock()
        mock_boto3_client.return_value = mock_client
        
        # Mock response
        mock_response = {
            'Invalidation': {
                'Id': self.invalidation_id,
                'Status': 'InProgress'
            }
        }
        mock_client.create_invalidation.return_value = mock_response
        
        # Test with custom paths
        custom_paths = ['/api/*', '/assets/*', '/index.html']
        result = create_invalidation(self.distribution_id, custom_paths)
        
        # Assertions
        self.assertEqual(result['paths'], custom_paths)
        
        # Verify the client was called with custom paths
        call_args = mock_client.create_invalidation.call_args[1]
        self.assertEqual(call_args['InvalidationBatch']['Paths']['Items'], custom_paths)
        self.assertEqual(call_args['InvalidationBatch']['Paths']['Quantity'], len(custom_paths))
    
    @patch('cloudfront_invalidation.boto3.client')
    def test_create_invalidation_no_such_distribution(self, mock_boto3_client):
        """Test invalidation creation with non-existent distribution."""
        # Mock CloudFront client
        mock_client = Mock()
        mock_boto3_client.return_value = mock_client
        
        # Mock ClientError
        from botocore.exceptions import ClientError
        error_response = {
            'Error': {
                'Code': 'NoSuchDistribution',
                'Message': 'The specified distribution does not exist'
            }
        }
        mock_client.create_invalidation.side_effect = ClientError(error_response, 'CreateInvalidation')
        
        # Test the function
        with self.assertRaises(CloudFrontInvalidationError) as context:
            create_invalidation(self.distribution_id)
        
        self.assertIn("not found", str(context.exception))
    
    @patch('cloudfront_invalidation.boto3.client')
    @patch('cloudfront_invalidation.time.sleep')
    def test_wait_for_invalidation_success(self, mock_sleep, mock_boto3_client):
        """Test waiting for invalidation completion."""
        # Mock CloudFront client
        mock_client = Mock()
        mock_boto3_client.return_value = mock_client
        
        # Mock responses - first InProgress, then Completed
        mock_responses = [
            {'Invalidation': {'Status': 'InProgress'}},
            {'Invalidation': {'Status': 'Completed'}}
        ]
        mock_client.get_invalidation.side_effect = mock_responses
        
        # Test the function
        result = wait_for_invalidation(self.distribution_id, self.invalidation_id, timeout=60)
        
        # Assertions
        self.assertTrue(result)
        self.assertEqual(mock_client.get_invalidation.call_count, 2)
        mock_sleep.assert_called_once_with(30)
    
    def test_cfngin_hook_missing_distribution_id(self):
        """Test CFNgin hook with missing distribution_id."""
        provider = Mock()
        context = Mock()
        
        with self.assertRaises(ValueError) as context:
            cfngin_hook(provider, context)
        
        self.assertIn("distribution_id parameter is required", str(context.exception))
    
    @patch('cloudfront_invalidation.create_invalidation')
    def test_cfngin_hook_success(self, mock_create_invalidation):
        """Test successful CFNgin hook execution."""
        # Mock the create_invalidation function
        mock_result = {
            'invalidation_id': self.invalidation_id,
            'status': 'InProgress',
            'distribution_id': self.distribution_id,
            'paths': ['/*'],
            'caller_reference': 'test-ref'
        }
        mock_create_invalidation.return_value = mock_result
        
        # Test the hook
        provider = Mock()
        context = Mock()
        result = cfngin_hook(provider, context, distribution_id=self.distribution_id)
        
        # Assertions
        self.assertEqual(result, mock_result)
        mock_create_invalidation.assert_called_once_with(self.distribution_id, ['/*'])
    
    @patch('cloudfront_invalidation.create_invalidation')
    @patch('cloudfront_invalidation.wait_for_invalidation')
    def test_cfngin_hook_with_wait(self, mock_wait, mock_create_invalidation):
        """Test CFNgin hook with wait option."""
        # Mock functions
        mock_result = {
            'invalidation_id': self.invalidation_id,
            'status': 'InProgress',
            'distribution_id': self.distribution_id,
            'paths': ['/*'],
            'caller_reference': 'test-ref'
        }
        mock_create_invalidation.return_value = mock_result
        mock_wait.return_value = True
        
        # Test the hook with wait=True
        provider = Mock()
        context = Mock()
        result = cfngin_hook(
            provider, 
            context, 
            distribution_id=self.distribution_id,
            wait=True,
            timeout=300
        )
        
        # Assertions
        self.assertTrue(result['completed'])
        mock_wait.assert_called_once_with(self.distribution_id, self.invalidation_id, 300)


if __name__ == '__main__':
    unittest.main()
