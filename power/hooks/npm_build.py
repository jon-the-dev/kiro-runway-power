#!/usr/bin/env python3
"""
Custom hooks for CMM Registration Site deployment.
"""

import os
import subprocess
import sys
import logging
import time
import boto3
from pathlib import Path
from typing import Any, Dict, List

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def build_and_sync_app(context: Dict[str, Any], provider: Any, **kwargs) -> bool:
    """
    Hook to build Next.js app and sync to S3 bucket.

    Args:
        context: CFNgin context containing stack information
        provider: AWS provider instance
        **kwargs: Additional arguments including:
            - bucket_name: S3 bucket name (from stack output)
            - app_path: Path to the app directory (default: './app')
            - environment: Environment name for .env file selection

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get parameters
        bucket_name = kwargs.get("bucket_name")
        app_path = kwargs.get("app_path", "./app")
        environment = kwargs.get("environment", "dev")

        if not bucket_name:
            logger.error("bucket_name parameter is required")
            return False

        logger.info(f"Starting build and sync process for bucket: {bucket_name}")
        logger.info(f"App path: {app_path}, Environment: {environment}")

        # Convert to absolute path
        app_dir = Path(app_path).resolve()

        if not app_dir.exists():
            logger.error(f"App directory does not exist: {app_dir}")
            return False

        # Change to app directory
        original_cwd = os.getcwd()
        os.chdir(app_dir)

        try:
            # Copy environment-specific .env file
            env_file_src = f".env.{environment}"
            env_file_dest = ".env.local"

            if Path(env_file_src).exists():
                logger.info(f"Copying {env_file_src} to {env_file_dest}")
                subprocess.run(["cp", env_file_src, env_file_dest], check=True)
            else:
                logger.warning(f"Environment file {env_file_src} not found, skipping")

            # Check if node_modules exists, if not run npm install
            if not Path("node_modules").exists():
                logger.info("node_modules not found, running npm install...")
                result = subprocess.run(
                    ["npm", "install"], capture_output=True, text=True
                )
                if result.returncode != 0:
                    logger.error(f"npm install failed: {result.stderr}")
                    return False
                logger.info("npm install completed successfully")

            # Run npm run build
            logger.info("Running npm run build...")
            result = subprocess.run(
                ["npm", "run", "build"], capture_output=True, text=True
            )
            if result.returncode != 0:
                logger.error(f"npm run build failed: {result.stderr}")
                return False
            logger.info("Build completed successfully")

            # Determine output directory (Next.js uses 'out' for static export)
            output_dir = Path("out")
            if not output_dir.exists():
                # Fallback to .next/static if out doesn't exist
                output_dir = Path(".next")
                if not output_dir.exists():
                    logger.error("No build output directory found (out or .next)")
                    return False

            logger.info(f"Using output directory: {output_dir}")

            # Sync to S3 with delete flag
            logger.info(f"Syncing {output_dir} to s3://{bucket_name}/")

            # Build AWS CLI sync command
            sync_cmd = [
                "aws",
                "s3",
                "sync",
                str(output_dir),
                f"s3://{bucket_name}/",
                "--delete",
                "--cache-control",
                "max-age=31536000",  # 1 year for static assets
                # '--exclude', '*.html',
                # '--exclude', '*.json'
            ]

            # Sync static assets with long cache
            result = subprocess.run(sync_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"S3 sync (static assets) failed: {result.stderr}")
                return False

            # Sync HTML and JSON files with no cache
            html_sync_cmd = [
                "aws",
                "s3",
                "sync",
                str(output_dir),
                f"s3://{bucket_name}/",
                "--delete",
                "--cache-control",
                "no-cache, no-store, must-revalidate",
                "--include",
                "*.html",
                "--include",
                "*.json",
                "--exclude",
                "*",
            ]

            result = subprocess.run(html_sync_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"S3 sync (HTML/JSON) failed: {result.stderr}")
                return False

            logger.info("S3 sync completed successfully")

            # Set proper content types for specific files
            logger.info("Setting content types...")

            # Set content-type for HTML files
            subprocess.run(
                [
                    "aws",
                    "s3",
                    "cp",
                    f"s3://{bucket_name}/",
                    f"s3://{bucket_name}/",
                    "--recursive",
                    "--exclude",
                    "*",
                    "--include",
                    "*.html",
                    "--content-type",
                    "text/html",
                    "--metadata-directive",
                    "REPLACE",
                ],
                capture_output=True,
            )

            # Set content-type for JSON files
            subprocess.run(
                [
                    "aws",
                    "s3",
                    "cp",
                    f"s3://{bucket_name}/",
                    f"s3://{bucket_name}/",
                    "--recursive",
                    "--exclude",
                    "*",
                    "--include",
                    "*.json",
                    "--content-type",
                    "application/json",
                    "--metadata-directive",
                    "REPLACE",
                ],
                capture_output=True,
            )

            logger.info("Content types set successfully")
            logger.info("Build and sync process completed successfully")
            return True

        finally:
            # Always return to original directory
            os.chdir(original_cwd)

    except Exception as e:
        logger.error(f"Build and sync failed with error: {str(e)}")
        return False


class CloudFrontInvalidation:
    """CloudFront invalidation utilities."""

    @staticmethod
    def cfngin_hook(context: Dict[str, Any], provider: Any, **kwargs) -> bool:
        """
        CFNgin hook to invalidate CloudFront distribution.

        Args:
            context: CFNgin context
            provider: AWS provider instance
            **kwargs: Additional arguments including:
                - distribution_id: CloudFront distribution ID
                - paths: List of paths to invalidate (default: ['/*'])
                - wait: Whether to wait for invalidation to complete (default: False)

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            distribution_id = kwargs.get("distribution_id")
            paths = kwargs.get("paths", ["/*"])
            wait = kwargs.get("wait", False)

            if not distribution_id:
                logger.error("distribution_id parameter is required")
                return False

            logger.info(
                f"Creating CloudFront invalidation for distribution: {distribution_id}"
            )
            logger.info(f"Paths to invalidate: {paths}")

            # Create CloudFront client
            cloudfront = boto3.client("cloudfront")

            # Create invalidation
            response = cloudfront.create_invalidation(
                DistributionId=distribution_id,
                InvalidationBatch={
                    "Paths": {"Quantity": len(paths), "Items": paths},
                    "CallerReference": f"cfngin-{int(time.time())}",
                },
            )

            invalidation_id = response["Invalidation"]["Id"]
            logger.info(f"Invalidation created with ID: {invalidation_id}")

            if wait:
                logger.info("Waiting for invalidation to complete...")
                waiter = cloudfront.get_waiter("invalidation_completed")
                waiter.wait(
                    DistributionId=distribution_id,
                    Id=invalidation_id,
                    WaiterConfig={
                        "Delay": 30,
                        "MaxAttempts": 40,  # Wait up to 20 minutes
                    },
                )
                logger.info("Invalidation completed successfully")
            else:
                logger.info("Invalidation started (not waiting for completion)")

            return True

        except Exception as e:
            logger.error(f"CloudFront invalidation failed: {str(e)}")
            return False


# Create module-level reference for backward compatibility
cloudfront_invalidation = CloudFrontInvalidation()


def cfngin_hook(context: Dict[str, Any], provider: Any, **kwargs) -> bool:
    """
    CFNgin hook wrapper for build_and_sync_app.

    This is the entry point that CFNgin will call.
    """
    return build_and_sync_app(context, provider, **kwargs)


if __name__ == "__main__":
    # For testing purposes
    import argparse

    parser = argparse.ArgumentParser(description="Build and sync Next.js app to S3")
    parser.add_argument("--bucket-name", required=True, help="S3 bucket name")
    parser.add_argument("--app-path", default="./app", help="Path to app directory")
    parser.add_argument("--environment", default="dev", help="Environment (dev/prod)")

    args = parser.parse_args()

    # Mock context and provider for testing
    mock_context = {}
    mock_provider = None

    success = build_and_sync_app(
        mock_context,
        mock_provider,
        bucket_name=args.bucket_name,
        app_path=args.app_path,
        environment=args.environment,
    )

    sys.exit(0 if success else 1)
