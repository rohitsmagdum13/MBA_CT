"""
FastAPI service for S3 file upload and CSV ingestion with duplicate detection.

This module provides REST API endpoints for file uploads, CSV ingestion to RDS,
and service health monitoring.

Module Input:
    - HTTP multipart/form-data file uploads
    - JSON request bodies for ingestion triggers
    - Configuration from settings module

Module Output:
    - JSON responses with upload/ingestion status
    - HTTP status codes for success/failure
    - Structured error messages

Endpoints:
    GET  /health              - Service health check
    POST /upload/single       - Upload single file to S3
    POST /upload/multi        - Upload multiple files to S3
    POST /ingest/file         - Ingest single CSV to RDS
    POST /ingest/directory    - Ingest all CSVs from directory
    GET  /ingest/status/{id}  - Get ingestion job status
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, status, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from pathlib import Path
import tempfile
import shutil
import uuid
from datetime import datetime

from MBA.core.logging_config import get_logger, setup_root_logger
from MBA.core.exceptions import (
    UploadError, FileDiscoveryError, ConfigError,
    DatabaseError, DataIngestionError
)
from MBA.core.settings import settings
from MBA.services.storage.s3_client import S3Client
from MBA.services.storage.file_processor import FileProcessor
from MBA.services.storage.duplicate_detector import DuplicateDetector
from MBA.services.ingestion.orchestrator import CSVIngestor
from MBA.services.database.client import RDSClient
from MBA.agents import MemberVerificationAgent, DeductibleOOPAgent, BenefitAccumulatorAgent, BenefitCoverageRAGAgent, IntentIdentificationAgent, OrchestrationAgent

# Setup logging
setup_root_logger()
logger = get_logger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="MBA Upload & Ingestion Service",
    description="S3 file upload and CSV ingestion service with RDS integration",
    version="0.2.0"
)

# Service instances (initialized on startup)
s3_client: Optional[S3Client] = None
file_processor: Optional[FileProcessor] = None
duplicate_detector: Optional[DuplicateDetector] = None
rds_client: Optional[RDSClient] = None
csv_ingestor: Optional[CSVIngestor] = None
verification_agent: Optional[MemberVerificationAgent] = None
deductible_oop_agent: Optional[DeductibleOOPAgent] = None
benefit_accumulator_agent: Optional[BenefitAccumulatorAgent] = None
benefit_coverage_rag_agent: Optional[BenefitCoverageRAGAgent] = None
intent_identification_agent: Optional[IntentIdentificationAgent] = None
orchestration_agent: Optional[OrchestrationAgent] = None

# Job tracking (in-memory for simplicity)
ingestion_jobs: Dict[str, Dict[str, Any]] = {}


# ============== Request/Response Models ==============

class UploadResponse(BaseModel):
    """Response model for successful single file upload."""
    success: bool
    s3_uri: str
    file_name: str
    document_type: str
    is_duplicate: bool
    duplicate_of: Optional[List[str]] = None
    content_hash: str


class MultiUploadResponse(BaseModel):
    """Response model for multi-file batch upload."""
    total: int
    successful: int
    failed: int
    uploads: List[UploadResponse]
    errors: List[Dict[str, Any]]


class IngestFileRequest(BaseModel):
    """Request model for single file ingestion."""
    file_path: str
    table_name: Optional[str] = None
    update_schema: bool = True


class IngestDirectoryRequest(BaseModel):
    """Request model for directory ingestion."""
    directory_path: str = "data/csv"
    file_pattern: str = "*.csv"
    continue_on_error: bool = True


class IngestResponse(BaseModel):
    """Response model for ingestion operation."""
    job_id: str
    status: str  # "queued", "running", "completed", "failed"
    message: str


class IngestStatusResponse(BaseModel):
    """Response model for ingestion status check."""
    job_id: str
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    results: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """Response model for service health check."""
    status: str
    services: Dict[str, str]
    database_connected: bool


class VerificationRequest(BaseModel):
    """Request model for member verification."""
    member_id: Optional[str] = None
    dob: Optional[str] = None
    name: Optional[str] = None


class BatchVerificationRequest(BaseModel):
    """Request model for batch member verification."""
    members: List[Dict[str, Any]]


class DeductibleOOPRequest(BaseModel):
    """Request model for deductible/OOP lookup."""
    member_id: str
    plan_type: Optional[str] = None
    network: Optional[str] = None


class BenefitAccumulatorRequest(BaseModel):
    """Request model for benefit accumulator lookup."""
    member_id: str
    service: Optional[str] = None


class RAGPrepareRequest(BaseModel):
    """Request model for RAG pipeline preparation."""
    s3_bucket: str
    textract_prefix: str
    index_name: Optional[str] = None
    chunk_size: int = 1000
    chunk_overlap: int = 200


class RAGQueryRequest(BaseModel):
    """Request model for RAG query."""
    question: str
    index_name: Optional[str] = None
    k: int = 5


class IntentIdentificationRequest(BaseModel):
    """Request model for intent identification."""
    query: str
    context: Optional[Dict[str, Any]] = None


class BatchIntentIdentificationRequest(BaseModel):
    """Request model for batch intent identification."""
    queries: List[str]
    context: Optional[Dict[str, Any]] = None


class OrchestrationRequest(BaseModel):
    """Request model for orchestration query processing."""
    query: str
    context: Optional[Dict[str, Any]] = None
    preserve_history: bool = False


class BatchOrchestrationRequest(BaseModel):
    """Request model for batch orchestration."""
    queries: List[str]
    context: Optional[Dict[str, Any]] = None


# ============== Startup/Shutdown ==============

@app.on_event("startup")
async def startup_event():
    """
    Initialize services on application startup.
    
    Side Effects:
        - Initializes global service instances
        - Tests database connectivity
        - Logs initialization status
    """
    global s3_client, file_processor, duplicate_detector, rds_client, csv_ingestor, verification_agent, deductible_oop_agent, benefit_accumulator_agent, benefit_coverage_rag_agent, intent_identification_agent, orchestration_agent

    try:
        # Initialize S3 client
        bucket = settings.get_bucket("mba")
        prefix = settings.get_prefix("mba")
        s3_client = S3Client(bucket=bucket, prefix=prefix)

        # Initialize file processor
        file_processor = FileProcessor(
            allowed_extensions={
                ".pdf", ".doc", ".docx",
                ".xls", ".xlsx", ".xlsm",
                ".txt", ".csv", ".json", ".md"
            },
            max_file_size_mb=100
        )

        # Initialize duplicate detector
        duplicate_detector = DuplicateDetector()

        # Initialize RDS client
        rds_client = RDSClient()

        # Initialize CSV ingestor
        csv_ingestor = CSVIngestor(rds_client=rds_client)

        # Initialize AI agents
        verification_agent = MemberVerificationAgent()
        deductible_oop_agent = DeductibleOOPAgent()
        benefit_accumulator_agent = BenefitAccumulatorAgent()
        benefit_coverage_rag_agent = BenefitCoverageRAGAgent()
        intent_identification_agent = IntentIdentificationAgent()
        orchestration_agent = OrchestrationAgent()

        logger.info("All services initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """
    Cleanup on application shutdown.
    
    Side Effects:
        - Closes database connections
        - Logs shutdown
    """
    if rds_client:
        rds_client.close_all_connections()
    logger.info("Application shutdown complete")


# ============== Health Endpoint ==============

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Health check endpoint for service monitoring.
    
    Returns:
        HealthResponse: Service health status including database connectivity
    """
    services_status = {
        "s3_client": "initialized" if s3_client else "not_initialized",
        "file_processor": "initialized" if file_processor else "not_initialized",
        "duplicate_detector": "initialized" if duplicate_detector else "not_initialized",
        "rds_client": "initialized" if rds_client else "not_initialized",
        "csv_ingestor": "initialized" if csv_ingestor else "not_initialized",
        "verification_agent": "initialized" if verification_agent else "not_initialized",
        "deductible_oop_agent": "initialized" if deductible_oop_agent else "not_initialized",
        "benefit_accumulator_agent": "initialized" if benefit_accumulator_agent else "not_initialized",
        "benefit_coverage_rag_agent": "initialized" if benefit_coverage_rag_agent else "not_initialized",
        "intent_identification_agent": "initialized" if intent_identification_agent else "not_initialized",
        "orchestration_agent": "initialized" if orchestration_agent else "not_initialized"
    }
    
    # Test database connectivity
    db_connected = False
    if rds_client:
        try:
            rds_client.execute_query("SELECT 1", fetch=True)
            db_connected = True
        except:
            pass
    
    all_healthy = (
        all(status == "initialized" for status in services_status.values())
        and db_connected
    )
    
    return HealthResponse(
        status="healthy" if all_healthy else "degraded",
        services=services_status,
        database_connected=db_connected
    )


# ============== Upload Endpoints (Existing) ==============

@app.post("/upload/single", response_model=UploadResponse, tags=["Upload"])
async def upload_single_file(file: UploadFile = File(...)):
    """Upload a single file to S3 with duplicate detection and routing."""
    if not all([s3_client, file_processor, duplicate_detector]):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Services not initialized"
        )
    
    temp_file = None
    try:
        # Create temporary file
        with tempfile.NamedTemporaryFile(
            delete=False, 
            suffix=Path(file.filename).suffix
        ) as tmp:
            shutil.copyfileobj(file.file, tmp)
            temp_file = Path(tmp.name)
        
        logger.info(f"Processing upload: {file.filename}")
        
        # Validate file
        if not file_processor.validate_file(temp_file):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File validation failed: {file.filename}"
            )
        
        # Check for duplicates
        is_dup, content_hash, duplicate_paths = duplicate_detector.is_duplicate(
            temp_file,
            compute_if_missing=True
        )
        
        # Generate S3 key with document-type routing
        original_path = Path(file.filename)
        doc_type = file_processor.get_document_type(original_path)
        s3_key = f"{doc_type.value}/{file.filename}"
        
        # Upload to S3
        s3_uri = s3_client.upload_file(
            temp_file,
            s3_key=s3_key,
            metadata={
                "original_filename": file.filename,
                "document_type": doc_type.value,
                "content_hash": content_hash,
                "is_duplicate": str(is_dup)
            }
        )
        
        logger.info(f"Successfully uploaded {file.filename} to {s3_uri}")
        
        return UploadResponse(
            success=True,
            s3_uri=s3_uri,
            file_name=file.filename,
            document_type=doc_type.value,
            is_duplicate=is_dup,
            duplicate_of=duplicate_paths,
            content_hash=content_hash
        )
        
    except UploadError as e:
        logger.error(f"Upload error: {e.message}", extra={"details": e.details})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=e.message
        )
    except FileDiscoveryError as e:
        logger.error(f"File validation error: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}"
        )
    finally:
        if temp_file and temp_file.exists():
            temp_file.unlink()


@app.post("/upload/multi", response_model=MultiUploadResponse, tags=["Upload"])
async def upload_multiple_files(files: List[UploadFile] = File(...)):
    """Upload multiple files to S3 with duplicate detection and routing."""
    if not all([s3_client, file_processor, duplicate_detector]):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Services not initialized"
        )
    
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files provided"
        )
    
    logger.info(f"Processing batch upload: {len(files)} files")
    
    uploads = []
    errors = []
    temp_files = []
    
    try:
        for file in files:
            temp_file = None
            try:
                # Create temporary file
                with tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=Path(file.filename).suffix
                ) as tmp:
                    shutil.copyfileobj(file.file, tmp)
                    temp_file = Path(tmp.name)
                    temp_files.append(temp_file)
                
                # Validate and process file
                if not file_processor.validate_file(temp_file):
                    errors.append({
                        "file_name": file.filename,
                        "error": "File validation failed"
                    })
                    continue
                
                is_dup, content_hash, duplicate_paths = duplicate_detector.is_duplicate(
                    temp_file,
                    compute_if_missing=True
                )
                
                original_path = Path(file.filename)
                doc_type = file_processor.get_document_type(original_path)
                s3_key = f"{doc_type.value}/{file.filename}"
                
                s3_uri = s3_client.upload_file(
                    temp_file,
                    s3_key=s3_key,
                    metadata={
                        "original_filename": file.filename,
                        "document_type": doc_type.value,
                        "content_hash": content_hash,
                        "is_duplicate": str(is_dup)
                    }
                )
                
                uploads.append(UploadResponse(
                    success=True,
                    s3_uri=s3_uri,
                    file_name=file.filename,
                    document_type=doc_type.value,
                    is_duplicate=is_dup,
                    duplicate_of=duplicate_paths,
                    content_hash=content_hash
                ))
                
            except (UploadError, FileDiscoveryError) as e:
                errors.append({
                    "file_name": file.filename,
                    "error": e.message,
                    "details": e.details
                })
            except Exception as e:
                errors.append({
                    "file_name": file.filename,
                    "error": str(e)
                })
        
        return MultiUploadResponse(
            total=len(files),
            successful=len(uploads),
            failed=len(errors),
            uploads=uploads,
            errors=errors
        )
        
    finally:
        for temp_file in temp_files:
            if temp_file.exists():
                temp_file.unlink()


# ============== CSV Ingestion Endpoints ==============

def run_ingestion_job(job_id: str, file_path: str, table_name: Optional[str]):
    """
    Background task to run CSV ingestion.
    
    Args:
        job_id (str): Unique job identifier
        file_path (str): Path to CSV file
        table_name (Optional[str]): Target table name
    """
    try:
        ingestion_jobs[job_id]["status"] = "running"
        ingestion_jobs[job_id]["started_at"] = datetime.now().isoformat()
        
        logger.info(f"Starting ingestion job {job_id}: {file_path}")
        
        results = csv_ingestor.ingest_csv(
            csv_path=Path(file_path),
            table_name=table_name
        )
        
        ingestion_jobs[job_id]["status"] = "completed"
        ingestion_jobs[job_id]["completed_at"] = datetime.now().isoformat()
        ingestion_jobs[job_id]["results"] = results
        
        logger.info(f"Ingestion job {job_id} completed successfully")
        
    except Exception as e:
        ingestion_jobs[job_id]["status"] = "failed"
        ingestion_jobs[job_id]["completed_at"] = datetime.now().isoformat()
        ingestion_jobs[job_id]["error"] = str(e)
        logger.error(f"Ingestion job {job_id} failed: {str(e)}")


@app.post("/ingest/file", response_model=IngestResponse, tags=["Ingestion"])
async def ingest_csv_file(
    request: IngestFileRequest,
    background_tasks: BackgroundTasks
):
    """
    Ingest single CSV file into RDS.
    
    Triggers background job to:
    1. Infer schema from CSV
    2. Create/update table in RDS
    3. Load data with batch processing
    
    Args:
        request: File path and ingestion options
        
    Returns:
        IngestResponse: Job ID and initial status
        
    Example Request:
        ```json
        {
            "file_path": "data/csv/MemberData.csv",
            "table_name": "members",
            "update_schema": true
        }
        ```
    """
    if not csv_ingestor:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ingestion service not initialized"
        )
    
    # Validate file exists
    csv_path = Path(request.file_path)
    if not csv_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CSV file not found: {request.file_path}"
        )
    
    # Create job
    job_id = str(uuid.uuid4())
    ingestion_jobs[job_id] = {
        "status": "queued",
        "file_path": request.file_path,
        "table_name": request.table_name,
        "created_at": datetime.now().isoformat()
    }
    
    # Queue background task
    background_tasks.add_task(
        run_ingestion_job,
        job_id,
        request.file_path,
        request.table_name
    )
    
    logger.info(f"Queued ingestion job {job_id} for {request.file_path}")
    
    return IngestResponse(
        job_id=job_id,
        status="queued",
        message=f"Ingestion job queued for {csv_path.name}"
    )


@app.post("/ingest/directory", response_model=IngestResponse, tags=["Ingestion"])
async def ingest_csv_directory(
    request: IngestDirectoryRequest,
    background_tasks: BackgroundTasks
):
    """
    Ingest all CSV files from directory into RDS.
    
    Processes multiple CSV files with individual error handling.
    
    Args:
        request: Directory path and processing options
        
    Returns:
        IngestResponse: Job ID for batch operation
        
    Example Request:
        ```json
        {
            "directory_path": "data/csv",
            "file_pattern": "*.csv",
            "continue_on_error": true
        }
        ```
    """
    if not csv_ingestor:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ingestion service not initialized"
        )
    
    # Validate directory exists
    dir_path = Path(request.directory_path)
    if not dir_path.exists() or not dir_path.is_dir():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Directory not found: {request.directory_path}"
        )
    
    # Create job
    job_id = str(uuid.uuid4())
    ingestion_jobs[job_id] = {
        "status": "queued",
        "directory_path": request.directory_path,
        "created_at": datetime.now().isoformat()
    }
    
    # Background task for directory ingestion
    async def run_directory_ingestion():
        try:
            ingestion_jobs[job_id]["status"] = "running"
            ingestion_jobs[job_id]["started_at"] = datetime.now().isoformat()
            
            results = csv_ingestor.ingest_directory(
                directory=dir_path,
                file_pattern=request.file_pattern,
                continue_on_error=request.continue_on_error
            )
            
            ingestion_jobs[job_id]["status"] = "completed"
            ingestion_jobs[job_id]["completed_at"] = datetime.now().isoformat()
            ingestion_jobs[job_id]["results"] = results
            
        except Exception as e:
            ingestion_jobs[job_id]["status"] = "failed"
            ingestion_jobs[job_id]["completed_at"] = datetime.now().isoformat()
            ingestion_jobs[job_id]["error"] = str(e)
    
    background_tasks.add_task(run_directory_ingestion)
    
    logger.info(f"Queued directory ingestion job {job_id} for {request.directory_path}")
    
    return IngestResponse(
        job_id=job_id,
        status="queued",
        message=f"Directory ingestion queued for {request.directory_path}"
    )


@app.get("/ingest/status/{job_id}", response_model=IngestStatusResponse, tags=["Ingestion"])
async def get_ingestion_status(job_id: str):
    """
    Get status of ingestion job.
    
    Args:
        job_id: Job identifier from ingest response
        
    Returns:
        IngestStatusResponse: Current job status and results
    """
    if job_id not in ingestion_jobs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}"
        )
    
    job = ingestion_jobs[job_id]
    
    return IngestStatusResponse(
        job_id=job_id,
        status=job["status"],
        started_at=job.get("started_at"),
        completed_at=job.get("completed_at"),
        results=job.get("results"),
        error=job.get("error")
    )


# ============== Member Verification Endpoints ==============

@app.post("/verify/member", tags=["Verification"])
async def verify_member(request: VerificationRequest):
    """Verify a single member identity."""
    if not verification_agent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Verification service not initialized"
        )
    
    try:
        result = await verification_agent.verify_member(
            member_id=request.member_id,
            dob=request.dob,
            name=request.name
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")


@app.post("/verify/batch", tags=["Verification"])
async def verify_members_batch(request: BatchVerificationRequest):
    """Verify multiple members in batch."""
    if not verification_agent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Verification service not initialized"
        )

    try:
        results = await verification_agent.verify_member_batch(request.members)
        return {"results": results, "total": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch verification failed: {str(e)}")


# ============== Deductible/OOP Endpoints ==============

@app.post("/lookup/deductible-oop", tags=["Lookup"])
async def lookup_deductible_oop(request: DeductibleOOPRequest):
    """
    Lookup deductible and out-of-pocket information for a member.

    This endpoint uses AWS Bedrock LLM to process the request and query
    the deductibles_oop table in RDS MySQL.

    Flow:
    1. User Request
    2. AWS Bedrock LLM Invocation
    3. Bedrock LLM Analyzes Request
    4. Bedrock Calls get_deductible_oop tool
    5. Tool Executes SQL Query against RDS MySQL
    6. Database Returns Results
    7. Tool Returns Structured JSON
    8. Bedrock Formats Final Response
    9. Parse Agent Response
    10. Return to User

    Args:
        request: DeductibleOOPRequest with member_id and optional filters

    Returns:
        JSON response with deductible/OOP information

    Example Request:
        ```json
        {
            "member_id": "M1001",
            "plan_type": "individual",
            "network": "ppo"
        }
        ```
    """
    if not deductible_oop_agent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Deductible/OOP lookup service not initialized"
        )

    try:
        result = await deductible_oop_agent.get_deductible_oop(
            member_id=request.member_id,
            plan_type=request.plan_type,
            network=request.network
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deductible/OOP lookup failed: {str(e)}")


# ============== Benefit Accumulator Endpoints ==============

@app.post("/lookup/benefit-accumulator", tags=["Lookup"])
async def lookup_benefit_accumulator(request: BenefitAccumulatorRequest):
    """
    Lookup benefit accumulator information for a member.

    This endpoint uses AWS Bedrock LLM to process the request and query
    the benefit_accumulator table in RDS MySQL.

    Flow:
    1. User Request
    2. AWS Bedrock LLM Invocation
    3. Bedrock LLM Analyzes Request
    4. Bedrock Calls get_benefit_accumulator tool
    5. Tool Executes SQL Query against RDS MySQL
    6. Database Returns Results
    7. Tool Returns Structured JSON
    8. Bedrock Formats Final Response
    9. Parse Agent Response
    10. Return to User

    Args:
        request: BenefitAccumulatorRequest with member_id and optional service filter

    Returns:
        JSON response with benefit accumulator information

    Example Request:
        ```json
        {
            "member_id": "M1001",
            "service": "Massage Therapy"
        }
        ```
    """
    if not benefit_accumulator_agent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Benefit accumulator lookup service not initialized"
        )

    try:
        result = await benefit_accumulator_agent.get_benefit_accumulator(
            member_id=request.member_id,
            service=request.service
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Benefit accumulator lookup failed: {str(e)}")


# ============== Benefit Coverage RAG Endpoints ==============

@app.post("/rag/prepare", tags=["RAG"])
async def prepare_rag_pipeline(request: RAGPrepareRequest):
    """
    Prepare RAG pipeline from Textract output in S3.

    This endpoint processes Textract-extracted documents and indexes them
    for semantic search and question answering.

    Flow:
    1. Extract text from Textract JSON files in S3
    2. Apply intelligent chunking for benefit coverage documents
    3. Generate embeddings using AWS Bedrock Titan
    4. Index chunks in vector store (OpenSearch/Qdrant)

    Args:
        request: RAGPrepareRequest with S3 bucket and Textract output prefix

    Returns:
        JSON response with preparation results

    Example Request:
        ```json
        {
            "s3_bucket": "mb-assistant-bucket",
            "textract_prefix": "mba/textract-output/mba/pdf/policy.pdf/job-123/",
            "index_name": "benefit_coverage_rag_index",
            "chunk_size": 1000,
            "chunk_overlap": 200
        }
        ```

    Example Response:
        ```json
        {
            "success": true,
            "message": "Processed 10 docs into 45 chunks",
            "chunks_count": 45,
            "doc_count": 10,
            "index_name": "benefit_coverage_rag_index"
        }
        ```
    """
    if not benefit_coverage_rag_agent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Benefit coverage RAG service not initialized"
        )

    try:
        result = await benefit_coverage_rag_agent.prepare_pipeline(
            s3_bucket=request.s3_bucket,
            textract_prefix=request.textract_prefix,
            index_name=request.index_name,
            chunk_size=request.chunk_size,
            chunk_overlap=request.chunk_overlap
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG pipeline preparation failed: {str(e)}")


@app.post("/rag/upload-and-prepare", tags=["RAG"])
async def upload_pdf_and_prepare_rag(
    file: UploadFile = File(...),
    index_name: Optional[str] = None,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    background_tasks: BackgroundTasks = None
):
    """
    **DYNAMIC RAG WORKFLOW**: Upload PDF + Textract + Auto RAG Pipeline Preparation.

    This endpoint provides an all-in-one solution for uploading a PDF document
    and automatically preparing it for RAG querying. It handles:

    1. File upload to S3
    2. Triggering AWS Textract for text extraction
    3. Automatically running the RAG pipeline on the Textract output
    4. Indexing the document for immediate querying

    **Flow:**
    1. Upload PDF to S3 (mba/pdf/)
    2. Trigger AWS Textract Lambda (processes PDF → JSON outputs to mba/textract-output/)
    3. Automatically detect Textract output location
    4. Run RAG preparation pipeline:
       - Extract text from Textract JSON
       - Apply intelligent chunking
       - Generate embeddings with Bedrock Titan
       - Index in Qdrant vector store
    5. Return status and query-ready confirmation

    **Args:**
        file: PDF file to upload (multipart/form-data)
        index_name: Optional custom index name (default: benefit_coverage_rag_index)
        chunk_size: Target chunk size in characters (default: 1000)
        chunk_overlap: Chunk overlap in characters (default: 200)

    **Returns:**
        JSON response with upload status, Textract job info, and RAG preparation results

    **Example Request:**
    ```bash
    curl -X POST "http://localhost:8000/rag/upload-and-prepare" \\
      -H "accept: application/json" \\
      -F "file=@policy_document.pdf" \\
      -F "index_name=my_benefits_index" \\
      -F "chunk_size=1000" \\
      -F "chunk_overlap=200"
    ```

    **Example Response:**
    ```json
    {
      "success": true,
      "message": "PDF uploaded and RAG pipeline prepared successfully",
      "file_name": "policy_document.pdf",
      "s3_uri": "s3://mb-assistant-bucket/mba/pdf/policy_document.pdf",
      "textract_output_prefix": "mba/textract-output/mba/pdf/policy_document.pdf/",
      "rag_preparation": {
        "success": true,
        "message": "Processed 15 docs into 67 chunks",
        "chunks_count": 67,
        "doc_count": 15,
        "index_name": "benefit_coverage_rag_index"
      },
      "query_ready": true,
      "next_steps": "You can now query this document using POST /rag/query"
    }
    ```

    **Note:** This endpoint assumes AWS Textract Lambda is configured to automatically
    process PDFs uploaded to the mba/pdf/ prefix and output results to mba/textract-output/.
    """
    if not all([s3_client, file_processor, benefit_coverage_rag_agent]):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Required services not initialized"
        )

    # Validate PDF file
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported for RAG pipeline"
        )

    temp_file = None
    try:
        logger.info(f"=" * 80)
        logger.info(f"DYNAMIC RAG WORKFLOW STARTED: {file.filename}")
        logger.info(f"=" * 80)

        # Step 1: Save uploaded file temporarily
        logger.info(f"STEP 1: Saving uploaded PDF temporarily...")
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            shutil.copyfileobj(file.file, tmp)
            temp_file = Path(tmp.name)

        logger.info(f"✅ File saved: {temp_file}")

        # Step 2: Validate file
        logger.info(f"\nSTEP 2: Validating PDF file...")
        if not file_processor.validate_file(temp_file):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File validation failed: {file.filename}"
            )
        logger.info(f"✅ File validation passed")

        # Step 3: Upload to S3 (mba/pdf/ prefix)
        logger.info(f"\nSTEP 3: Uploading PDF to S3...")
        s3_key = f"pdf/{file.filename}"
        s3_uri = s3_client.upload_file(
            temp_file,
            s3_key=s3_key,
            metadata={
                "original_filename": file.filename,
                "document_type": "pdf",
                "workflow": "dynamic_rag"
            }
        )
        logger.info(f"✅ Uploaded to: {s3_uri}")

        # Step 4: Construct expected Textract output prefix
        # AWS Textract Lambda should output to: mba/textract-output/mba/pdf/{filename}/
        logger.info(f"\nSTEP 4: Determining Textract output location...")
        textract_prefix = f"textract-output/{s3_key}/"
        logger.info(f"📁 Expected Textract output: s3://{s3_client.bucket}/{textract_prefix}")

        # Step 5: Wait briefly for Textract processing (if synchronous)
        # NOTE: In production, Textract is usually async. You may need to poll or use SNS notifications.
        logger.info(f"\nSTEP 5: Waiting for Textract processing...")
        logger.info(f"⏳ Assuming Textract Lambda processes the PDF automatically...")
        logger.info(f"⚠️  Note: This endpoint assumes Textract has completed processing.")
        logger.info(f"   For async workflows, implement polling or webhook notification.")

        # Step 6: Prepare RAG pipeline from Textract output
        logger.info(f"\nSTEP 6: Preparing RAG pipeline from Textract output...")

        index = index_name or "benefit_coverage_rag_index"

        rag_result = await benefit_coverage_rag_agent.prepare_pipeline(
            s3_bucket=s3_client.bucket,
            textract_prefix=textract_prefix,
            index_name=index,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )

        if not rag_result.get("success"):
            logger.error(f"❌ RAG pipeline preparation failed: {rag_result.get('error')}")
            return {
                "success": False,
                "message": "PDF uploaded but RAG pipeline preparation failed",
                "file_name": file.filename,
                "s3_uri": s3_uri,
                "textract_output_prefix": textract_prefix,
                "rag_preparation": rag_result,
                "query_ready": False,
                "error": rag_result.get("error")
            }

        logger.info(f"✅ RAG pipeline prepared successfully!")
        logger.info(f"=" * 80)
        logger.info(f"DYNAMIC RAG WORKFLOW COMPLETE")
        logger.info(f"Document is now ready for querying!")
        logger.info(f"=" * 80)

        return {
            "success": True,
            "message": "PDF uploaded and RAG pipeline prepared successfully",
            "file_name": file.filename,
            "s3_uri": s3_uri,
            "textract_output_prefix": textract_prefix,
            "rag_preparation": rag_result,
            "query_ready": True,
            "next_steps": f"You can now query this document using POST /rag/query with index_name='{index}'"
        }

    except UploadError as e:
        logger.error(f"❌ Upload error: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=e.message
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error in dynamic RAG workflow: {str(e)}")
        logger.exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Dynamic RAG workflow failed: {str(e)}"
        )
    finally:
        if temp_file and temp_file.exists():
            temp_file.unlink()
            logger.info(f"🧹 Cleaned up temporary file")


@app.post("/rag/query", tags=["RAG"])
async def query_benefit_coverage(request: RAGQueryRequest):
    """
    Query benefit coverage documents using RAG.

    This endpoint uses Retrieval-Augmented Generation to answer questions
    about benefit coverage policies by:
    1. Performing semantic search over indexed documents
    2. Reranking results using AWS Bedrock Cohere Rerank
    3. Generating answers using AWS Bedrock Claude LLM
    4. Providing source citations

    Args:
        request: RAGQueryRequest with question and optional parameters

    Returns:
        JSON response with answer and sources

    Example Request:
        ```json
        {
            "question": "Is massage therapy covered?",
            "index_name": "benefit_coverage_rag_index",
            "k": 5
        }
        ```

    Example Response:
        ```json
        {
            "success": true,
            "answer": "Massage therapy is covered with a limit of 6 visits per calendar year...",
            "sources": [
                {
                    "source_id": 1,
                    "content": "Massage Therapy: Covered with 6 visit limit...",
                    "metadata": {
                        "source": "policy.pdf",
                        "page": 15,
                        "section_title": "Therapy Services"
                    }
                }
            ],
            "question": "Is massage therapy covered?",
            "retrieved_docs_count": 3
        }
        ```
    """
    if not benefit_coverage_rag_agent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Benefit coverage RAG service not initialized"
        )

    try:
        result = await benefit_coverage_rag_agent.query(
            question=request.question,
            index_name=request.index_name,
            k=request.k
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG query failed: {str(e)}")


# ============== Intent Identification Endpoints ==============

@app.post("/intent/identify", tags=["Intent"])
async def identify_intent(request: IntentIdentificationRequest):
    """
    Identify user intent from query for intelligent routing.

    This endpoint analyzes user queries and classifies them into appropriate
    intent categories for routing to the correct agent/service.

    Flow:
    1. Receive user query
    2. Pattern-based pre-classification (fast)
    3. Entity extraction (member ID, service type, query type)
    4. Confidence scoring
    5. Intent classification
    6. Return classification results with routing suggestions

    Supported Intents:
    - member_verification: Verify member eligibility and status
    - deductible_oop: Query deductible and out-of-pocket information
    - benefit_accumulator: Check benefit accumulation and service limits
    - benefit_coverage_rag: Answer benefit coverage policy questions
    - local_rag: Query uploaded benefit documents
    - general_inquiry: Handle greetings and general questions

    Args:
        request: IntentIdentificationRequest with query and optional context

    Returns:
        JSON response with intent classification results

    Example Request:
        ```json
        {
            "query": "Is member M1001 active?",
            "context": {}
        }
        ```

    Example Response:
        ```json
        {
            "success": true,
            "intent": "member_verification",
            "confidence": 0.95,
            "reasoning": "Detected member ID: M1001. Pattern matches: 2 for member_verification",
            "extracted_entities": {
                "member_id": "M1001",
                "query_type": "status"
            },
            "suggested_agent": "MemberVerificationAgent",
            "fallback_intent": "general_inquiry",
            "pattern_matches": {
                "member_verification": 2,
                "deductible_oop": 0,
                "benefit_accumulator": 0,
                "benefit_coverage_rag": 0,
                "local_rag": 0,
                "general_inquiry": 0
            },
            "query": "Is member M1001 active?"
        }
        ```
    """
    if not intent_identification_agent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Intent identification service not initialized"
        )

    try:
        result = await intent_identification_agent.identify(
            query=request.query,
            context=request.context
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Intent identification failed: {str(e)}")


@app.post("/intent/identify-batch", tags=["Intent"])
async def identify_intent_batch(request: BatchIntentIdentificationRequest):
    """
    Identify intents for multiple queries in batch.

    This endpoint processes multiple user queries and returns intent
    classifications for each one. Useful for analyzing conversation
    history or processing bulk queries.

    Args:
        request: BatchIntentIdentificationRequest with list of queries

    Returns:
        JSON response with list of classification results

    Example Request:
        ```json
        {
            "queries": [
                "Is member M1001 active?",
                "What is the deductible for member M1234?",
                "How many massage visits has member M5678 used?"
            ],
            "context": {}
        }
        ```

    Example Response:
        ```json
        {
            "results": [
                {
                    "success": true,
                    "intent": "member_verification",
                    "confidence": 0.95,
                    ...
                },
                {
                    "success": true,
                    "intent": "deductible_oop",
                    "confidence": 0.90,
                    ...
                },
                {
                    "success": true,
                    "intent": "benefit_accumulator",
                    "confidence": 0.98,
                    ...
                }
            ],
            "total": 3
        }
        ```
    """
    if not intent_identification_agent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Intent identification service not initialized"
        )

    try:
        results = await intent_identification_agent.classify_batch(
            queries=request.queries,
            context=request.context
        )
        return {"results": results, "total": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch intent identification failed: {str(e)}")


@app.get("/intent/supported", tags=["Intent"])
async def get_supported_intents():
    """
    Get list of supported intent categories.

    Returns the available intent codes and their corresponding
    agent mappings for reference.

    Returns:
        JSON response with intent codes and agent mapping

    Example Response:
        ```json
        {
            "intents": [
                "member_verification",
                "deductible_oop",
                "benefit_accumulator",
                "benefit_coverage_rag",
                "local_rag",
                "general_inquiry"
            ],
            "agent_mapping": {
                "member_verification": "MemberVerificationAgent",
                "deductible_oop": "DeductibleOOPAgent",
                "benefit_accumulator": "BenefitAccumulatorAgent",
                "benefit_coverage_rag": "BenefitCoverageRAGAgent",
                "local_rag": "LocalRAGAgent",
                "general_inquiry": "None"
            }
        }
        ```
    """
    if not intent_identification_agent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Intent identification service not initialized"
        )

    try:
        intents = intent_identification_agent.get_supported_intents()
        mapping = intent_identification_agent.get_agent_mapping()
        return {"intents": intents, "agent_mapping": mapping}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve supported intents: {str(e)}")


# ============== Orchestration Endpoints ==============

@app.post("/orchestrate/query", tags=["Orchestration"])
async def orchestrate_query(request: OrchestrationRequest):
    """
    Process a user query through intelligent multi-agent orchestration.

    This is the main orchestration endpoint that provides intelligent routing
    and delegation across all MBA system agents. It automatically:
    1. Identifies the intent of the user's query
    2. Routes to the appropriate specialized agent
    3. Executes the agent workflow
    4. Returns a unified response with full context

    This endpoint is ideal for:
    - Building conversational interfaces
    - Creating chatbots or virtual assistants
    - Processing natural language queries without pre-classification
    - Complex workflows requiring multi-agent coordination

    Flow:
    1. Receive user query
    2. Intent classification using IntentIdentificationAgent
    3. Automatic routing to specialized agent:
       - MemberVerificationAgent for member eligibility/status
       - DeductibleOOPAgent for deductible/OOP information
       - BenefitAccumulatorAgent for benefit usage tracking
       - BenefitCoverageRAGAgent for coverage policy questions
       - LocalRAGAgent for user-uploaded document queries
    4. Agent execution with full error handling
    5. Return unified response with intent, confidence, and results

    Args:
        request: OrchestrationRequest with query, optional context, and history flag

    Returns:
        JSON response with orchestration results

    Example Request:
        ```json
        {
            "query": "Is member M1001 active?",
            "context": {},
            "preserve_history": false
        }
        ```

    Example Response:
        ```json
        {
            "success": true,
            "intent": "member_verification",
            "confidence": 0.95,
            "agent": "MemberVerificationAgent",
            "result": {
                "valid": true,
                "member_id": "M1001",
                "name": "John Doe",
                "dob": "1990-01-01",
                "status": "active"
            },
            "query": "Is member M1001 active?",
            "reasoning": "Detected member ID: M1001. Pattern matches: 2 for member_verification",
            "extracted_entities": {
                "member_id": "M1001",
                "query_type": "status"
            }
        }
        ```

    Error Response:
        ```json
        {
            "success": false,
            "error": "Member ID is required for verification",
            "intent": "member_verification",
            "confidence": 0.95,
            "query": "Is the member active?"
        }
        ```
    """
    if not orchestration_agent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Orchestration service not initialized"
        )

    try:
        result = await orchestration_agent.process_query(
            query=request.query,
            context=request.context,
            preserve_history=request.preserve_history
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Orchestration failed: {str(e)}")


@app.post("/orchestrate/batch", tags=["Orchestration"])
async def orchestrate_batch(request: BatchOrchestrationRequest):
    """
    Process multiple queries through orchestration in batch.

    This endpoint allows you to process multiple user queries simultaneously,
    with each query being independently routed to the appropriate agent based
    on its intent classification.

    Useful for:
    - Processing conversation history
    - Batch analysis of user queries
    - Performance testing with multiple query types
    - Analyzing intent distribution across queries

    Args:
        request: BatchOrchestrationRequest with list of queries and optional context

    Returns:
        JSON response with array of orchestration results

    Example Request:
        ```json
        {
            "queries": [
                "Is member M1001 active?",
                "What is the deductible for member M1234?",
                "How many massage therapy visits has member M5678 used?",
                "Is acupuncture covered under the plan?"
            ],
            "context": {}
        }
        ```

    Example Response:
        ```json
        {
            "results": [
                {
                    "success": true,
                    "intent": "member_verification",
                    "confidence": 0.95,
                    "agent": "MemberVerificationAgent",
                    "result": {...},
                    "query": "Is member M1001 active?"
                },
                {
                    "success": true,
                    "intent": "deductible_oop",
                    "confidence": 0.90,
                    "agent": "DeductibleOOPAgent",
                    "result": {...},
                    "query": "What is the deductible for member M1234?"
                },
                {
                    "success": true,
                    "intent": "benefit_accumulator",
                    "confidence": 0.98,
                    "agent": "BenefitAccumulatorAgent",
                    "result": {...},
                    "query": "How many massage therapy visits has member M5678 used?"
                },
                {
                    "success": true,
                    "intent": "benefit_coverage_rag",
                    "confidence": 0.85,
                    "agent": "BenefitCoverageRAGAgent",
                    "result": {...},
                    "query": "Is acupuncture covered under the plan?"
                }
            ],
            "total": 4,
            "successful": 4,
            "failed": 0,
            "intents": {
                "member_verification": 1,
                "deductible_oop": 1,
                "benefit_accumulator": 1,
                "benefit_coverage_rag": 1
            }
        }
        ```
    """
    if not orchestration_agent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Orchestration service not initialized"
        )

    try:
        results = await orchestration_agent.process_batch(
            queries=request.queries,
            context=request.context
        )

        # Calculate statistics
        successful = sum(1 for r in results if r.get("success"))
        failed = len(results) - successful

        # Count intents
        intent_counts = {}
        for result in results:
            intent = result.get("intent", "unknown")
            intent_counts[intent] = intent_counts.get(intent, 0) + 1

        return {
            "results": results,
            "total": len(results),
            "successful": successful,
            "failed": failed,
            "intents": intent_counts
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch orchestration failed: {str(e)}")


@app.get("/orchestrate/agents", tags=["Orchestration"])
async def get_available_agents():
    """
    Get list of available specialized agents in the orchestration system.

    Returns information about all agents that can be used for query processing,
    including their capabilities and supported intents.

    Returns:
        JSON response with list of available agents

    Example Response:
        ```json
        {
            "agents": [
                "IntentIdentificationAgent",
                "MemberVerificationAgent",
                "DeductibleOOPAgent",
                "BenefitAccumulatorAgent",
                "BenefitCoverageRAGAgent",
                "LocalRAGAgent"
            ],
            "total_agents": 6,
            "orchestration_enabled": true
        }
        ```
    """
    if not orchestration_agent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Orchestration service not initialized"
        )

    try:
        agents = orchestration_agent.get_available_agents()
        return {
            "agents": agents,
            "total_agents": len(agents),
            "orchestration_enabled": True
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve available agents: {str(e)}")


@app.get("/orchestrate/history", tags=["Orchestration"])
async def get_conversation_history():
    """
    Get conversation history for the current orchestration session.

    Note: Conversation history is only maintained when preserve_history=true
    is set in orchestration requests. Each orchestration agent instance
    maintains its own history.

    Returns:
        JSON response with conversation history

    Example Response:
        ```json
        {
            "history": [
                {
                    "query": "Is member M1001 active?",
                    "intent": "member_verification",
                    "confidence": 0.95,
                    "agent": "MemberVerificationAgent",
                    "success": true,
                    "timestamp": null
                },
                {
                    "query": "What is their deductible?",
                    "intent": "deductible_oop",
                    "confidence": 0.88,
                    "agent": "DeductibleOOPAgent",
                    "success": true,
                    "timestamp": null
                }
            ],
            "total_interactions": 2
        }
        ```
    """
    if not orchestration_agent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Orchestration service not initialized"
        )

    try:
        history = orchestration_agent.get_conversation_history()
        return {
            "history": history,
            "total_interactions": len(history)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve conversation history: {str(e)}")


@app.delete("/orchestrate/history", tags=["Orchestration"])
async def clear_conversation_history():
    """
    Clear conversation history for the current orchestration session.

    Returns:
        JSON response confirming history cleared

    Example Response:
        ```json
        {
            "success": true,
            "message": "Conversation history cleared"
        }
        ```
    """
    if not orchestration_agent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Orchestration service not initialized"
        )

    try:
        orchestration_agent.clear_conversation_history()
        return {
            "success": True,
            "message": "Conversation history cleared"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear conversation history: {str(e)}")


# ============== Server Runner ==============

def run_server():
    """
    Run the FastAPI server with uvicorn.
    
    Command-line entry point for starting the API server.
    """
    import uvicorn
    uvicorn.run(
        "MBA.microservices.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )


if __name__ == "__main__":
    run_server()