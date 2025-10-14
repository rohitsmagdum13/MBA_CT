"""
Amazon Textract polling client (no SNS) for async PDF analysis.

Starts an async Textract job (TextDetection or DocumentAnalysis),
polls until completion with exponential backoff, paginates results,
and persists each page of output JSON to S3 under the configured
output prefix.

Environment variables (read at runtime):
- AWS_REGION                  (e.g., "us-east-1")
- S3_BUCKET                   (e.g., "mb-assistant-bucket")
- PDF_PREFIX                  (e.g., "mba/pdf/")
- OUTPUT_PREFIX               (e.g., "mba/textract-output/")
- TEXTRACT_FEATURES           (comma list, for analysis: e.g., "TABLES,FORMS")
- TEXTRACT_MAX_SECONDS        (default 240) Hard cap for polling
- TEXTRACT_BACKOFF_START_SEC  (default 2)
- TEXTRACT_BACKOFF_MAX_SEC    (default 12)
"""

from __future__ import annotations

import os
import time
import json
from typing import Dict, Any, List, Optional, Tuple

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from MBA.core.logging_config import get_logger
from MBA.core.exceptions import TextractError, ConfigError
from MBA.services.storage.s3_client import S3Client

logger = get_logger(__name__)


class TextractPollingService:
    """
    SNS-free Textract runner with backoff polling.

    Usage:
        svc = TextractPollingService()
        job_id, job_type = svc.start_job(bucket, key, mode="text")
        status = svc.poll_job(job_id, job_type)
        pages = svc.fetch_results(job_id, job_type)
        svc.persist_results(bucket, key, pages)
    """

    def __init__(
        self,
        region_name: Optional[str] = None,
        output_prefix: Optional[str] = None,
        s3_bucket: Optional[str] = None,
    ):
        self.region = region_name or os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
        self.s3_bucket = s3_bucket or os.environ.get("S3_BUCKET")
        self.pdf_prefix = (os.environ.get("PDF_PREFIX") or "mba/pdf/").lstrip("/")
        self.output_prefix = (output_prefix or os.environ.get("OUTPUT_PREFIX") or "mba/textract-output/").lstrip("/")

        if not self.s3_bucket:
            raise ConfigError("S3_BUCKET is required for Textract workflow")

        # CRITICAL FIX: Detect Lambda environment
        is_lambda = 'AWS_EXECUTION_ENV' in os.environ or 'AWS_LAMBDA_FUNCTION_NAME' in os.environ
        
        if is_lambda:
            # In Lambda: Use execution role automatically
            logger.info("Running in AWS Lambda - using execution role")
            session = boto3.Session(region_name=self.region)
        else:
            # Running locally: Use credentials from settings if available
            logger.info("Running locally - using credentials from settings")
            session_kwargs = {'region_name': self.region}
            
            # Import settings here to avoid circular dependency
            from MBA.core.settings import settings
            
            if settings.aws_profile:
                session_kwargs["profile_name"] = settings.aws_profile
            elif settings.aws_access_key_id and settings.aws_secret_access_key:
                session_kwargs["aws_access_key_id"] = settings.aws_access_key_id
                session_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
            
            session = boto3.Session(**session_kwargs)
        
        self.textract = session.client("textract")
        self.s3_client_wrapped = S3Client(bucket=self.s3_bucket, prefix="")

        # Polling/backoff tuning
        self.max_seconds = int(os.environ.get("TEXTRACT_MAX_SECONDS", "240"))
        self.backoff_start = float(os.environ.get("TEXTRACT_BACKOFF_START_SEC", "2"))
        self.backoff_max = float(os.environ.get("TEXTRACT_BACKOFF_MAX_SEC", "12"))

        # Features for analysis mode
        raw_feats = os.environ.get("TEXTRACT_FEATURES", "")
        self.analysis_features = [f.strip().upper() for f in raw_feats.split(",") if f.strip()]

        logger.info(
            "TextractPollingService initialized: region=%s, bucket=%s, output_prefix=%s",
            self.region, self.s3_bucket, self.output_prefix
        )

    # ----------------------------- Job Start -----------------------------

    def start_job(self, bucket: str, key: str, mode: str = "text") -> Tuple[str, str]:
        """
        Start async Textract job.

        Args:
            bucket: S3 bucket containing the input PDF.
            key: S3 key (must be in PDF prefix).
            mode: "text" (StartDocumentTextDetection) or "analysis" (StartDocumentAnalysis).

        Returns:
            (job_id, job_type) where job_type in {"TEXT_DETECTION","DOCUMENT_ANALYSIS"}
        """
        document = {"S3Object": {"Bucket": bucket, "Name": key}}

        try:
            if mode.lower() == "analysis":
                features = self.analysis_features or ["TABLES", "FORMS"]
                resp = self.textract.start_document_analysis(
                    DocumentLocation=document,
                    FeatureTypes=features
                )
                job_type = "DOCUMENT_ANALYSIS"
            else:
                resp = self.textract.start_document_text_detection(DocumentLocation=document)
                job_type = "TEXT_DETECTION"

            job_id = resp["JobId"]
            logger.info("Started Textract %s: job_id=%s key=%s", job_type, job_id, key)
            return job_id, job_type

        except (ClientError, BotoCoreError) as e:
            raise TextractError(
                f"Failed to start Textract job: {str(e)}",
                details={"bucket": bucket, "key": key, "mode": mode}
            )

    # ----------------------------- Polling ------------------------------

    def poll_job(self, job_id: str, job_type: str) -> str:
        """
        Poll job status with exponential backoff (no SNS).

        Returns:
            Final status string ("SUCCEEDED", "FAILED", "PARTIAL_SUCCESS").
        """
        elapsed = 0.0
        delay = self.backoff_start

        describe_fn = (
            self.textract.get_document_text_detection
            if job_type == "TEXT_DETECTION"
            else self.textract.get_document_analysis
        )

        while elapsed < self.max_seconds:
            try:
                resp = describe_fn(JobId=job_id, MaxResults=1)
                status = resp.get("JobStatus", "UNKNOWN")
                logger.info("Textract job %s status=%s elapsed=%.1fs", job_id, status, elapsed)

                if status in ("SUCCEEDED", "FAILED", "PARTIAL_SUCCESS"):
                    return status

                time.sleep(delay)
                elapsed += delay
                delay = min(self.backoff_max, delay * 1.5)

            except (ClientError, BotoCoreError) as e:
                # Transient describe failure; back off and continue
                logger.warning("Describe failed for job %s: %s", job_id, str(e))
                time.sleep(delay)
                elapsed += delay
                delay = min(self.backoff_max, delay * 1.5)

        raise TextractError(
            "Textract job timed out while polling",
            details={"job_id": job_id, "max_seconds": self.max_seconds}
        )

    # ----------------------------- Fetch --------------------------------

    def fetch_results(self, job_id: str, job_type: str) -> List[Dict[str, Any]]:
        """
        Drain all result pages (handles NextToken).

        Returns:
            List of page JSON payloads in Textract native format.
        """
        pages: List[Dict[str, Any]] = []
        token: Optional[str] = None

        fetch_fn = (
            self.textract.get_document_text_detection
            if job_type == "TEXT_DETECTION"
            else self.textract.get_document_analysis
        )

        try:
            while True:
                kwargs = {"JobId": job_id, "MaxResults": 1000}
                if token:
                    kwargs["NextToken"] = token

                resp = fetch_fn(**kwargs)
                pages.append(resp)
                token = resp.get("NextToken")
                if not token:
                    break

            logger.info("Fetched %d Textract page(s) for job_id=%s", len(pages), job_id)
            return pages

        except (ClientError, BotoCoreError) as e:
            raise TextractError(
                f"Failed to fetch Textract results: {str(e)}",
                details={"job_id": job_id, "job_type": job_type}
            )

    # ----------------------------- Persist ------------------------------

    def _output_folder_for_key(self, src_key: str, job_id: str) -> str:
        """
        Build output folder path under OUTPUT_PREFIX for this source key.
        Example: mba/textract-output/mba/pdf/claim123.pdf/<job_id>/
        """
        # Keep source key (minus leading slash) to maintain lineage
        normalized_key = src_key.lstrip("/")
        return f"{self.output_prefix}/{normalized_key}/{job_id}/".replace("//", "/")

    def persist_results(self, src_bucket: str, src_key: str, job_id: str, job_type: str, pages: List[Dict[str, Any]]) -> str:
        """
        Write a manifest + page JSON files under OUTPUT_PREFIX.

        Returns:
            The output folder key that was written.
        """
        out_folder = self._output_folder_for_key(src_key, job_id)

        # 1) Manifest
        manifest = {
            "job_id": job_id,
            "job_type": job_type,
            "source_bucket": src_bucket,
            "source_key": src_key,
            "page_count": len(pages),
            "status": "SUCCEEDED"
        }
        self._put_json(out_folder + "manifest.json", manifest)

        # 2) Page files
        for idx, payload in enumerate(pages, start=1):
            self._put_json(out_folder + f"page_{idx:04d}.json", payload)

        logger.info("Persisted Textract outputs to s3://%s/%s", self.s3_bucket, out_folder)
        return out_folder

    # ----------------------------- Helpers ------------------------------

    def _put_json(self, key: str, data: Dict[str, Any]) -> None:
        tmp = json.dumps(data, ensure_ascii=False).encode("utf-8")
        # Use the wrapped S3 client’s upload (inherits your logging/retries) :contentReference[oaicite:2]{index=2}
        from pathlib import Path
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as f:
            f.write(tmp)
            tmp_path = Path(f.name)
        try:
            self.s3_client_wrapped.upload_file(tmp_path, s3_key=key, content_type="application/json")
        finally:
            try:
                tmp_path.unlink(missing_ok=True)  # py311+
            except Exception:
                pass
