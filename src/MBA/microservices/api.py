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
from MBA.agents import MemberVerificationAgent, DeductibleOOPAgent, BenefitAccumulatorAgent, BenefitCoverageRAGAgent

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
    global s3_client, file_processor, duplicate_detector, rds_client, csv_ingestor, verification_agent, deductible_oop_agent, benefit_accumulator_agent, benefit_coverage_rag_agent

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
        "benefit_coverage_rag_agent": "initialized" if benefit_coverage_rag_agent else "not_initialized"
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