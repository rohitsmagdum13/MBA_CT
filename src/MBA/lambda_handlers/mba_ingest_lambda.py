"""
Unified Lambda handler for MBA CSV and PDF ingestion.

Routes S3 PutObject events to appropriate pipeline:
- mba/csv/*.csv → CSV ingestion to RDS
- mba/pdf/*.pdf → Textract async processing

Environment Variables Required:
    AWS_REGION, S3_BUCKET_MBA, CSV_PREFIX, PDF_PREFIX, OUTPUT_PREFIX,
    RDS_HOST, RDS_DATABASE, RDS_USERNAME, RDS_PASSWORD, RDS_PORT
"""

import json
import os
import traceback
from datetime import datetime
from typing import Dict, Any

# Core imports
from MBA.core.logging_config import get_logger, setup_root_logger
from MBA.core.exceptions import (
    TextractError, DataIngestionError, FileDiscoveryError, ConfigError
)
from MBA.core.settings import settings

# Service imports
from MBA.services.ingestion.orchestrator import CSVIngestor
from MBA.services.processing.textract_client import TextractPollingService
from MBA.services.processing.audit_writer import AuditLoggerService
from MBA.services.storage.s3_client import S3Client

# Setup logging
setup_root_logger()
logger = get_logger(__name__)


class MBALambdaRouter:
    """
    Routes S3 events to CSV or PDF processing pipelines.
    
    Handles:
    - Prefix-based routing (csv/ vs pdf/)
    - Pipeline execution with error handling
    - Audit trail generation
    - Structured logging with correlation IDs
    """
    
    def __init__(self):
        """Initialize router with service instances."""
        # Get prefixes from environment
        self.csv_prefix = os.environ.get('CSV_PREFIX', 'mba/csv/').lstrip('/')
        self.pdf_prefix = os.environ.get('PDF_PREFIX', 'mba/pdf/').lstrip('/')
        self.output_prefix = os.environ.get('OUTPUT_PREFIX', 'mba/textract-output/').lstrip('/')
        self.bucket = os.environ.get('S3_BUCKET_MBA', settings.s3_bucket_mba)
        
        # Initialize services (lazy to avoid cold start overhead)
        self._csv_ingestor = None
        self._textract_service = None
        self._audit_service = None
        self._s3_client = None
        
        logger.info(
            "MBALambdaRouter initialized",
            extra={
                "csv_prefix": self.csv_prefix,
                "pdf_prefix": self.pdf_prefix,
                "output_prefix": self.output_prefix,
                "bucket": self.bucket
            }
        )
    
    @property
    def csv_ingestor(self) -> CSVIngestor:
        """Lazy initialization of CSV ingestor."""
        if self._csv_ingestor is None:
            self._csv_ingestor = CSVIngestor()
            logger.info("CSV ingestor initialized")
        return self._csv_ingestor
    
    @property
    def textract_service(self) -> TextractPollingService:
        """Lazy initialization of Textract service."""
        if self._textract_service is None:
            self._textract_service = TextractPollingService(
                output_prefix=self.output_prefix,
                s3_bucket=self.bucket
            )
            logger.info("Textract service initialized")
        return self._textract_service
    
    @property
    def audit_service(self) -> AuditLoggerService:
        """Lazy initialization of audit service."""
        if self._audit_service is None:
            s3_client = S3Client(bucket=self.bucket, prefix="")
            self._audit_service = AuditLoggerService(s3_client=s3_client)
            logger.info("Audit service initialized")
        return self._audit_service
    
    def determine_pipeline(self, s3_key: str) -> str:
        """
        Determine which pipeline to use based on S3 key.
        
        Args:
            s3_key: S3 object key
            
        Returns:
            "csv" | "pdf" | "skip"
        """
        if s3_key.startswith(self.csv_prefix) and s3_key.lower().endswith('.csv'):
            return "csv"
        elif s3_key.startswith(self.pdf_prefix) and s3_key.lower().endswith('.pdf'):
            return "pdf"
        else:
            return "skip"
    
    def process_csv(self, bucket: str, key: str, event_time: str) -> Dict[str, Any]:
        """
        Process CSV file through ingestion pipeline.
        
        Args:
            bucket: S3 bucket name
            key: S3 object key
            event_time: Event timestamp
            
        Returns:
            Processing results with status and metrics
        """
        import tempfile
        from pathlib import Path
        
        start_time = datetime.now()
        local_file = None
        
        try:
            logger.info(f"Starting CSV ingestion: s3://{bucket}/{key}")
            
            # Download file to /tmp
            s3_client = S3Client(bucket=bucket, prefix="")
            filename = Path(key).name
            local_file = Path(tempfile.gettempdir()) / filename
            
            # Download using boto3 directly (simpler for Lambda)
            import boto3
            s3 = boto3.client('s3')
            s3.download_file(bucket, key, str(local_file))
            
            logger.info(f"Downloaded CSV to {local_file} ({local_file.stat().st_size} bytes)")
            
            # Run ingestion
            result = self.csv_ingestor.ingest_csv(local_file)
            
            # Calculate duration
            duration = (datetime.now() - start_time).total_seconds()
            
            # Build audit payload
            audit_payload = {
                "timestamp": event_time,
                "pipeline": "csv",
                "s3_key": key,
                "s3_bucket": bucket,
                "status": "success" if result.get("success") else "failed",
                "table_name": result.get("table_name"),
                "rows_loaded": result.get("load_results", {}).get("rows_loaded", 0),
                "rows_failed": result.get("load_results", {}).get("rows_failed", 0),
                "duration_seconds": duration,
                "errors": result.get("load_results", {}).get("errors", [])[:5]  # First 5 errors
            }
            
            # Write audit
            audit_key = f"mba/audit/csv/{datetime.now().strftime('%Y-%m-%d')}/{filename}.json"
            self.audit_service.write_audit(audit_key.rsplit('/', 1)[0] + '/', audit_payload)
            
            logger.info(
                f"CSV ingestion completed: {result.get('load_results', {}).get('rows_loaded', 0)} rows in {duration:.2f}s"
            )
            
            return {
                "success": result.get("success", False),
                "pipeline": "csv",
                "audit": audit_payload
            }
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            error_msg = str(e)
            
            logger.error(f"CSV ingestion failed: {error_msg}", exc_info=True)
            
            # Write failure audit
            audit_payload = {
                "timestamp": event_time,
                "pipeline": "csv",
                "s3_key": key,
                "s3_bucket": bucket,
                "status": "failed",
                "error": error_msg,
                "error_type": type(e).__name__,
                "duration_seconds": duration
            }
            
            try:
                audit_key = f"mba/audit/csv/{datetime.now().strftime('%Y-%m-%d')}/failed-{Path(key).name}.json"
                self.audit_service.write_audit(audit_key.rsplit('/', 1)[0] + '/', audit_payload)
            except Exception as audit_err:
                logger.warning(f"Failed to write failure audit: {audit_err}")
            
            return {
                "success": False,
                "pipeline": "csv",
                "error": error_msg,
                "audit": audit_payload
            }
            
        finally:
            # Cleanup
            if local_file and local_file.exists():
                try:
                    local_file.unlink()
                    logger.debug(f"Cleaned up temporary file: {local_file}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup {local_file}: {e}")
    
    def process_pdf(self, bucket: str, key: str, event_time: str) -> Dict[str, Any]:
        """
        Process PDF file through Textract pipeline.
        
        Args:
            bucket: S3 bucket name
            key: S3 object key
            event_time: Event timestamp
            
        Returns:
            Processing results with status and Textract job details
        """
        from pathlib import Path
        
        start_time = datetime.now()
        job_id = None
        job_type = None
        
        try:
            logger.info(f"Starting Textract processing: s3://{bucket}/{key}")
            
            # Start Textract job
            job_id, job_type = self.textract_service.start_job(
                bucket=bucket,
                key=key,
                mode="analysis"  # Use analysis for forms/tables
            )
            
            logger.info(f"Textract job started: {job_id} ({job_type})")
            
            # Poll for completion
            status = self.textract_service.poll_job(job_id, job_type)
            
            logger.info(f"Textract job {job_id} status: {status}")
            
            if status == "SUCCEEDED":
                # Fetch and persist results
                pages = self.textract_service.fetch_results(job_id, job_type)
                
                output_folder = self.textract_service.persist_results(
                    src_bucket=bucket,
                    src_key=key,
                    job_id=job_id,
                    job_type=job_type,
                    pages=pages
                )
                
                duration = (datetime.now() - start_time).total_seconds()
                
                # Build audit payload
                audit_payload = {
                    "timestamp": event_time,
                    "pipeline": "pdf",
                    "s3_key": key,
                    "s3_bucket": bucket,
                    "job_id": job_id,
                    "job_type": job_type,
                    "status": "success",
                    "page_count": len(pages),
                    "output_folder": output_folder,
                    "duration_seconds": duration
                }
                
                # Write audit to output folder
                self.audit_service.write_audit(output_folder, audit_payload)
                
                logger.info(
                    f"Textract processing completed: {len(pages)} pages in {duration:.2f}s"
                )
                
                return {
                    "success": True,
                    "pipeline": "pdf",
                    "job_id": job_id,
                    "output_folder": output_folder,
                    "audit": audit_payload
                }
            
            else:
                # Job failed or partial success
                duration = (datetime.now() - start_time).total_seconds()
                
                audit_payload = {
                    "timestamp": event_time,
                    "pipeline": "pdf",
                    "s3_key": key,
                    "s3_bucket": bucket,
                    "job_id": job_id,
                    "job_type": job_type,
                    "status": status.lower(),
                    "duration_seconds": duration
                }
                
                logger.warning(f"Textract job ended with status: {status}")
                
                return {
                    "success": False,
                    "pipeline": "pdf",
                    "job_id": job_id,
                    "status": status,
                    "audit": audit_payload
                }
                
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            error_msg = str(e)
            
            logger.error(f"Textract processing failed: {error_msg}", exc_info=True)
            
            # Write failure audit
            audit_payload = {
                "timestamp": event_time,
                "pipeline": "pdf",
                "s3_key": key,
                "s3_bucket": bucket,
                "job_id": job_id,
                "job_type": job_type,
                "status": "failed",
                "error": error_msg,
                "error_type": type(e).__name__,
                "duration_seconds": duration
            }
            
            return {
                "success": False,
                "pipeline": "pdf",
                "error": error_msg,
                "audit": audit_payload
            }
    
    def route_event(self, event_record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Route single S3 event record to appropriate pipeline.

        Args:
            event_record: S3 event record

        Returns:
            Processing result
        """
        try:
            # Extract S3 info
            s3_info = event_record['s3']
            bucket = s3_info['bucket']['name']
            key = s3_info['object']['key']

            # URL decode the S3 key (S3 events send URL-encoded keys)
            from urllib.parse import unquote_plus
            key = unquote_plus(key)

            event_time = event_record.get('eventTime', datetime.now().isoformat())
            
            logger.info(
                f"Processing event: s3://{bucket}/{key}",
                extra={"event_time": event_time, "s3_key": key}
            )
            
            # Determine pipeline
            pipeline = self.determine_pipeline(key)
            
            if pipeline == "csv":
                return self.process_csv(bucket, key, event_time)
            elif pipeline == "pdf":
                return self.process_pdf(bucket, key, event_time)
            else:
                logger.info(f"Skipping file (unsupported prefix or extension): {key}")
                return {
                    "success": True,
                    "skipped": True,
                    "reason": "Unsupported prefix or file type",
                    "s3_key": key
                }
                
        except Exception as e:
            logger.error(f"Failed to route event: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }


# Global router instance (reused across invocations)
router = None


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler for S3 PutObject events.
    
    Processes CSV files to RDS and PDF files through Textract.
    
    Args:
        event: Lambda event (S3 notification)
        context: Lambda context object
        
    Returns:
        Processing results summary
    """
    global router
    
    # Initialize router on first invocation (warm start optimization)
    if router is None:
        logger.info("Cold start - initializing router")
        router = MBALambdaRouter()
    else:
        logger.info("Warm start - reusing router")
    
    logger.info(
        f"Lambda invoked: request_id={context.aws_request_id}, "
        f"remaining_time={context.get_remaining_time_in_millis()}ms"
    )
    logger.debug(f"Event: {json.dumps(event)}")
    
    try:
        records = event.get('Records', [])
        
        if not records:
            logger.warning("No records in event")
            return {
                "statusCode": 200,
                "body": json.dumps({"message": "No records to process"})
            }
        
        logger.info(f"Processing {len(records)} record(s)")
        
        results = []
        successful = 0
        failed = 0
        skipped = 0
        
        for idx, record in enumerate(records, 1):
            logger.info(f"Processing record {idx}/{len(records)}")
            
            # Check remaining time
            remaining_ms = context.get_remaining_time_in_millis()
            if remaining_ms < 30000:  # Less than 30 seconds
                logger.warning(
                    f"Low remaining time ({remaining_ms}ms), skipping remaining records"
                )
                break
            
            result = router.route_event(record)
            results.append(result)
            
            if result.get("skipped"):
                skipped += 1
            elif result.get("success"):
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
            f"Lambda execution complete: {successful} successful, "
            f"{failed} failed, {skipped} skipped"
        )
        
        return {
            "statusCode": 200 if failed == 0 else 207,  # Multi-status if any failures
            "body": json.dumps(summary)
        }
        
    except Exception as e:
        logger.error(f"Lambda execution failed: {str(e)}", exc_info=True)
        
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": str(e),
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc()
            })
        }