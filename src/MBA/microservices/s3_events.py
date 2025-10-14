"""
S3 event handler for CSV ingestion triggers.

This module provides event handlers for S3 PutObject events that trigger
automatic CSV ingestion into RDS. Can be used directly or deployed as AWS Lambda.

Module Input:
    - S3 event notifications (PutObject)
    - S3 bucket and key information
    - Lambda context (when deployed)

Module Output:
    - Ingestion results for processed files
    - Error reports for failed ingestions
    - CloudWatch logs for monitoring
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional
import traceback

import boto3
from botocore.exceptions import ClientError

from MBA.core.logging_config import get_logger, setup_root_logger
from MBA.core.exceptions import DataIngestionError, FileDiscoveryError
from MBA.core.settings import settings
from MBA.services.ingestion.orchestrator import CSVIngestor
from MBA.services.database.client import RDSClient

# Setup logging
setup_root_logger()
logger = get_logger(__name__)


class S3EventHandler:
    """
    Handler for S3 PutObject events to trigger CSV ingestion.
    
    Processes S3 event notifications, downloads CSV files to temporary
    storage, and orchestrates ingestion into RDS. Suitable for use
    in AWS Lambda or as a standalone event processor.
    
    Attributes:
        s3_client: Boto3 S3 client
        csv_ingestor (CSVIngestor): Ingestion orchestrator
        csv_prefix (str): S3 prefix filter for CSV files
        temp_dir (Path): Temporary directory for downloads
        
    Thread Safety:
        Not thread-safe. Create separate instances for concurrent use.
    """
    
    def __init__(
        self,
        csv_prefix: Optional[str] = None,
        rds_client: Optional[RDSClient] = None
    ):
        """
        Initialize S3 event handler.
        
        Args:
            csv_prefix (Optional[str]): S3 prefix filter (default: from settings)
            rds_client (Optional[RDSClient]): Database client (creates new if None)
            
        Side Effects:
            - Creates boto3 S3 client
            - Initializes CSV ingestor
            - Logs initialization
        """
        self.csv_prefix = csv_prefix or os.environ.get('CSV_PREFIX', 'mba/csv/')
        
        # CRITICAL FIX: Detect if running in Lambda
        is_lambda = 'AWS_EXECUTION_ENV' in os.environ or 'AWS_LAMBDA_FUNCTION_NAME' in os.environ
        
        if is_lambda:
            # In Lambda: NEVER use explicit credentials - use execution role automatically
            logger.info("Running in AWS Lambda - using execution role")
            session = boto3.Session(region_name=os.environ.get('AWS_REGION', 'us-east-1'))
        else:
            # Running locally: use credentials from settings if available
            logger.info("Running locally - using credentials from settings")
            session_kwargs = {'region_name': settings.aws_default_region}
            
            if settings.aws_profile:
                session_kwargs["profile_name"] = settings.aws_profile
            elif settings.aws_access_key_id and settings.aws_secret_access_key:
                session_kwargs["aws_access_key_id"] = settings.aws_access_key_id
                session_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
            
            session = boto3.Session(**session_kwargs)
        
        self.s3_client = session.client("s3")
        
        # Initialize ingestion components
        self.csv_ingestor = CSVIngestor(rds_client=rds_client)
        
        # Temporary directory for downloads
        self.temp_dir = Path(tempfile.gettempdir()) / "mba_s3_events"
        self.temp_dir.mkdir(exist_ok=True)
        
        logger.info(
            f"S3EventHandler initialized: prefix={self.csv_prefix}, "
            f"temp_dir={self.temp_dir}"
        )
    
    def is_csv_file(self, s3_key: str) -> bool:
        """
        Check if S3 key represents a CSV file in monitored prefix.
        
        Args:
            s3_key (str): S3 object key
            
        Returns:
            bool: True if key is a CSV in the monitored prefix
        """
        # Check prefix
        if not s3_key.startswith(self.csv_prefix):
            return False
        
        # Check extension
        if not s3_key.lower().endswith('.csv'):
            return False
        
        # Ignore directories
        if s3_key.endswith('/'):
            return False
        
        return True
    
    def download_csv(self, bucket: str, key: str) -> Path:
        """
        Download CSV file from S3 to temporary storage.
        
        Args:
            bucket (str): S3 bucket name
            key (str): S3 object key
            
        Returns:
            Path: Local path to downloaded file
            
        Raises:
            FileDiscoveryError: If download fails
            
        Side Effects:
            - Downloads file to temp directory
            - Logs download progress
        """
        try:
            # Extract filename from key
            filename = Path(key).name
            local_path = self.temp_dir / filename
            
            logger.info(f"Downloading s3://{bucket}/{key} to {local_path}")
            
            # Download file
            self.s3_client.download_file(bucket, key, str(local_path))
            
            logger.info(f"Downloaded {filename} ({local_path.stat().st_size} bytes)")
            
            return local_path
            
        except ClientError as e:
            raise FileDiscoveryError(
                f"Failed to download CSV from S3: {str(e)}",
                details={"bucket": bucket, "key": key}
            )
        except Exception as e:
            raise FileDiscoveryError(
                f"Unexpected error downloading CSV: {str(e)}",
                details={"bucket": bucket, "key": key}
            )
    
    def process_s3_event(self, event_record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process single S3 event record.
        
        Extracts bucket/key from event, downloads CSV, and triggers ingestion.
        
        Args:
            event_record (Dict[str, Any]): S3 event record
            
        Returns:
            Dict[str, Any]: Processing result with keys:
                - success (bool): Processing status
                - bucket (str): S3 bucket
                - key (str): S3 object key
                - ingestion_results (Dict): Ingestion statistics (if successful)
                - error (str): Error message (if failed)
                
        Side Effects:
            - Downloads file from S3
            - Ingests data to RDS
            - Cleans up temporary files
            - Logs processing
        """
        local_file = None
        
        try:
            # Extract S3 information
            s3_info = event_record['s3']
            bucket = s3_info['bucket']['name']
            key = s3_info['object']['key']
            
            logger.info(f"Processing S3 event: s3://{bucket}/{key}")
            
            # Check if this is a CSV we should process
            if not self.is_csv_file(key):
                logger.info(f"Skipping non-CSV or filtered file: {key}")
                return {
                    "success": True,
                    "bucket": bucket,
                    "key": key,
                    "skipped": True,
                    "reason": "Not a CSV in monitored prefix"
                }
            
            # Download CSV from S3
            local_file = self.download_csv(bucket, key)
            
            # Ingest CSV to RDS
            ingestion_results = self.csv_ingestor.ingest_csv(local_file)
            
            return {
                "success": True,
                "bucket": bucket,
                "key": key,
                "ingestion_results": ingestion_results
            }
            
        except Exception as e:
            logger.error(f"Failed to process S3 event: {str(e)}")
            logger.debug(traceback.format_exc())
            
            return {
                "success": False,
                "bucket": event_record.get('s3', {}).get('bucket', {}).get('name'),
                "key": event_record.get('s3', {}).get('object', {}).get('key'),
                "error": str(e),
                "error_type": type(e).__name__
            }
        
        finally:
            # Cleanup temporary file
            if local_file and local_file.exists():
                try:
                    local_file.unlink()
                    logger.debug(f"Cleaned up temporary file: {local_file}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup {local_file}: {e}")
    
    def handle_events(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle S3 event notification with multiple records.
        
        Processes all records in S3 event notification, handling
        each CSV file independently.
        
        Args:
            event (Dict[str, Any]): S3 event notification (Lambda format)
            
        Returns:
            Dict[str, Any]: Batch processing results with keys:
                - total_records (int): Number of event records
                - successful (int): Successfully processed
                - failed (int): Failed processing
                - skipped (int): Skipped files
                - results (List[Dict]): Individual results
                
        Example S3 Event Structure:
            {
                "Records": [
                    {
                        "eventName": "ObjectCreated:Put",
                        "s3": {
                            "bucket": {"name": "my-bucket"},
                            "object": {"key": "csv/data.csv"}
                        }
                    }
                ]
            }
        """
        logger.info(f"Received S3 event with {len(event.get('Records', []))} records")
        
        records = event.get('Records', [])
        
        if not records:
            logger.warning("No records in S3 event")
            return {
                "total_records": 0,
                "successful": 0,
                "failed": 0,
                "skipped": 0,
                "results": []
            }
        
        results = []
        successful = 0
        failed = 0
        skipped = 0
        
        for idx, record in enumerate(records, 1):
            logger.info(f"Processing record {idx}/{len(records)}")
            
            result = self.process_s3_event(record)
            results.append(result)
            
            if result.get('skipped'):
                skipped += 1
            elif result['success']:
                successful += 1
            else:
                failed += 1
        
        summary = {
            "total_records": len(records),
            "successful": successful,
            "failed": failed,
            "skipped": skipped,
            "results": results
        }
        
        logger.info(
            f"Event processing complete: {successful} successful, "
            f"{failed} failed, {skipped} skipped"
        )
        
        return summary


# Lambda handler function
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler for S3 events.
    
    Entry point for Lambda function that processes S3 PutObject events
    and triggers CSV ingestion.
    
    Args:
        event (Dict[str, Any]): Lambda event (S3 notification)
        context (Any): Lambda context object
        
    Returns:
        Dict[str, Any]: Processing results
        
    Side Effects:
        - Processes S3 events
        - Ingests CSV data to RDS
        - Logs to CloudWatch
        
    Example Lambda Configuration:
        - Runtime: Python 3.11+
        - Handler: MBA.microservices.s3_events.lambda_handler
        - Trigger: S3 bucket PutObject events
        - Environment: RDS connection parameters
        - Timeout: 5 minutes (adjust based on CSV sizes)
        - Memory: 512 MB (adjust based on CSV sizes)
    """
    logger.info(f"Lambda invoked: request_id={context.aws_request_id}")
    logger.debug(f"Event: {json.dumps(event)}")
    
    try:
        handler = S3EventHandler()
        results = handler.handle_events(event)
        
        logger.info(f"Lambda execution complete: {results['successful']} successful")
        
        return {
            "statusCode": 200,
            "body": json.dumps(results)
        }
        
    except Exception as e:
        logger.error(f"Lambda execution failed: {str(e)}")
        logger.debug(traceback.format_exc())
        
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": str(e),
                "error_type": type(e).__name__
            })
        }


# Standalone execution for local testing
def main():
    """
    Test S3 event handler with sample event.
    
    For local development and testing without deploying to Lambda.
    
    Side Effects:
        - Processes test S3 event
        - Prints results to console
    """
    # Sample S3 event for testing
    test_event = {
        "Records": [
            {
                "eventVersion": "2.1",
                "eventName": "ObjectCreated:Put",
                "s3": {
                    "bucket": {
                        "name": settings.s3_bucket_mba
                    },
                    "object": {
                        "key": f"{settings.csv_prefix}test_data.csv"
                    }
                }
            }
        ]
    }
    
    logger.info("Running S3 event handler test")
    
    handler = S3EventHandler()
    results = handler.handle_events(test_event)
    
    print("\nResults:")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()