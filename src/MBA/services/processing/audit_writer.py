"""
Lightweight audit writer.

Writes a compact audit record per run next to Textract outputs:
mba/textract-output/<src_key>/<job_id>/audit.json

Integrates with your existing structured logging.  No database needed.
"""

from __future__ import annotations

import json
from typing import Dict, Any
from pathlib import Path
import tempfile

from MBA.core.logging_config import get_logger
from MBA.services.storage.s3_client import S3Client

logger = get_logger(__name__)


class AuditLoggerService:
    """Emit JSON audit artifacts to S3 (append/overwrite semantics)."""

    def __init__(self, s3_client: S3Client):
        self.s3 = s3_client

    def write_audit(self, s3_folder_key: str, audit_payload: Dict[str, Any]) -> str:
        """
        Write audit.json to the output folder.

        Args:
            s3_folder_key: Folder key ending with "/".
            audit_payload: Dict payload with stages, timings, errors, etc.

        Returns:
            The S3 key written.
        """
        key = f"{s3_folder_key.rstrip('/')}/audit.json"

        data = json.dumps(audit_payload, ensure_ascii=False, indent=2).encode("utf-8")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as f:
            f.write(data)
            tmp_path = Path(f.name)

        try:
            self.s3.upload_file(tmp_path, s3_key=key, content_type="application/json")
            logger.info("Wrote audit to s3://%s/%s", self.s3.bucket, key)
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass

        return key
