"""
Streamlit web interface for MBA file upload and CSV ingestion service.

This module provides a comprehensive web UI for testing file uploads, CSV ingestion
to RDS, and monitoring ingestion status with real-time feedback.

Module Input:
    - File uploads via Streamlit file_uploader
    - User interactions via Streamlit widgets
    - Configuration from settings module

Module Output:
    - Interactive web UI for file uploads and CSV ingestion
    - Visual feedback on upload/ingestion status
    - Duplicate detection results
    - Database table information

Pages:
    - Single Upload: Upload and test individual files to S3
    - Multi Upload: Batch upload multiple files to S3
    - CSV Ingestion: Ingest CSV files into RDS
    - View Duplicates: Browse duplicate detection cache
    - Database Tables: View RDS table schemas
"""

import streamlit as st
from pathlib import Path
import tempfile
import shutil
from typing import Dict, Any, List
import pandas as pd
from datetime import datetime

from MBA.core.logging_config import get_logger, setup_root_logger
from MBA.core.exceptions import (
    UploadError, FileDiscoveryError,
    DatabaseError, DataIngestionError
)
from MBA.core.settings import settings
from MBA.services.storage.s3_client import S3Client
from MBA.services.storage.file_processor import FileProcessor
from MBA.services.storage.duplicate_detector import DuplicateDetector
from MBA.services.database.client import RDSClient
from MBA.services.ingestion.orchestrator import CSVIngestor
from MBA.agents.member_verification_agent import MemberVerificationAgent
from MBA.agents.deductible_oop_agent import DeductibleOOPAgent
from MBA.agents.benefit_accumulator_agent import BenefitAccumulatorAgent
from MBA.agents.benefit_coverage_rag_agent import BenefitCoverageRAGAgent
from MBA.agents.local_rag_agent import LocalRAGAgent
from MBA.agents.orchestration_agent import OrchestrationAgent

# Setup logging
setup_root_logger()
logger = get_logger(__name__)

# Page configuration
st.set_page_config(
    page_title="MBA Upload & Ingestion Service",
    page_icon="📤",
    layout="wide",
    initial_sidebar_state="expanded"
)


@st.cache_resource
def initialize_services():
    """
    Initialize and cache service instances.

    Returns:
        Tuple: (S3Client, FileProcessor, DuplicateDetector, RDSClient, CSVIngestor, MemberVerificationAgent)

    Side Effects:
        - Creates service instances
        - Tests connectivity
        - Logs initialization
    """
    try:
        bucket = settings.get_bucket("mba")
        prefix = settings.get_prefix("mba")

        s3_client = S3Client(bucket=bucket, prefix=prefix)
        file_processor = FileProcessor(
            allowed_extensions={
                ".pdf", ".doc", ".docx",
                ".xls", ".xlsx", ".xlsm",
                ".txt", ".csv", ".json", ".md"
            },
            max_file_size_mb=100
        )
        duplicate_detector = DuplicateDetector()
        rds_client = RDSClient()
        csv_ingestor = CSVIngestor(rds_client=rds_client)

        logger.info("Core services initialized successfully")
        return s3_client, file_processor, duplicate_detector, rds_client, csv_ingestor

    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        st.error(f"❌ Failed to initialize services: {str(e)}")
        st.stop()


def process_file_upload(
    file_data,
    file_name: str,
    s3_client: S3Client,
    file_processor: FileProcessor,
    duplicate_detector: DuplicateDetector
) -> Dict[str, Any]:
    """
    Process and upload a single file with duplicate detection.
    
    Args:
        file_data: File data from Streamlit uploader
        file_name (str): Original filename
        s3_client: S3 client instance
        file_processor: File processor instance
        duplicate_detector: Duplicate detector instance
        
    Returns:
        Dict[str, Any]: Upload result with status and metadata
    """
    temp_file = None
    try:
        suffix = Path(file_name).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(file_data.read())
            temp_file = Path(tmp.name)
        
        if not file_processor.validate_file(temp_file):
            return {
                "success": False,
                "file_name": file_name,
                "error": "File validation failed"
            }
        
        is_dup, content_hash, duplicate_paths = duplicate_detector.is_duplicate(
            temp_file,
            compute_if_missing=True
        )
        
        # Get document type from original filename (not temp file)
        original_path = Path(file_name)
        doc_type = file_processor.get_document_type(original_path)
        
        # Generate S3 key using original filename
        s3_key = f"{doc_type.value}/{file_name}"
        
        s3_uri = s3_client.upload_file(
            temp_file,
            s3_key=s3_key,
            metadata={
                "original_filename": file_name,
                "document_type": doc_type.value,
                "content_hash": content_hash,
                "is_duplicate": str(is_dup)
            }
        )
        
        return {
            "success": True,
            "file_name": file_name,
            "s3_uri": s3_uri,
            "document_type": doc_type.value,
            "is_duplicate": is_dup,
            "duplicate_of": duplicate_paths,
            "content_hash": content_hash[:16]
        }
        
    except (UploadError, FileDiscoveryError) as e:
        logger.error(f"Failed to upload {file_name}: {e.message}")
        return {
            "success": False,
            "file_name": file_name,
            "error": e.message
        }
    except Exception as e:
        logger.error(f"Unexpected error uploading {file_name}: {str(e)}")
        return {
            "success": False,
            "file_name": file_name,
            "error": str(e)
        }
    finally:
        if temp_file and temp_file.exists():
            temp_file.unlink()


def render_upload_result(result: Dict[str, Any]):
    """Render upload result in formatted display."""
    if result["success"]:
        st.success("✅ Upload successful!")
        
        col_a, col_b = st.columns(2)
        
        with col_a:
            st.write(f"**S3 URI:** `{result['s3_uri']}`")
            st.write(f"**Document Type:** `{result['document_type']}`")
            st.write(f"**Content Hash:** `{result['content_hash']}...`")
        
        with col_b:
            if result["is_duplicate"]:
                st.warning("⚠️ Duplicate Detected")
                if result.get("duplicate_of"):
                    st.write("**Duplicate of:**")
                    for dup_path in result["duplicate_of"]:
                        st.code(Path(dup_path).name, language=None)
            else:
                st.success("✅ Unique File")
    else:
        st.error(f"❌ Upload failed: {result['error']}")


def render_ingestion_result(result: Dict[str, Any]):
    """Render CSV ingestion result."""
    if result.get("success"):
        st.success("✅ Ingestion successful!")
        
        load_results = result.get("load_results", {})
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Table", result["table_name"])
        col2.metric("Rows Loaded", load_results.get("rows_loaded", 0))
        col3.metric("Failed", load_results.get("rows_failed", 0))
        col4.metric("Duration", f"{load_results.get('duration_seconds', 0)}s")
        
        if load_results.get("errors"):
            with st.expander("⚠️ View Errors"):
                for error in load_results["errors"][:10]:
                    st.code(str(error), language="json")
    else:
        st.error("❌ Ingestion failed")
        if result.get("load_results", {}).get("errors"):
            with st.expander("View Error Details"):
                for error in result["load_results"]["errors"][:10]:
                    st.code(str(error), language="json")


def main():
    """Main Streamlit application entry point."""

    # Initialize services
    s3_client, file_processor, duplicate_detector, rds_client, csv_ingestor = initialize_services()
    
    # Lazy-load agents (only when tabs are accessed)
    verification_agent = None
    deductible_oop_agent = None
    benefit_accumulator_agent = None
    benefit_coverage_rag_agent = None
    local_rag_agent = None
    orchestration_agent = None
    
    # Header
    st.title("📤 MBA Upload & Ingestion Service")
    st.markdown(
        "Upload files to S3 and ingest CSVs into RDS with automatic schema management"
    )
    
    # Sidebar - Configuration & Statistics
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # S3 Info
        st.subheader("S3 Storage")
        st.info(f"**Bucket:** `{s3_client.bucket}`")
        st.info(f"**Prefix:** `{s3_client.prefix}`")
        
        # RDS Info
        st.subheader("RDS Database")
        st.info(f"**Host:** `{rds_client.host}`")
        st.info(f"**Database:** `{rds_client.database}`")
        
        # Test database connection
        try:
            rds_client.execute_query("SELECT 1", fetch=True)
            st.success("✅ Database Connected")
        except:
            st.error("❌ Database Connection Failed")
        
        st.divider()
        
        # Cache Statistics
        st.header("📊 Duplicate Cache")
        cache_stats = duplicate_detector.get_cache_stats()
        
        col1, col2 = st.columns(2)
        col1.metric("Files", cache_stats["total_files"])
        col2.metric("Duplicates", cache_stats["duplicate_groups"])
        
        if st.button("🗑️ Clear Cache", use_container_width=True):
            duplicate_detector.clear_cache()
            st.success("Cache cleared!")
            st.rerun()
        
        st.divider()
        
        st.caption(
            "**Supported formats:** PDF, Word, Excel, Text, CSV, JSON, Markdown"
        )
        st.caption(f"**Max file size:** {file_processor.max_file_size_mb} MB")
    
    # Main content - Tabs
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10, tab11 = st.tabs([
        "📄 Single Upload",
        "📁 Multi Upload",
        "💾 CSV Ingestion",
        "👤 Member Verification",
        "💰 Deductible/OOP",
        "🏥 Benefit Accumulator",
        "🔍 View Duplicates",
        "🗄️ Database Tables",
        "📚 Benefit Coverage RAG",
        "📁 Local RAG",
        "🎯 AI Orchestration"
    ])
    
    # Tab 1: Single File Upload
    with tab1:
        st.header("Upload Single File to S3")
        st.markdown("Upload and analyze a single file with duplicate detection.")
        
        uploaded_file = st.file_uploader(
            "Choose a file",
            type=["pdf", "doc", "docx", "xls", "xlsx", "xlsm", "txt", "csv", "json", "md"],
            key="single_upload"
        )
        
        if uploaded_file:
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.write(f"**Filename:** {uploaded_file.name}")
                st.write(f"**Size:** {uploaded_file.size / 1024:.2f} KB")
                st.write(f"**Type:** {uploaded_file.type}")
            
            with col2:
                if st.button("🚀 Upload", type="primary", use_container_width=True):
                    with st.spinner("Uploading..."):
                        result = process_file_upload(
                            uploaded_file,
                            uploaded_file.name,
                            s3_client,
                            file_processor,
                            duplicate_detector
                        )
                        
                        st.divider()
                        render_upload_result(result)
    
    # Tab 2: Multi-File Upload
    with tab2:
        st.header("Upload Multiple Files to S3")
        st.markdown("Batch upload multiple files with individual status tracking.")
        
        uploaded_files = st.file_uploader(
            "Choose files",
            type=["pdf", "doc", "docx", "xls", "xlsx", "xlsm", "txt", "csv", "json", "md"],
            accept_multiple_files=True,
            key="multi_upload"
        )
        
        if uploaded_files:
            st.write(f"**Selected Files:** {len(uploaded_files)}")
            
            with st.expander("📋 View file list"):
                for idx, file in enumerate(uploaded_files, 1):
                    st.text(f"{idx}. {file.name} ({file.size / 1024:.2f} KB)")
            
            if st.button("🚀 Upload All", type="primary", use_container_width=True):
                progress_bar = st.progress(0, text="Starting upload...")
                
                results = []
                for idx, file in enumerate(uploaded_files):
                    progress_bar.progress(
                        idx / len(uploaded_files),
                        text=f"Uploading {idx + 1}/{len(uploaded_files)}: {file.name}"
                    )
                    
                    result = process_file_upload(
                        file,
                        file.name,
                        s3_client,
                        file_processor,
                        duplicate_detector
                    )
                    results.append(result)
                
                progress_bar.progress(1.0, text="Upload complete!")
                progress_bar.empty()
                
                # Display summary
                st.divider()
                st.subheader("📊 Upload Summary")
                
                successful = sum(1 for r in results if r["success"])
                failed = len(results) - successful
                duplicates = sum(1 for r in results if r.get("is_duplicate", False))
                
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Total", len(results))
                col2.metric("Successful", successful)
                col3.metric("Failed", failed)
                col4.metric("Duplicates", duplicates)
                
                # Display results
                st.divider()
                st.subheader("📝 Detailed Results")
                
                for result in results:
                    status_icon = "✅" if result["success"] else "❌"
                    with st.expander(f"{status_icon} {result['file_name']}"):
                        render_upload_result(result)
    
    # Tab 3: CSV Ingestion
    with tab3:
        st.header("CSV Ingestion to RDS")
        st.markdown("Ingest CSV files into MySQL with automatic schema management.")
        
        # Mode selection
        mode = st.radio(
            "Ingestion Mode",
            ["Single File", "Directory"],
            horizontal=True
        )
        
        if mode == "Single File":
            st.subheader("Ingest Single CSV File")
            
            # File selection
            csv_dir = Path(settings.csv_data_dir)
            if csv_dir.exists():
                csv_files = list(csv_dir.glob("*.csv"))
                
                if csv_files:
                    selected_file = st.selectbox(
                        "Select CSV File",
                        options=[f.name for f in csv_files],
                        key="single_csv"
                    )
                    
                    if selected_file:
                        file_path = csv_dir / selected_file
                        
                        # Preview
                        with st.expander("📊 Preview Data"):
                            try:
                                df_preview = pd.read_csv(file_path, nrows=5)
                                st.dataframe(df_preview)
                                st.caption(f"Showing first 5 rows of {len(df_preview.columns)} columns")
                            except Exception as e:
                                st.error(f"Failed to preview: {str(e)}")
                        
                        # Options
                        col1, col2 = st.columns(2)
                        with col1:
                            custom_table = st.text_input(
                                "Custom Table Name (optional)",
                                placeholder="Leave empty for auto-generated"
                            )
                        with col2:
                            truncate = st.checkbox("Truncate table before load", value=False)
                        
                        # Ingest button
                        if st.button("💾 Ingest to RDS", type="primary", use_container_width=True):
                            with st.spinner(f"Ingesting {selected_file}..."):
                                try:
                                    # Update ingestor settings
                                    csv_ingestor.truncate_before_load = truncate
                                    
                                    # Run ingestion
                                    result = csv_ingestor.ingest_csv(
                                        csv_path=file_path,
                                        table_name=custom_table if custom_table else None
                                    )
                                    
                                    st.divider()
                                    render_ingestion_result(result)
                                    
                                except Exception as e:
                                    st.error(f"❌ Ingestion failed: {str(e)}")
                                    logger.error(f"Ingestion error: {str(e)}")
                else:
                    st.warning(f"No CSV files found in {csv_dir}")
            else:
                st.error(f"CSV directory not found: {csv_dir}")
        
        else:  # Directory mode
            st.subheader("Ingest All CSVs from Directory")
            
            csv_dir = Path(settings.csv_data_dir)
            
            if csv_dir.exists():
                csv_files = list(csv_dir.glob("*.csv"))
                
                st.info(f"📁 Directory: `{csv_dir}`")
                st.info(f"📄 CSV files found: **{len(csv_files)}**")
                
                if csv_files:
                    with st.expander("📋 View files"):
                        for f in csv_files:
                            st.text(f"• {f.name}")
                    
                    # Options
                    continue_on_error = st.checkbox(
                        "Continue on error",
                        value=True,
                        help="Continue processing remaining files if one fails"
                    )
                    
                    truncate = st.checkbox(
                        "Truncate tables before load",
                        value=False
                    )
                    
                    # Ingest button
                    if st.button("💾 Ingest All", type="primary", use_container_width=True):
                        with st.spinner("Ingesting files..."):
                            try:
                                csv_ingestor.truncate_before_load = truncate
                                
                                results = csv_ingestor.ingest_directory(
                                    directory=csv_dir,
                                    continue_on_error=continue_on_error
                                )
                                
                                st.divider()
                                st.subheader("📊 Batch Ingestion Summary")
                                
                                col1, col2, col3 = st.columns(3)
                                col1.metric("Total Files", results["total_files"])
                                col2.metric("Successful", results["successful"])
                                col3.metric("Failed", results["failed"])
                                
                                # Individual results
                                if results["results"]:
                                    st.divider()
                                    st.subheader("📝 File Results")
                                    
                                    for res in results["results"]:
                                        status = "✅" if res.get("success") else "❌"
                                        with st.expander(f"{status} {res['csv_file']}"):
                                            render_ingestion_result(res)
                                
                                # Errors
                                if results["errors"]:
                                    st.divider()
                                    st.subheader("⚠️ Errors")
                                    for error in results["errors"]:
                                        st.error(f"{error['file']}: {error['error']}")
                                
                            except Exception as e:
                                st.error(f"❌ Batch ingestion failed: {str(e)}")
                else:
                    st.warning("No CSV files found in directory")
            else:
                st.error(f"Directory not found: {csv_dir}")

    # Tab 4: Member Verification
    with tab4:
        st.header("👤 Member Verification")
        st.markdown("Verify member identity using AI-powered authentication with AWS Bedrock.")

        # Information box
        st.info("""
        **How it works:**
        1. User Request → Strands Agent → AWS Bedrock LLM
        2. Bedrock analyzes request → verify_member Tool → RDS MySQL
        3. SQL Query Result → JSON Response
        """)

        # Verification mode selection
        verification_mode = st.radio(
            "Verification Mode",
            ["Single Member", "Batch Verification"],
            horizontal=True
        )

        if verification_mode == "Single Member":
            st.subheader("Verify Single Member")

            # Input form
            with st.form("single_verification_form"):
                col1, col2 = st.columns(2)

                with col1:
                    member_id = st.text_input(
                        "Member ID",
                        placeholder="e.g., M1001",
                        help="Unique member identifier"
                    )
                    dob = st.date_input(
                        "Date of Birth",
                        value=None,
                        help="Member's date of birth"
                    )

                with col2:
                    name = st.text_input(
                        "Full Name (Optional)",
                        placeholder="e.g., John Doe",
                        help="Member's full name for additional validation"
                    )

                st.markdown("**Note:** At least one field (Member ID or DOB) is required for verification.")

                submit_button = st.form_submit_button("🔍 Verify Member", type="primary", use_container_width=True)

            if submit_button:
                # Validate at least one field is provided
                if not member_id and not dob and not name:
                    st.error("❌ Please provide at least one verification parameter (Member ID, DOB, or Name)")
                else:
                    with st.spinner("Verifying member..."):
                        try:
                            # Lazy-load agent
                            if verification_agent is None:
                                verification_agent = MemberVerificationAgent()
                            # Build params
                            params = {}
                            if member_id:
                                params["member_id"] = member_id
                            if dob:
                                params["dob"] = str(dob)
                            if name:
                                params["name"] = name

                            # Call verification agent
                            import asyncio
                            result = asyncio.run(verification_agent.verify_member(**params))

                            st.divider()

                            # Display result
                            if result.get("valid"):
                                st.success("✅ Member Verified Successfully!")

                                col1, col2, col3 = st.columns(3)
                                col1.metric("Member ID", result.get("member_id", "N/A"))
                                col2.metric("Name", result.get("name", "N/A"))
                                col3.metric("Date of Birth", result.get("dob", "N/A"))

                                # Show full result
                                with st.expander("📋 View Full Response"):
                                    st.json(result)

                            elif "error" in result:
                                st.error(f"❌ Verification Error: {result['error']}")

                                with st.expander("📋 View Error Details"):
                                    st.json(result)

                            else:
                                st.warning("⚠️ Member Not Found")
                                st.info(result.get("message", "Authentication failed"))

                                with st.expander("📋 View Response"):
                                    st.json(result)

                        except Exception as e:
                            st.error(f"❌ Verification failed: {str(e)}")
                            logger.error(f"Member verification error: {str(e)}", exc_info=True)

        else:  # Batch Verification
            st.subheader("Batch Member Verification")

            st.markdown("Upload a CSV file or enter multiple members manually.")

            # Option to upload CSV or manual entry
            batch_mode = st.radio(
                "Input Method",
                ["Manual Entry", "Upload CSV"],
                horizontal=True
            )

            if batch_mode == "Manual Entry":
                st.markdown("**Enter member details (one per line):**")

                # Text area for manual entry
                manual_input = st.text_area(
                    "Member Data",
                    placeholder="M1001, 2005-05-23, Brandi Kim\nM1002, 1987-12-14, Anthony Brown",
                    help="Format: member_id, dob, name (one member per line)",
                    height=150
                )

                if st.button("🔍 Verify All", type="primary", use_container_width=True):
                    if not manual_input.strip():
                        st.error("❌ Please enter member data")
                    else:
                        # Parse manual input
                        members = []
                        lines = manual_input.strip().split("\n")

                        for idx, line in enumerate(lines, 1):
                            parts = [p.strip() for p in line.split(",")]
                            if len(parts) >= 2:
                                member = {"member_id": parts[0], "dob": parts[1]}
                                if len(parts) >= 3:
                                    member["name"] = parts[2]
                                members.append(member)

                        if not members:
                            st.error("❌ No valid member data found")
                        else:
                            with st.spinner(f"Verifying {len(members)} members..."):
                                try:
                                    # Lazy-load agent
                                    if verification_agent is None:
                                        verification_agent = MemberVerificationAgent()
                                    import asyncio
                                    results = asyncio.run(verification_agent.verify_member_batch(members))

                                    st.divider()
                                    st.subheader("📊 Batch Verification Results")

                                    # Summary metrics
                                    verified = sum(1 for r in results if r.get("valid"))
                                    failed = sum(1 for r in results if not r.get("valid") and "error" not in r)
                                    errors = sum(1 for r in results if "error" in r)

                                    col1, col2, col3, col4 = st.columns(4)
                                    col1.metric("Total", len(results))
                                    col2.metric("Verified", verified)
                                    col3.metric("Not Found", failed)
                                    col4.metric("Errors", errors)

                                    st.divider()

                                    # Display individual results
                                    st.subheader("📝 Individual Results")

                                    for idx, result in enumerate(results, 1):
                                        if result.get("valid"):
                                            status = "✅"
                                            label = f"{result.get('member_id', 'Unknown')} - {result.get('name', 'N/A')}"
                                        elif "error" in result:
                                            status = "❌"
                                            label = f"Member {idx} - Error"
                                        else:
                                            status = "⚠️"
                                            label = f"Member {idx} - Not Found"

                                        with st.expander(f"{status} {label}"):
                                            st.json(result)

                                except Exception as e:
                                    st.error(f"❌ Batch verification failed: {str(e)}")
                                    logger.error(f"Batch verification error: {str(e)}", exc_info=True)

            else:  # Upload CSV
                st.markdown("**Upload a CSV file with member data:**")

                csv_file = st.file_uploader(
                    "Choose CSV file",
                    type=["csv"],
                    help="CSV should have columns: member_id, dob, name (optional)",
                    key="batch_verification_csv"
                )

                if csv_file:
                    try:
                        df = pd.read_csv(csv_file)

                        st.write(f"**Loaded:** {len(df)} members")

                        with st.expander("📊 Preview Data"):
                            st.dataframe(df.head(10))

                        if st.button("🔍 Verify All", type="primary", use_container_width=True):
                            with st.spinner(f"Verifying {len(df)} members..."):
                                try:
                                    # Lazy-load agent
                                    if verification_agent is None:
                                        verification_agent = MemberVerificationAgent()
                                    
                                    # Convert DataFrame to list of dicts
                                    members = df.to_dict('records')

                                    # Clean up the data
                                    for member in members:
                                        # Convert any NaN to None
                                        member = {k: (None if pd.isna(v) else v) for k, v in member.items()}

                                    import asyncio
                                    results = asyncio.run(verification_agent.verify_member_batch(members))

                                    st.divider()
                                    st.subheader("📊 Batch Verification Results")

                                    # Summary metrics
                                    verified = sum(1 for r in results if r.get("valid"))
                                    failed = sum(1 for r in results if not r.get("valid") and "error" not in r)
                                    errors = sum(1 for r in results if "error" in r)

                                    col1, col2, col3, col4 = st.columns(4)
                                    col1.metric("Total", len(results))
                                    col2.metric("Verified", verified)
                                    col3.metric("Not Found", failed)
                                    col4.metric("Errors", errors)

                                    st.divider()

                                    # Create results DataFrame
                                    results_df = pd.DataFrame(results)
                                    st.subheader("📝 Results Table")
                                    st.dataframe(results_df, use_container_width=True)

                                    # Download results
                                    csv_results = results_df.to_csv(index=False)
                                    st.download_button(
                                        label="📥 Download Results CSV",
                                        data=csv_results,
                                        file_name=f"verification_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                        mime="text/csv"
                                    )

                                except Exception as e:
                                    st.error(f"❌ Batch verification failed: {str(e)}")
                                    logger.error(f"CSV batch verification error: {str(e)}", exc_info=True)

                    except Exception as e:
                        st.error(f"❌ Failed to load CSV: {str(e)}")

    # Tab 5: Deductible/OOP Lookup
    with tab5:
        st.header("💰 Deductible & Out-of-Pocket Lookup")
        st.markdown("Query member deductible and OOP information using AWS Bedrock AI.")

        st.info("""
        **How it works:**
        1. User Request → AWS Bedrock LLM → get_deductible_oop Tool
        2. Tool queries RDS MySQL deductibles_oop table
        3. Returns structured deductible/OOP data for all plan types and networks
        """)

        with st.form("deductible_oop_form"):
            col1, col2, col3 = st.columns(3)

            with col1:
                member_id = st.text_input(
                    "Member ID *",
                    placeholder="e.g., M1001",
                    help="Required: Member identifier"
                )

            with col2:
                plan_type = st.selectbox(
                    "Plan Type (Optional)",
                    options=["", "individual", "family"],
                    help="Filter by plan type"
                )

            with col3:
                network = st.selectbox(
                    "Network (Optional)",
                    options=["", "ppo", "par", "oon"],
                    help="Filter by network level"
                )

            submit = st.form_submit_button("🔍 Lookup", type="primary", use_container_width=True)

        if submit:
            if not member_id:
                st.error("❌ Member ID is required")
            else:
                with st.spinner("Querying deductible/OOP data..."):
                    try:
                        # Lazy-load agent
                        if deductible_oop_agent is None:
                            deductible_oop_agent = DeductibleOOPAgent()
                        import asyncio
                        result = asyncio.run(deductible_oop_agent.get_deductible_oop(
                            member_id=member_id,
                            plan_type=plan_type if plan_type else None,
                            network=network if network else None
                        ))

                        st.divider()

                        if result.get("found"):
                            st.success(f"✅ Found deductible/OOP data for {result['member_id']}")

                            # Individual Plans
                            st.subheader("👤 Individual Plans")
                            ind_data = result.get("individual", {})

                            col1, col2, col3 = st.columns(3)

                            with col1:
                                st.markdown("**PPO**")
                                ppo = ind_data.get("ppo", {})
                                st.metric("Deductible", ppo.get("deductible", "N/A"))
                                st.metric("Met", ppo.get("deductible_met", "N/A"))
                                st.metric("Remaining", ppo.get("deductible_remaining", "N/A"))
                                st.metric("OOP Limit", ppo.get("oop", "N/A"))
                                st.metric("OOP Met", ppo.get("oop_met", "N/A"))
                                st.metric("OOP Remaining", ppo.get("oop_remaining", "N/A"))

                            with col2:
                                st.markdown("**PAR**")
                                par = ind_data.get("par", {})
                                st.metric("Deductible", par.get("deductible", "N/A"))
                                st.metric("Met", par.get("deductible_met", "N/A"))
                                st.metric("Remaining", par.get("deductible_remaining", "N/A"))
                                st.metric("OOP Limit", par.get("oop", "N/A"))
                                st.metric("OOP Met", par.get("oop_met", "N/A"))
                                st.metric("OOP Remaining", par.get("oop_remaining", "N/A"))

                            with col3:
                                st.markdown("**OON**")
                                oon = ind_data.get("oon", {})
                                st.metric("Deductible", oon.get("deductible", "N/A"))
                                st.metric("Met", oon.get("deductible_met", "N/A"))
                                st.metric("Remaining", oon.get("deductible_remaining", "N/A"))
                                st.metric("OOP Limit", oon.get("oop", "N/A"))
                                st.metric("OOP Met", oon.get("oop_met", "N/A"))
                                st.metric("OOP Remaining", oon.get("oop_remaining", "N/A"))

                            st.divider()

                            # Family Plans
                            st.subheader("👨‍👩‍👧‍👦 Family Plans")
                            fam_data = result.get("family", {})

                            col1, col2, col3 = st.columns(3)

                            with col1:
                                st.markdown("**PPO**")
                                ppo = fam_data.get("ppo", {})
                                st.metric("Deductible", ppo.get("deductible", "N/A"))
                                st.metric("Met", ppo.get("deductible_met", "N/A"))
                                st.metric("Remaining", ppo.get("deductible_remaining", "N/A"))
                                st.metric("OOP Limit", ppo.get("oop", "N/A"))
                                st.metric("OOP Met", ppo.get("oop_met", "N/A"))
                                st.metric("OOP Remaining", ppo.get("oop_remaining", "N/A"))

                            with col2:
                                st.markdown("**PAR**")
                                par = fam_data.get("par", {})
                                st.metric("Deductible", par.get("deductible", "N/A"))
                                st.metric("Met", par.get("deductible_met", "N/A"))
                                st.metric("Remaining", par.get("deductible_remaining", "N/A"))
                                st.metric("OOP Limit", par.get("oop", "N/A"))
                                st.metric("OOP Met", par.get("oop_met", "N/A"))
                                st.metric("OOP Remaining", par.get("oop_remaining", "N/A"))

                            with col3:
                                st.markdown("**OON**")
                                oon = fam_data.get("oon", {})
                                st.metric("Deductible", oon.get("deductible", "N/A"))
                                st.metric("Met", oon.get("deductible_met", "N/A"))
                                st.metric("Remaining", oon.get("deductible_remaining", "N/A"))
                                st.metric("OOP Limit", oon.get("oop", "N/A"))
                                st.metric("OOP Met", oon.get("oop_met", "N/A"))
                                st.metric("OOP Remaining", oon.get("oop_remaining", "N/A"))

                            with st.expander("📋 View Full Response"):
                                st.json(result)

                        elif "error" in result:
                            st.error(f"❌ Lookup Error: {result['error']}")
                            with st.expander("📋 View Error Details"):
                                st.json(result)
                        else:
                            st.warning("⚠️ No data found")
                            st.info(result.get("message", "No deductible/OOP data found"))

                    except Exception as e:
                        st.error(f"❌ Lookup failed: {str(e)}")
                        logger.error(f"Deductible/OOP lookup error: {str(e)}", exc_info=True)

    # Tab 6: Benefit Accumulator Lookup
    with tab6:
        st.header("🏥 Benefit Accumulator Lookup")
        st.markdown("Query member benefit usage information using AWS Bedrock AI.")

        st.info("""
        **How it works:**
        1. User Request → AWS Bedrock LLM → get_benefit_accumulator Tool
        2. Tool queries RDS MySQL benefit_accumulator table
        3. Returns benefit usage data with limits, used amounts, and remaining balances
        """)

        with st.form("benefit_accumulator_form"):
            col1, col2 = st.columns(2)

            with col1:
                member_id = st.text_input(
                    "Member ID *",
                    placeholder="e.g., M1001",
                    help="Required: Member identifier"
                )

            with col2:
                service = st.text_input(
                    "Service (Optional)",
                    placeholder="e.g., Massage Therapy",
                    help="Filter by specific service name"
                )

            submit = st.form_submit_button("🔍 Lookup", type="primary", use_container_width=True)

        if submit:
            if not member_id:
                st.error("❌ Member ID is required")
            else:
                with st.spinner("Querying benefit accumulator data..."):
                    try:
                        # Lazy-load agent
                        if benefit_accumulator_agent is None:
                            benefit_accumulator_agent = BenefitAccumulatorAgent()
                        import asyncio
                        result = asyncio.run(benefit_accumulator_agent.get_benefit_accumulator(
                            member_id=member_id,
                            service=service if service else None
                        ))

                        st.divider()

                        if result.get("found"):
                            benefits = result.get("benefits", [])
                            st.success(f"✅ Found {len(benefits)} benefit(s) for {result['member_id']}")

                            # Display benefits as table
                            if benefits:
                                df_benefits = pd.DataFrame(benefits)
                                st.dataframe(
                                    df_benefits,
                                    use_container_width=True,
                                    column_config={
                                        "service": st.column_config.TextColumn("Service", width="medium"),
                                        "allowed_limit": st.column_config.TextColumn("Allowed Limit", width="medium"),
                                        "used": st.column_config.NumberColumn("Used", width="small"),
                                        "remaining": st.column_config.NumberColumn("Remaining", width="small")
                                    }
                                )

                                st.divider()

                                # Individual benefit cards
                                st.subheader("📊 Benefit Details")
                                for benefit in benefits:
                                    with st.expander(f"🏥 {benefit['service']}"):
                                        col1, col2, col3 = st.columns(3)
                                        col1.metric("Allowed Limit", benefit['allowed_limit'])
                                        col2.metric("Used", benefit['used'])
                                        col3.metric("Remaining", benefit['remaining'])

                            with st.expander("📋 View Full Response"):
                                st.json(result)

                        elif "error" in result:
                            st.error(f"❌ Lookup Error: {result['error']}")
                            with st.expander("📋 View Error Details"):
                                st.json(result)
                        else:
                            st.warning("⚠️ No benefits found")
                            st.info(result.get("message", "No benefit accumulator data found"))

                    except Exception as e:
                        st.error(f"❌ Lookup failed: {str(e)}")
                        logger.error(f"Benefit accumulator lookup error: {str(e)}", exc_info=True)

    # Tab 7: View Duplicates
    with tab7:
        st.header("Duplicate Detection Cache")
        st.markdown("Browse all detected duplicate file groups.")
        
        duplicates = duplicate_detector.get_all_duplicates()
        
        if not duplicates:
            st.info("ℹ️ No duplicates detected yet. Upload some files to see duplicates.")
        else:
            st.success(f"Found **{len(duplicates)}** duplicate group(s)")
            
            for idx, (hash_val, paths) in enumerate(duplicates.items(), 1):
                with st.expander(
                    f"**Group {idx}:** {len(paths)} files (Hash: `{hash_val[:16]}...`)"
                ):
                    st.write("**Files in this group:**")
                    for path in paths:
                        st.code(Path(path).name, language=None)
                    
                    st.caption(f"Full hash: `{hash_val}`")

    # Tab 8: Database Tables
    with tab8:
        st.header("RDS Database Tables")
        st.markdown("View table schemas and statistics.")
        
        try:
            # Get list of tables
            tables_query = """
                SELECT 
                    table_name,
                    table_rows,
                    data_length,
                    create_time,
                    update_time
                FROM information_schema.tables
                WHERE table_schema = %s
                ORDER BY table_name
            """
            
            tables = rds_client.execute_query(
                tables_query,
                params=(rds_client.database,)
            )
            
            if tables:
                st.success(f"Found **{len(tables)}** tables")
                
                # Table selector
                table_names = [t["table_name"] for t in tables]
                selected_table = st.selectbox("Select Table", options=table_names)
                
                if selected_table:
                    # Table info
                    table_info = next(t for t in tables if t["table_name"] == selected_table)
                    
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Rows", f"{table_info['table_rows']:,}")
                    col2.metric("Size", f"{table_info['data_length'] / 1024:.2f} KB")
                    col3.metric("Created", table_info["create_time"].strftime("%Y-%m-%d") if table_info["create_time"] else "N/A")
                    
                    st.divider()
                    
                    # Get columns
                    columns = rds_client.get_table_columns(selected_table)
                    
                    st.subheader("📋 Schema")
                    
                    # Display as dataframe
                    df_schema = pd.DataFrame(columns)
                    st.dataframe(
                        df_schema[["column_name", "column_type", "is_nullable", "column_key"]],
                        use_container_width=True
                    )
                    
                    st.divider()
                    
                    # Preview data
                    st.subheader("📊 Data Preview")
                    
                    preview_limit = st.slider("Number of rows", 5, 100, 10)
                    
                    if st.button("Load Preview"):
                        try:
                            preview_query = f"SELECT * FROM `{selected_table}` LIMIT %s"
                            preview_data = rds_client.execute_query(
                                preview_query,
                                params=(preview_limit,)
                            )
                            
                            if preview_data:
                                df_preview = pd.DataFrame(preview_data)
                                st.dataframe(df_preview, use_container_width=True)
                            else:
                                st.info("Table is empty")
                                
                        except Exception as e:
                            st.error(f"Failed to load preview: {str(e)}")
            else:
                st.info("No tables found in database")
                
        except Exception as e:
            st.error(f"Failed to retrieve table information: {str(e)}")

    # Tab 9: Benefit Coverage RAG
    with tab9:
        st.header("📚 Benefit Coverage RAG Agent")
        st.markdown("Query benefit coverage documents using cloud-based RAG with AWS Textract and Bedrock.")

        st.info("""
        **How it works:**
        - **🆕 Dynamic Upload**: Upload PDF → Auto Textract → Auto RAG Prep → Query Ready!
        - **Prepare**: Extract text from Textract JSON in S3 → Chunk → Embed with Bedrock Titan → Store in vector DB
        - **Query**: Semantic search → Rerank with Bedrock Cohere → Generate answer with Bedrock Claude
        """)

        # Mode selection
        rag_mode = st.radio(
            "Operation Mode",
            ["🆕 Dynamic Upload", "Prepare Pipeline", "Query Documents"],
            horizontal=True,
            key="benefit_rag_mode"
        )

        if rag_mode == "🆕 Dynamic Upload":
            st.subheader("🚀 Dynamic Upload + Auto RAG Pipeline")
            st.markdown("**Upload PDF → Automatic Textract → Automatic RAG → Query Ready!**")

            st.success("""
            ✨ **One-Click Solution:**
            1. Upload your PDF benefit document
            2. System automatically uploads to S3
            3. Textract extracts text (wait for processing)
            4. RAG pipeline prepares automatically
            5. Document is immediately ready for querying!
            """)

            uploaded_pdf = st.file_uploader(
                "Choose a PDF benefit document",
                type=["pdf"],
                key="dynamic_rag_pdf_upload",
                help="Upload a benefit policy PDF for automatic processing"
            )

            if uploaded_pdf:
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Filename:** {uploaded_pdf.name}")
                    st.write(f"**Size:** {uploaded_pdf.size / 1024:.2f} KB")
                    st.write(f"**Type:** {uploaded_pdf.type}")

                with col2:
                    index_name = st.text_input(
                        "Index Name (Optional)",
                        placeholder="benefit_coverage_rag_index",
                        help="Custom index name for this document",
                        key="dynamic_rag_index_name"
                    )

                    chunk_size = st.number_input(
                        "Chunk Size",
                        min_value=500,
                        max_value=2000,
                        value=1000,
                        step=100,
                        help="Target chunk size in characters",
                        key="dynamic_rag_chunk_size"
                    )

                st.divider()

                if st.button("🚀 Upload & Prepare RAG Pipeline", type="primary", use_container_width=True):
                    with st.spinner("📤 Step 1/4: Uploading PDF to S3..."):
                        try:
                            # Save uploaded file to temp location
                            import tempfile
                            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                                tmp.write(uploaded_pdf.read())
                                temp_pdf_path = tmp.name

                            # Upload to S3
                            s3_key = f"pdf/{uploaded_pdf.name}"
                            s3_uri = s3_client.upload_file(
                                Path(temp_pdf_path),
                                s3_key=s3_key,
                                metadata={
                                    "original_filename": uploaded_pdf.name,
                                    "document_type": "pdf",
                                    "workflow": "dynamic_rag"
                                }
                            )

                            st.success(f"✅ Uploaded to S3: `{s3_uri}`")

                            # Clean up temp file
                            Path(temp_pdf_path).unlink(missing_ok=True)

                            # Construct Textract output prefix
                            # S3 client adds 'mba/' prefix, so full key is: mba/pdf/filename.pdf
                            # Textract Lambda outputs to: mba/textract-output/mba/pdf/filename/{job_id}/
                            # We need to include the full path structure

                            # Get the actual uploaded key from S3 URI
                            # S3 URI format: s3://bucket/key
                            actual_s3_key = s3_uri.split(f"s3://{s3_client.bucket}/")[1]
                            logger.info(f"Actual S3 key from upload: {actual_s3_key}")

                            # Construct Textract output prefix based on actual key
                            # If key is "mba/pdf/file.pdf", Textract outputs to "mba/textract-output/mba/pdf/file.pdf/{job_id}/"
                            textract_prefix = f"mba/textract-output/{actual_s3_key}/"

                            logger.info(f"Constructed Textract prefix: {textract_prefix}")

                            st.divider()
                            st.info(f"⏳ Step 2/4: Waiting for Textract processing...")
                            st.caption(f"📁 Searching for Textract output: `s3://{s3_client.bucket}/{textract_prefix}`")
                            st.caption(f"💡 Note: Textract creates job-specific subfolders automatically")

                            # Wait for Textract to process - with progress updates
                            import time
                            import boto3

                            max_wait_time = 60  # Wait up to 60 seconds
                            check_interval = 5  # Check every 5 seconds

                            st.info("⏳ Waiting for Textract to process the PDF...")

                            # Create S3 client to check for output
                            session = boto3.Session(
                                aws_access_key_id=settings.aws_access_key_id,
                                aws_secret_access_key=settings.aws_secret_access_key,
                                region_name=settings.aws_default_region
                            )
                            boto_s3 = session.client('s3')

                            progress_bar = st.progress(0)
                            status_text = st.empty()

                            textract_completed = False
                            for elapsed in range(0, max_wait_time, check_interval):
                                progress_bar.progress((elapsed + check_interval) / max_wait_time)
                                status_text.text(f"⏳ Checking for Textract output... ({elapsed + check_interval}s / {max_wait_time}s)")

                                # Check if Textract output exists
                                try:
                                    response = boto_s3.list_objects_v2(
                                        Bucket=s3_client.bucket,
                                        Prefix=textract_prefix,
                                        MaxKeys=1
                                    )

                                    if response.get('KeyCount', 0) > 0:
                                        textract_completed = True
                                        status_text.text("✅ Textract processing complete!")
                                        break
                                except Exception as e:
                                    logger.warning(f"Error checking Textract output: {e}")

                                time.sleep(check_interval)

                            progress_bar.empty()

                            if not textract_completed:
                                st.warning(f"""
                                ⚠️ Textract output not found after {max_wait_time} seconds.

                                **Possible reasons:**
                                1. Textract is still processing (large PDFs take longer)
                                2. Textract Lambda failed (check CloudWatch logs)
                                3. Textract Lambda is not configured

                                **What to do:**
                                - Wait a bit longer and try uploading again
                                - Or use "Prepare Pipeline" mode manually once Textract completes
                                - Check CloudWatch logs: `/aws/lambda/mba-textract-lambda`
                                """)
                            else:
                                st.success(f"✅ Textract output detected at: `{textract_prefix}`")

                            st.divider()

                            # Only proceed if Textract completed
                            if not textract_completed:
                                st.error("❌ Cannot proceed without Textract output. Please check CloudWatch logs or try again later.")
                                st.stop()

                            # Step 3: Prepare RAG pipeline
                            with st.spinner("🔄 Step 3/4: Preparing RAG pipeline from Textract output..."):
                                # Lazy-load agent
                                if benefit_coverage_rag_agent is None:
                                    benefit_coverage_rag_agent = BenefitCoverageRAGAgent()

                                import asyncio

                                # Show detailed progress
                                progress_placeholder = st.empty()
                                progress_placeholder.info("📊 Extracting text from Textract JSON files...")

                                result = asyncio.run(benefit_coverage_rag_agent.prepare_pipeline(
                                    s3_bucket=s3_client.bucket,
                                    textract_prefix=textract_prefix,
                                    index_name=index_name if index_name else "benefit_coverage_rag_index",
                                    chunk_size=chunk_size,
                                    chunk_overlap=200
                                ))

                                progress_placeholder.empty()

                                st.divider()

                                if result.get("success"):
                                    st.success("✅ Step 4/4: RAG Pipeline prepared successfully!")

                                    st.balloons()

                                    # Display metrics
                                    col1, col2, col3, col4 = st.columns(4)
                                    col1.metric("📄 Documents", result.get("doc_count", 0))
                                    col2.metric("📦 Chunks", result.get("chunks_count", 0))
                                    col3.metric("📁 Index", result.get("index_name", "N/A"))
                                    col4.metric("✅ Status", "Ready to Query")

                                    st.divider()

                                    st.success(f"""
                                    🎉 **All Done!** Your document is ready for querying.

                                    **Next Steps:**
                                    1. Switch to "Query Documents" mode
                                    2. Ask questions about your benefit document
                                    3. Get instant AI-powered answers with sources!
                                    """)

                                    # Show sample queries
                                    with st.expander("💡 Sample Questions You Can Ask"):
                                        st.markdown("""
                                        - Is massage therapy covered?
                                        - What are the deductibles for PPO plans?
                                        - Are there visit limits for chiropractic care?
                                        - What is the copay for physical therapy?
                                        - Is acupuncture a covered benefit?
                                        """)

                                    with st.expander("📋 View Full RAG Preparation Response"):
                                        st.json(result)

                                else:
                                    st.error("❌ RAG Pipeline preparation failed")

                                    if "error" in result:
                                        st.error(f"**Error:** {result['error']}")

                                        # Check if it's a Textract-related error
                                        if "No files found" in result.get('error', '') or "No page JSON" in result.get('error', ''):
                                            st.warning("""
                                            🔍 **Textract Output Not Found**

                                            This usually means:
                                            1. Textract Lambda hasn't processed the PDF yet (wait a few seconds/minutes)
                                            2. Textract Lambda is not configured correctly
                                            3. The expected output path is incorrect

                                            **Solution:**
                                            - Wait for Textract to complete
                                            - Check Textract Lambda logs in AWS CloudWatch
                                            - Or use "Prepare Pipeline" mode manually once Textract completes
                                            """)

                                    with st.expander("📋 View Error Details"):
                                        st.json(result)

                        except Exception as e:
                            st.error(f"❌ Dynamic RAG workflow failed: {str(e)}")
                            logger.error(f"Dynamic RAG workflow error: {str(e)}", exc_info=True)

                            # Show troubleshooting tips
                            with st.expander("🔧 Troubleshooting Tips"):
                                st.markdown("""
                                **Common Issues:**

                                1. **S3 Upload Failed:**
                                   - Check AWS credentials in settings
                                   - Verify S3 bucket permissions

                                2. **Textract Not Processing:**
                                   - Ensure Textract Lambda is deployed
                                   - Check Lambda trigger configuration
                                   - Verify Lambda has S3 read/write permissions

                                3. **RAG Pipeline Failed:**
                                   - Check Qdrant/OpenSearch is running
                                   - Verify AWS Bedrock access
                                   - Check API quotas and limits
                                """)

        elif rag_mode == "Prepare Pipeline":
            st.subheader("🔧 Prepare RAG Pipeline")
            st.markdown("Prepare the RAG pipeline from AWS Textract output stored in S3.")

            with st.form("prepare_benefit_rag_form"):
                col1, col2 = st.columns(2)

                with col1:
                    s3_bucket = st.text_input(
                        "S3 Bucket *",
                        value=settings.get_bucket("mba"),
                        help="S3 bucket containing Textract output"
                    )

                with col2:
                    textract_prefix = st.text_input(
                        "Textract Output Prefix *",
                        placeholder="e.g., mba/textract-output/mba/pdf/policy.pdf/job-123/",
                        help="S3 prefix where Textract JSON files are stored"
                    )

                vector_store = st.selectbox(
                    "Vector Store",
                    options=["opensearch", "qdrant"],
                    help="Choose vector database backend"
                )

                submit = st.form_submit_button("🚀 Prepare Pipeline", type="primary", use_container_width=True)

            if submit:
                if not s3_bucket or not textract_prefix:
                    st.error("❌ S3 bucket and Textract prefix are required")
                else:
                    with st.spinner("Preparing RAG pipeline..."):
                        try:
                            # Lazy-load agent
                            if benefit_coverage_rag_agent is None:
                                benefit_coverage_rag_agent = BenefitCoverageRAGAgent()

                            import asyncio
                            result = asyncio.run(benefit_coverage_rag_agent.prepare_pipeline(
                                s3_bucket=s3_bucket,
                                textract_prefix=textract_prefix,
                                index_name=f"{vector_store}_benefit_coverage"
                            ))

                            st.divider()

                            if result.get("success"):
                                st.success("✅ RAG Pipeline prepared successfully!")

                                col1, col2, col3 = st.columns(3)
                                col1.metric("Documents", result.get("document_count", 0))
                                col2.metric("Chunks", result.get("chunk_count", 0))
                                col3.metric("Vector Store", result.get("vector_store", "N/A"))

                                with st.expander("📋 View Full Response"):
                                    st.json(result)

                            elif "error" in result:
                                st.error(f"❌ Preparation Error: {result['error']}")
                                with st.expander("📋 View Error Details"):
                                    st.json(result)
                            else:
                                st.warning("⚠️ Preparation incomplete")
                                st.json(result)

                        except Exception as e:
                            st.error(f"❌ Pipeline preparation failed: {str(e)}")
                            logger.error(f"Benefit Coverage RAG preparation error: {str(e)}", exc_info=True)

        else:  # Query Documents
            st.subheader("🔍 Query Benefit Coverage Documents")
            st.markdown("Ask questions about benefit coverage using RAG.")

            with st.form("query_benefit_rag_form"):
                question = st.text_area(
                    "Your Question *",
                    placeholder="e.g., Is massage therapy covered? What are the deductibles for PPO plans?",
                    help="Ask any question about benefit coverage",
                    height=100
                )

                col1, col2 = st.columns(2)

                with col1:
                    top_k = st.slider(
                        "Number of documents to retrieve",
                        min_value=1,
                        max_value=20,
                        value=10,
                        help="How many relevant chunks to retrieve"
                    )

                with col2:
                    rerank_top_n = st.slider(
                        "Top documents after reranking",
                        min_value=1,
                        max_value=10,
                        value=5,
                        help="How many top chunks to use for answer generation"
                    )

                submit = st.form_submit_button("🔍 Query", type="primary", use_container_width=True)

            if submit:
                if not question.strip():
                    st.error("❌ Please enter a question")
                else:
                    with st.spinner("Querying documents..."):
                        try:
                            # Lazy-load agent
                            if benefit_coverage_rag_agent is None:
                                benefit_coverage_rag_agent = BenefitCoverageRAGAgent()

                            import asyncio
                            result = asyncio.run(benefit_coverage_rag_agent.query(
                                question=question,
                                k=rerank_top_n  # Use rerank_top_n as the final number of docs
                            ))

                            st.divider()

                            if result.get("success"):
                                st.success("✅ Query completed successfully!")

                                # Display answer
                                st.subheader("💡 Answer")
                                st.markdown(result.get("answer", "No answer generated"))

                                st.divider()

                                # Display sources
                                sources = result.get("sources", [])
                                if sources:
                                    st.subheader("📚 Sources")
                                    for idx, source in enumerate(sources, 1):
                                        # Handle both field names: "content" and "text"
                                        page_num = source.get('metadata', {}).get('page', source.get('page', 'N/A'))
                                        score = source.get('score', source.get('similarity_score', 0))
                                        text_content = source.get("content", source.get("text", "No text available"))

                                        with st.expander(f"Source {idx} - Page {page_num} (Score: {score:.3f})"):
                                            st.markdown(text_content)
                                            st.caption(f"**Metadata:** {source.get('metadata', {})}")

                                with st.expander("📋 View Full Response"):
                                    st.json(result)

                            elif "error" in result:
                                st.error(f"❌ Query Error: {result['error']}")
                                with st.expander("📋 View Error Details"):
                                    st.json(result)
                            else:
                                st.warning("⚠️ Query incomplete")
                                st.json(result)

                        except Exception as e:
                            st.error(f"❌ Query failed: {str(e)}")
                            logger.error(f"Benefit Coverage RAG query error: {str(e)}", exc_info=True)

    # Tab 10: Local RAG
    with tab10:
        st.header("📁 Local RAG Agent")
        st.markdown("Upload PDFs and query them using local open-source RAG (PyMuPDF, Tabula, ChromaDB).")

        st.info("""
        **How it works:**
        1. **Upload**: Upload PDF → Extract text/tables with PyMuPDF & Tabula → Save JSON locally
        2. **Prepare**: Load JSON → Chunk → Embed with Sentence Transformers → Store in ChromaDB
        3. **Query**: Semantic search → Rerank with Cross-Encoder → Generate answer with Bedrock Claude
        """)

        # Mode selection
        local_rag_mode = st.radio(
            "Operation Mode",
            ["Upload PDF", "Prepare Pipeline", "Query Documents"],
            horizontal=True,
            key="local_rag_mode"
        )

        if local_rag_mode == "Upload PDF":
            st.subheader("📤 Upload PDF for Local Processing")
            st.markdown("Upload a PDF file to extract text and tables locally.")

            uploaded_pdf = st.file_uploader(
                "Choose a PDF file",
                type=["pdf"],
                key="local_rag_pdf_upload",
                help="Upload a benefit policy document"
            )

            if uploaded_pdf:
                st.write(f"**Filename:** {uploaded_pdf.name}")
                st.write(f"**Size:** {uploaded_pdf.size / 1024:.2f} KB")

                if st.button("🚀 Extract Content", type="primary", use_container_width=True):
                    with st.spinner("Extracting text and tables from PDF..."):
                        try:
                            # Save uploaded file to temp location
                            import tempfile
                            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                                tmp.write(uploaded_pdf.read())
                                temp_pdf_path = tmp.name

                            # Lazy-load agent
                            if local_rag_agent is None:
                                local_rag_agent = LocalRAGAgent()

                            import asyncio
                            result = asyncio.run(local_rag_agent.upload_pdf(
                                file_path=temp_pdf_path,
                                filename=uploaded_pdf.name,  # Pass original filename
                                extract_now=True
                            ))

                            # Clean up temp file
                            Path(temp_pdf_path).unlink(missing_ok=True)

                            st.divider()

                            if result.get("success"):
                                st.success("✅ PDF extraction completed successfully!")

                                extraction = result.get("extraction", {})
                                col1, col2, col3 = st.columns(3)
                                col1.metric("Pages Extracted", extraction.get("pages", 0))
                                col2.metric("Tables Found", extraction.get("tables", 0))
                                output_file = extraction.get("json_path", "N/A")
                                col3.metric("Output File", output_file.split("\\")[-1] if output_file != "N/A" else "N/A")

                                st.info(f"📁 Extracted data saved to: `{output_file}`")
                                st.caption(f"**Original filename:** {result.get('file_name', 'Unknown')}")

                                with st.expander("📋 View Extraction Details"):
                                    st.json(result)

                            elif "error" in result:
                                st.error(f"❌ Extraction Error: {result['error']}")
                                with st.expander("📋 View Error Details"):
                                    st.json(result)
                            else:
                                st.warning("⚠️ Extraction incomplete")
                                st.json(result)

                        except Exception as e:
                            st.error(f"❌ PDF extraction failed: {str(e)}")
                            logger.error(f"Local RAG PDF extraction error: {str(e)}", exc_info=True)

        elif local_rag_mode == "Prepare Pipeline":
            st.subheader("🔧 Prepare Local RAG Pipeline")
            st.markdown("Prepare the RAG pipeline from extracted JSON file.")

            # Get list of extracted JSON files
            data_dir = Path("data/processed")
            if data_dir.exists():
                json_files = list(data_dir.glob("*_extracted.json"))

                if json_files:
                    selected_json = st.selectbox(
                        "Select Extracted JSON File",
                        options=[f.name for f in json_files],
                        help="Choose a previously extracted document"
                    )

                    if selected_json:
                        json_path = data_dir / selected_json

                        # Preview JSON metadata
                        with st.expander("📊 Preview Extraction Metadata"):
                            try:
                                import json
                                with open(json_path, "r", encoding="utf-8") as f:
                                    data = json.load(f)

                                col1, col2 = st.columns(2)
                                col1.metric("Pages", len(data.get("pages", [])))
                                col2.metric("Tables", len(data.get("tables", [])))

                                st.caption(f"Source PDF: {data.get('metadata', {}).get('source_pdf', 'N/A')}")
                            except Exception as e:
                                st.error(f"Failed to preview: {str(e)}")

                        if st.button("🚀 Prepare Pipeline", type="primary", use_container_width=True):
                            with st.spinner("Preparing local RAG pipeline..."):
                                try:
                                    # Lazy-load agent
                                    if local_rag_agent is None:
                                        local_rag_agent = LocalRAGAgent()

                                    import asyncio
                                    result = asyncio.run(local_rag_agent.prepare_pipeline(
                                        json_path=str(json_path)
                                    ))

                                    st.divider()

                                    if result.get("success"):
                                        st.success("✅ Local RAG Pipeline prepared successfully!")

                                        col1, col2, col3 = st.columns(3)
                                        col1.metric("Documents", result.get("doc_count", 0))
                                        col2.metric("Chunks", result.get("chunks_count", 0))
                                        col3.metric("Embeddings", result.get("chunks_count", 0))  # Same as chunks

                                        st.info(f"📁 Collection: `{result.get('collection_name', 'N/A')}`")

                                        with st.expander("📋 View Full Response"):
                                            st.json(result)

                                    elif "error" in result:
                                        st.error(f"❌ Preparation Error: {result['error']}")
                                        with st.expander("📋 View Error Details"):
                                            st.json(result)
                                    else:
                                        st.warning("⚠️ Preparation incomplete")
                                        st.json(result)

                                except Exception as e:
                                    st.error(f"❌ Pipeline preparation failed: {str(e)}")
                                    logger.error(f"Local RAG preparation error: {str(e)}", exc_info=True)
                else:
                    st.warning("📂 No extracted JSON files found. Please upload and extract a PDF first.")
            else:
                st.warning(f"📂 Directory `data/processed` not found. Please upload and extract a PDF first.")

        else:  # Query Documents
            st.subheader("🔍 Query Local Documents")
            st.markdown("Ask questions about uploaded documents using local RAG.")

            with st.form("query_local_rag_form"):
                question = st.text_area(
                    "Your Question *",
                    placeholder="e.g., What is the coverage for chiropractic care? Are there any visit limits?",
                    help="Ask any question about the uploaded documents",
                    height=100
                )

                col1, col2 = st.columns(2)

                with col1:
                    top_k = st.slider(
                        "Number of documents to retrieve",
                        min_value=1,
                        max_value=20,
                        value=10,
                        help="How many relevant chunks to retrieve",
                        key="local_rag_top_k"
                    )

                with col2:
                    rerank_top_n = st.slider(
                        "Top documents after reranking",
                        min_value=1,
                        max_value=10,
                        value=5,
                        help="How many top chunks to use for answer generation",
                        key="local_rag_rerank_top_n"
                    )

                collection_name = st.text_input(
                    "Collection Name (Optional)",
                    placeholder="Leave empty for default collection",
                    help="Specify ChromaDB collection name"
                )

                submit = st.form_submit_button("🔍 Query", type="primary", use_container_width=True)

            if submit:
                if not question.strip():
                    st.error("❌ Please enter a question")
                else:
                    with st.spinner("Querying local documents..."):
                        try:
                            # Lazy-load agent
                            if local_rag_agent is None:
                                local_rag_agent = LocalRAGAgent()

                            import asyncio
                            result = asyncio.run(local_rag_agent.query(
                                question=question,
                                collection_name=collection_name if collection_name else "local_benefit_coverage",
                                k=rerank_top_n,  # Use rerank_top_n as final number of docs
                                use_reranker=True
                            ))

                            st.divider()

                            if result.get("success"):
                                st.success("✅ Query completed successfully!")

                                # Display answer
                                st.subheader("💡 Answer")
                                st.markdown(result.get("answer", "No answer generated"))

                                st.divider()

                                # Display sources
                                sources = result.get("sources", [])
                                if sources:
                                    st.subheader("📚 Sources")
                                    for idx, source in enumerate(sources, 1):
                                        # Extract page from metadata
                                        metadata = source.get("metadata", {})
                                        page_num = metadata.get("page", "N/A")
                                        similarity_score = source.get("similarity_score", 0)

                                        with st.expander(f"Source {idx} - Page {page_num} (Score: {similarity_score:.3f})"):
                                            st.markdown(source.get("content", "No text available"))
                                            st.caption(f"**Metadata:** {metadata}")

                                with st.expander("📋 View Full Response"):
                                    st.json(result)

                            elif "error" in result:
                                st.error(f"❌ Query Error: {result['error']}")
                                with st.expander("📋 View Error Details"):
                                    st.json(result)
                            else:
                                st.warning("⚠️ Query incomplete")
                                st.json(result)

                        except Exception as e:
                            st.error(f"❌ Query failed: {str(e)}")
                            logger.error(f"Local RAG query error: {str(e)}", exc_info=True)

    # Tab 11: AI Orchestration
    with tab11:
        st.header("🎯 AI-Powered Orchestration Agent")
        st.markdown("Intelligent multi-agent routing powered by AWS Bedrock Claude Sonnet 4.5")

        st.info("""
        **How it works:**
        1. **Analyze**: AI analyzes your natural language query
        2. **Classify**: Identifies intent (member verification, deductible lookup, etc.)
        3. **Extract**: Extracts entities (member IDs, service types, etc.)
        4. **Route**: Automatically routes to the appropriate specialized agent
        5. **Execute**: Runs the agent workflow and returns results

        **Available Agents:**
        - 👤 Member Verification
        - 💰 Deductible/OOP Lookup
        - 🏥 Benefit Accumulator
        - 📚 Benefit Coverage RAG
        - 📁 Local RAG
        """)

        # Mode selection
        orch_mode = st.radio(
            "Operation Mode",
            ["Single Query", "Batch Queries", "Conversation History"],
            horizontal=True,
            key="orchestration_mode"
        )

        if orch_mode == "Single Query":
            st.subheader("🔍 Process Single Query")
            st.markdown("Ask any question in natural language - the AI will route it to the right agent!")

            with st.form("orchestration_single_form"):
                # Query input
                query = st.text_area(
                    "Your Question *",
                    placeholder="Examples:\n- Is member M1001 active?\n- What is the deductible for member M1234?\n- How many massage visits has member M5678 used?\n- Is acupuncture covered under the plan?",
                    help="Ask any question - the AI will understand and route it appropriately",
                    height=120,
                    key="orch_single_query"
                )

                # Options
                col1, col2 = st.columns(2)
                with col1:
                    preserve_history = st.checkbox(
                        "Preserve conversation history",
                        value=False,
                        help="Maintain query history for this session"
                    )

                with col2:
                    show_reasoning = st.checkbox(
                        "Show AI reasoning",
                        value=True,
                        help="Display intent classification and entity extraction"
                    )

                submit = st.form_submit_button("🚀 Process Query", type="primary", use_container_width=True)

            if submit:
                if not query.strip():
                    st.error("❌ Please enter a query")
                else:
                    with st.spinner("🤖 AI is analyzing your query and routing to appropriate agent..."):
                        try:
                            # Lazy-load orchestration agent
                            if orchestration_agent is None:
                                orchestration_agent = OrchestrationAgent()

                            import asyncio
                            result = asyncio.run(orchestration_agent.process_query(
                                query=query,
                                context={},
                                preserve_history=preserve_history
                            ))

                            st.divider()

                            # Display results
                            if result.get("success"):
                                st.success(f"✅ Query processed successfully by **{result.get('agent', 'Unknown')}**")

                                # Show AI reasoning if enabled
                                if show_reasoning:
                                    with st.expander("🧠 AI Reasoning & Intent Classification", expanded=True):
                                        col1, col2, col3 = st.columns(3)
                                        col1.metric("Intent", result.get("intent", "Unknown"))
                                        col2.metric("Confidence", f"{result.get('confidence', 0):.0%}")
                                        col3.metric("Routed To", result.get("agent", "Unknown"))

                                        st.markdown("**Classification Reasoning:**")
                                        st.info(result.get("reasoning", "No reasoning provided"))

                                        # Show extracted entities
                                        entities = result.get("extracted_entities", {})
                                        if entities:
                                            st.markdown("**Extracted Entities:**")
                                            st.json(entities)

                                st.divider()

                                # Display agent result based on intent
                                intent = result.get("intent")
                                agent_result = result.get("result", {})

                                st.subheader("📊 Agent Response")

                                if intent == "member_verification":
                                    if agent_result.get("valid"):
                                        st.success("✅ Member Verified Successfully!")
                                        col1, col2, col3 = st.columns(3)
                                        col1.metric("Member ID", agent_result.get("member_id", "N/A"))
                                        col2.metric("Name", agent_result.get("name", "N/A"))
                                        col3.metric("DOB", agent_result.get("dob", "N/A"))
                                    else:
                                        st.warning("⚠️ Member Not Found")
                                        st.info(agent_result.get("message", "Verification failed"))

                                elif intent == "deductible_oop":
                                    if agent_result.get("found"):
                                        st.success(f"💰 Deductible/OOP Data for {agent_result['member_id']}")

                                        # Show summary metrics
                                        ind_ppo = agent_result.get("individual", {}).get("ppo", {})
                                        col1, col2, col3, col4 = st.columns(4)
                                        col1.metric("Deductible", ind_ppo.get("deductible", "N/A"))
                                        col2.metric("Deductible Met", ind_ppo.get("deductible_met", "N/A"))
                                        col3.metric("OOP Max", ind_ppo.get("oop", "N/A"))
                                        col4.metric("OOP Met", ind_ppo.get("oop_met", "N/A"))
                                    else:
                                        st.warning("⚠️ No deductible/OOP data found")

                                elif intent == "benefit_accumulator":
                                    if agent_result.get("found"):
                                        benefits = agent_result.get("benefits", [])
                                        st.success(f"📊 Found {len(benefits)} Benefit(s)")

                                        if benefits:
                                            df = pd.DataFrame(benefits)
                                            st.dataframe(df, use_container_width=True)
                                    else:
                                        st.warning("⚠️ No benefit data found")

                                elif intent in ["benefit_coverage_rag", "local_rag"]:
                                    if "answer" in agent_result:
                                        st.markdown("**Answer:**")
                                        st.markdown(agent_result.get("answer"))

                                        sources = agent_result.get("sources", [])
                                        if sources:
                                            with st.expander(f"📚 View {len(sources)} Source(s)"):
                                                for idx, source in enumerate(sources, 1):
                                                    st.markdown(f"**Source {idx}:**")
                                                    st.text(source.get("text", source.get("content", "No text"))[:200] + "...")
                                    else:
                                        st.error(agent_result.get("error", "Query failed"))

                                elif intent == "general_inquiry":
                                    st.info(agent_result.get("message", "General inquiry processed"))

                                # Show full response
                                with st.expander("📋 View Full Response"):
                                    st.json(result)

                            elif "error" in result:
                                error_msg = result['error']

                                # Check if it's a rate limiting error
                                if "ThrottlingException" in error_msg or "Too many requests" in error_msg:
                                    st.warning("⚠️ **AWS Bedrock Rate Limit Reached**")
                                    st.info("""
                                    The orchestration agent hit AWS Bedrock's rate limits.

                                    **What this means:**
                                    - You're making requests too quickly
                                    - AWS Bedrock has usage quotas

                                    **Solutions:**
                                    1. **Wait 30-60 seconds** and try again
                                    2. **Use specific agent tabs directly** (Benefit Coverage RAG, Member Verification, etc.) - these work independently
                                    3. **Request quota increase** in AWS Console → Bedrock → Service Quotas

                                    **Note:** The underlying agents work fine! Only the orchestration routing is throttled.
                                    """)
                                else:
                                    st.error(f"❌ Orchestration Error: {error_msg}")

                                if show_reasoning:
                                    with st.expander("🧠 AI Classification Details"):
                                        st.info(f"**Intent:** {result.get('intent', 'Unknown')}")
                                        st.info(f"**Confidence:** {result.get('confidence', 0):.0%}")

                                with st.expander("📋 View Error Details"):
                                    st.json(result)
                            else:
                                st.warning("⚠️ Query processing incomplete")
                                st.json(result)

                        except Exception as e:
                            st.error(f"❌ Orchestration failed: {str(e)}")
                            logger.error(f"Orchestration error: {str(e)}", exc_info=True)

        elif orch_mode == "Batch Queries":
            st.subheader("📦 Process Batch Queries")
            st.markdown("Process multiple queries simultaneously with intelligent routing")

            # Batch input method
            batch_method = st.radio(
                "Input Method",
                ["Manual Entry", "Upload CSV"],
                horizontal=True,
                key="batch_method"
            )

            if batch_method == "Manual Entry":
                with st.form("orchestration_batch_form"):
                    queries_text = st.text_area(
                        "Enter Queries (one per line) *",
                        placeholder="Is member M1001 active?\nWhat is the deductible for member M1234?\nHow many massage visits has member M5678 used?\nIs acupuncture covered?",
                        help="Enter one query per line",
                        height=150
                    )

                    submit = st.form_submit_button("🚀 Process All Queries", type="primary", use_container_width=True)

                if submit:
                    queries = [q.strip() for q in queries_text.split("\n") if q.strip()]

                    if not queries:
                        st.error("❌ Please enter at least one query")
                    else:
                        with st.spinner(f"🤖 Processing {len(queries)} queries..."):
                            try:
                                # Lazy-load orchestration agent
                                if orchestration_agent is None:
                                    orchestration_agent = OrchestrationAgent()

                                import asyncio
                                results = asyncio.run(orchestration_agent.process_batch(
                                    queries=queries,
                                    context={}
                                ))

                                st.divider()
                                st.subheader("📊 Batch Processing Results")

                                # Summary metrics
                                successful = sum(1 for r in results if r.get("success"))
                                failed = len(results) - successful

                                # Intent distribution
                                intent_counts = {}
                                for r in results:
                                    intent = r.get("intent", "unknown")
                                    intent_counts[intent] = intent_counts.get(intent, 0) + 1

                                col1, col2, col3 = st.columns(3)
                                col1.metric("Total Queries", len(results))
                                col2.metric("Successful", successful)
                                col3.metric("Failed", failed)

                                # Intent distribution chart
                                st.markdown("**Intent Distribution:**")
                                intent_df = pd.DataFrame(
                                    list(intent_counts.items()),
                                    columns=["Intent", "Count"]
                                )
                                st.bar_chart(intent_df.set_index("Intent"))

                                st.divider()

                                # Individual results
                                st.subheader("📝 Individual Results")
                                for idx, result in enumerate(results, 1):
                                    query = queries[idx-1]
                                    status_icon = "✅" if result.get("success") else "❌"

                                    with st.expander(f"{status_icon} Query {idx}: {query[:60]}..."):
                                        col1, col2 = st.columns(2)
                                        col1.metric("Intent", result.get("intent", "Unknown"))
                                        col2.metric("Agent", result.get("agent", "Unknown"))

                                        st.json(result)

                            except Exception as e:
                                st.error(f"❌ Batch processing failed: {str(e)}")
                                logger.error(f"Batch orchestration error: {str(e)}", exc_info=True)

            else:  # Upload CSV
                st.markdown("Upload a CSV file with queries. CSV should have a 'query' column.")

                csv_file = st.file_uploader(
                    "Choose CSV file",
                    type=["csv"],
                    key="batch_orch_csv"
                )

                if csv_file:
                    try:
                        df = pd.read_csv(csv_file)

                        if "query" not in df.columns:
                            st.error("❌ CSV must have a 'query' column")
                        else:
                            st.write(f"**Loaded:** {len(df)} queries")

                            with st.expander("📊 Preview Queries"):
                                st.dataframe(df.head(10))

                            if st.button("🚀 Process All Queries", type="primary", use_container_width=True):
                                queries = df["query"].tolist()

                                with st.spinner(f"🤖 Processing {len(queries)} queries..."):
                                    try:
                                        # Lazy-load orchestration agent
                                        if orchestration_agent is None:
                                            orchestration_agent = OrchestrationAgent()

                                        import asyncio
                                        results = asyncio.run(orchestration_agent.process_batch(
                                            queries=queries,
                                            context={}
                                        ))

                                        st.divider()
                                        st.subheader("📊 Batch Processing Results")

                                        # Add results to dataframe
                                        df["intent"] = [r.get("intent") for r in results]
                                        df["agent"] = [r.get("agent") for r in results]
                                        df["success"] = [r.get("success") for r in results]
                                        df["confidence"] = [r.get("confidence") for r in results]

                                        # Summary
                                        successful = df["success"].sum()
                                        col1, col2, col3 = st.columns(3)
                                        col1.metric("Total", len(df))
                                        col2.metric("Successful", successful)
                                        col3.metric("Failed", len(df) - successful)

                                        # Show results table
                                        st.dataframe(df, use_container_width=True)

                                        # Download results
                                        csv_results = df.to_csv(index=False)
                                        st.download_button(
                                            label="📥 Download Results CSV",
                                            data=csv_results,
                                            file_name=f"orchestration_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                            mime="text/csv"
                                        )

                                    except Exception as e:
                                        st.error(f"❌ Batch processing failed: {str(e)}")
                                        logger.error(f"CSV batch orchestration error: {str(e)}", exc_info=True)

                    except Exception as e:
                        st.error(f"❌ Failed to load CSV: {str(e)}")

        else:  # Conversation History
            st.subheader("💬 Conversation History")
            st.markdown("View and manage conversation history for this session")

            # Get history button
            if st.button("🔍 View History", type="primary"):
                try:
                    # Lazy-load orchestration agent
                    if orchestration_agent is None:
                        orchestration_agent = OrchestrationAgent()

                    history = orchestration_agent.get_conversation_history()

                    if not history:
                        st.info("📭 No conversation history yet. Enable 'Preserve conversation history' when processing queries.")
                    else:
                        st.success(f"📜 Found {len(history)} interactions")

                        # Display as table
                        df_history = pd.DataFrame(history)
                        st.dataframe(df_history, use_container_width=True)

                        st.divider()

                        # Individual interactions
                        st.subheader("💬 Detailed History")
                        for idx, interaction in enumerate(history, 1):
                            status_icon = "✅" if interaction.get("success") else "❌"

                            with st.expander(f"{status_icon} Interaction {idx}: {interaction.get('query', '')[:60]}..."):
                                col1, col2, col3 = st.columns(3)
                                col1.metric("Intent", interaction.get("intent", "Unknown"))
                                col2.metric("Confidence", f"{interaction.get('confidence', 0):.0%}")
                                col3.metric("Agent", interaction.get("agent", "Unknown"))

                except Exception as e:
                    st.error(f"❌ Failed to retrieve history: {str(e)}")

            # Clear history button
            st.divider()
            if st.button("🗑️ Clear History", type="secondary"):
                try:
                    if orchestration_agent is None:
                        orchestration_agent = OrchestrationAgent()

                    orchestration_agent.clear_conversation_history()
                    st.success("✅ Conversation history cleared!")
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ Failed to clear history: {str(e)}")


if __name__ == "__main__":
    main()