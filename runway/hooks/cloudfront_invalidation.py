#!/usr/bin/env python3
"""
CFNgin hook for CloudFront invalidation.

This hook can be called from Runway to invalidate CloudFront distributions.
"""

import argparse
import logging
import os
import sys
import time
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class CloudFrontInvalidationError(Exception):
    """Custom exception for CloudFront invalidation errors."""

    pass


def create_invalidation(
    distribution_id: str, paths: list = None, caller_reference: str = None
) -> Dict[str, Any]:
    """
    Create a CloudFront invalidation.

    Args:
        distribution_id: CloudFront distribution ID
        paths: List of paths to invalidate (defaults to ['/*'])
        caller_reference: Unique reference for this invalidation (auto-generated if not provided)

    Returns:
        Dict containing invalidation details

    Raises:
        CloudFrontInvalidationError: If invalidation fails
    """
    if paths is None:
        paths = ["/*"]

    if caller_reference is None:
        caller_reference = f"runway-hook-{int(time.time())}"

    try:
        cloudfront = boto3.client("cloudfront")

        logger.info(f"Creating invalidation for distribution {distribution_id}")
        logger.info(f"Paths to invalidate: {paths}")

        response = cloudfront.create_invalidation(
            DistributionId=distribution_id,
            InvalidationBatch={
                "Paths": {"Quantity": len(paths), "Items": paths},
                "CallerReference": caller_reference,
            },
        )

        invalidation_id = response["Invalidation"]["Id"]
        status = response["Invalidation"]["Status"]

        logger.info(f"Invalidation created successfully")
        logger.info(f"Invalidation ID: {invalidation_id}")
        logger.info(f"Status: {status}")

        return {
            "invalidation_id": invalidation_id,
            "status": status,
            "distribution_id": distribution_id,
            "paths": paths,
            "caller_reference": caller_reference,
        }

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]

        if error_code == "NoSuchDistribution":
            raise CloudFrontInvalidationError(
                f"Distribution {distribution_id} not found"
            )
        elif error_code == "TooManyInvalidationsInProgress":
            raise CloudFrontInvalidationError(
                f"Too many invalidations in progress for distribution {distribution_id}"
            )
        else:
            raise CloudFrontInvalidationError(
                f"AWS Error ({error_code}): {error_message}"
            )

    except NoCredentialsError:
        raise CloudFrontInvalidationError("AWS credentials not found or invalid")
    except Exception as e:
        raise CloudFrontInvalidationError(f"Unexpected error: {str(e)}")


def wait_for_invalidation(
    distribution_id: str, invalidation_id: str, timeout: int = 900
) -> bool:
    """
    Wait for invalidation to complete.

    Args:
        distribution_id: CloudFront distribution ID
        invalidation_id: Invalidation ID to wait for
        timeout: Maximum time to wait in seconds (default: 15 minutes)

    Returns:
        True if invalidation completed successfully, False if timeout

    Raises:
        CloudFrontInvalidationError: If there's an error checking status
    """
    try:
        cloudfront = boto3.client("cloudfront")
        start_time = time.time()

        logger.info(f"Waiting for invalidation {invalidation_id} to complete...")

        while time.time() - start_time < timeout:
            response = cloudfront.get_invalidation(
                DistributionId=distribution_id, Id=invalidation_id
            )

            status = response["Invalidation"]["Status"]
            logger.info(f"Invalidation status: {status}")

            if status == "Completed":
                logger.info("Invalidation completed successfully")
                return True

            time.sleep(30)  # Wait 30 seconds before checking again

        logger.warning(f"Invalidation did not complete within {timeout} seconds")
        return False

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]
        raise CloudFrontInvalidationError(
            f"Error checking invalidation status ({error_code}): {error_message}"
        )
    except Exception as e:
        raise CloudFrontInvalidationError(
            f"Unexpected error waiting for invalidation: {str(e)}"
        )


def cfngin_hook(provider: Any, context: Any, **kwargs) -> Dict[str, Any]:
    """
    CFNgin hook entry point for CloudFront invalidation.

    Args:
        provider: CFNgin provider instance
        context: CFNgin context
        **kwargs: Hook arguments including:
            - distribution_id: CloudFront distribution ID (required)
            - paths: List of paths to invalidate (optional, defaults to ['/*'])
            - wait: Whether to wait for invalidation to complete (optional, defaults to False)
            - timeout: Timeout for waiting in seconds (optional, defaults to 900)

    Returns:
        Dict containing invalidation results

    Raises:
        ValueError: If required parameters are missing
        CloudFrontInvalidationError: If invalidation fails
    """
    distribution_id = kwargs.get("distribution_id")
    if not distribution_id:
        raise ValueError("distribution_id parameter is required")

    paths = kwargs.get("paths", ["/*"])
    wait = kwargs.get("wait", False)
    timeout = kwargs.get("timeout", 900)

    logger.info(f"Cloudfront Invalidation called for distribution: {distribution_id}")

    # Create invalidation
    result = create_invalidation(distribution_id, paths)

    # Wait for completion if requested
    if wait:
        completed = wait_for_invalidation(
            distribution_id, result["invalidation_id"], timeout
        )
        result["completed"] = completed

    return result


def main():
    """Command line interface for testing the hook."""
    parser = argparse.ArgumentParser(
        description="CloudFront invalidation hook for CFNgin/Runway"
    )
    parser.add_argument("distribution_id", help="CloudFront distribution ID")
    parser.add_argument(
        "--paths", nargs="+", default=["/*"], help="Paths to invalidate (default: /*)"
    )
    parser.add_argument(
        "--wait", action="store_true", help="Wait for invalidation to complete"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=900,
        help="Timeout for waiting in seconds (default: 900)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    try:
        # Create invalidation
        result = create_invalidation(args.distribution_id, args.paths)
        print(f"Invalidation created: {result['invalidation_id']}")

        # Wait for completion if requested
        if args.wait:
            completed = wait_for_invalidation(
                args.distribution_id, result["invalidation_id"], args.timeout
            )
            if completed:
                print("Invalidation completed successfully")
            else:
                print("Invalidation did not complete within timeout")
                sys.exit(1)

    except CloudFrontInvalidationError as e:
        logger.error(f"Invalidation failed: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
