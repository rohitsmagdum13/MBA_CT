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
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
        "📄 Single Upload",
        "📁 Multi Upload",
        "💾 CSV Ingestion",
        "👤 Member Verification",
        "💰 Deductible/OOP",
        "🏥 Benefit Accumulator",
        "🔍 View Duplicates",
        "🗄️ Database Tables"
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


if __name__ == "__main__":
    main()