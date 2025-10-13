# MBA Upload Service - Testing Guide

## Overview

This document provides comprehensive testing instructions for the MBA Upload Service, including both the FastAPI REST API and Streamlit web UI.

## Prerequisites

### Required Dependencies

Ensure all dependencies are installed:

```bash
# Using uv (recommended)
uv pip install -e .

# Or using pip
pip install -e .
```

### Environment Configuration

Create a `.env` file in the project root:

```env
# AWS Configuration
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=us-east-1

# S3 Configuration
S3_BUCKET_MBA=memberbenefitassistant-bucket
S3_PREFIX_MBA=mba/

# Server-Side Encryption
S3_SSE=AES256

# Logging
LOG_LEVEL=INFO
LOG_DIR=logs
LOG_FILE=app.log
```

## Project Structure

```
MBA_CT/
├── src/
│   └── MBA/
│       ├── core/                    # Core utilities
│       │   ├── exceptions.py        # Custom exceptions
│       │   ├── logging_config.py    # Logging setup
│       │   └── settings.py          # Configuration
│       ├── services/                # Reusable services
│       │   ├── s3_client.py         # S3 upload client
│       │   ├── file_utils.py        # File processing
│       │   └── duplicate_detector.py # Duplicate detection
│       ├── microservices/           # API services
│       │   └── api.py               # FastAPI endpoints
│       └── ui/                      # Web interfaces
│           └── streamlit_app.py     # Streamlit UI
├── .env                             # Environment variables
├── pyproject.toml                   # Project configuration
└── requirements.txt                 # Dependencies
```

## Testing the FastAPI Service

### 1. Start the API Server

Using the CLI entry point:

```bash
uv run mba-api
```

Or directly:

```bash
uv run fastapi dev src/MBA/microservices/api.py
```

The server will start at `http://localhost:8000`

### 2. Test Health Check

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "services": {
    "s3_client": "initialized",
    "file_processor": "initialized",
    "duplicate_detector": "initialized"
  }
}
```

### 3. Test Single File Upload

```bash
curl -X POST "http://localhost:8000/upload/single" \
  -F "file=@test_document.pdf"
```

Expected response:
```json
{
  "success": true,
  "s3_uri": "s3://memberbenefitassistant-bucket/mba/pdf/test_document.pdf",
  "file_name": "test_document.pdf",
  "document_type": "pdf",
  "is_duplicate": false,
  "duplicate_of": null,
  "content_hash": "2c26b46b68ffc68f..."
}
```

### 4. Test Multi-File Upload

```bash
curl -X POST "http://localhost:8000/upload/multi" \
  -F "files=@doc1.pdf" \
  -F "files=@doc2.xlsx" \
  -F "files=@doc3.txt"
```

Expected response:
```json
{
  "total": 3,
  "successful": 3,
  "failed": 0,
  "uploads": [
    {
      "success": true,
      "s3_uri": "s3://memberbenefitassistant-bucket/mba/pdf/doc1.pdf",
      "file_name": "doc1.pdf",
      "document_type": "pdf",
      "is_duplicate": false,
      "duplicate_of": null,
      "content_hash": "abc123..."
    },
    ...
  ],
  "errors": []
}
```

### 5. Interactive API Documentation

Visit the auto-generated API docs:

- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

## Testing the Streamlit UI

### 1. Start the Streamlit App

Using the CLI entry point:

```bash
uv run mba-app
```

Or directly:

```bash
uv run streamlit run src/MBA/ui/streamlit_app.py
```

The app will open at `http://localhost:8501`

### 2. Test Single Upload Tab

1. Navigate to the **"Single Upload"** tab
2. Click **"Browse files"** and select a test file
3. Review the file information displayed
4. Click **"🚀 Upload"** button
5. Verify the upload result shows:
   - S3 URI
   - Document type classification
   - Content hash
   - Duplicate detection status

### 3. Test Multi-Upload Tab

1. Navigate to the **"Multi Upload"** tab
2. Select multiple files (use Ctrl/Cmd+Click)
3. Review the file list in the expander
4. Click **"🚀 Upload All"** button
5. Monitor the progress bar
6. Review the summary statistics:
   - Total files
   - Successful uploads
   - Failed uploads
   - Duplicate count
7. Expand individual file results to see details

### 4. Test Duplicate Detection

1. Upload a file in Single Upload tab
2. Upload the same file again
3. Verify the second upload shows:
   - `⚠️ Duplicate Detected`
   - List of duplicate files
   - Same content hash as original

### 5. View Duplicates Tab

1. Navigate to **"View Duplicates"** tab
2. Browse detected duplicate groups
3. Each group shows:
   - Group number
   - File count
   - Content hash
   - List of duplicate file paths

### 6. Sidebar Features

Check the sidebar for:
- **Configuration:** Bucket and prefix info
- **Cache Statistics:** File counts and duplicate counts
- **Clear Cache:** Button to reset duplicate detection
- **Supported Formats:** List of allowed file types
- **Max File Size:** Upload size limit

## Document Type Routing

Files are automatically routed to folders based on type:

| Extension | Document Type | S3 Path |
|-----------|--------------|---------|
| `.pdf` | PDF | `mba/pdf/filename.pdf` |
| `.doc`, `.docx` | Word | `mba/word/filename.docx` |
| `.xls`, `.xlsx`, `.xlsm` | Excel | `mba/excel/filename.xlsx` |
| `.txt`, `.md`, `.csv`, `.json` | Text | `mba/text/filename.txt` |
| `.jpg`, `.png`, `.gif` | Image | `mba/image/filename.jpg` |
| `.zip`, `.tar`, `.gz` | Archive | `mba/archive/filename.zip` |

## Duplicate Detection

The system uses SHA-256 content hashing to detect duplicates:

1. **First upload** of a file:
   - Hash computed
   - Added to cache
   - Marked as unique

2. **Subsequent upload** of identical content:
   - Hash computed and matches existing
   - Marked as duplicate
   - List of original files provided
   - Still uploaded to S3 with metadata

## Testing Scenarios

### Scenario 1: Upload Different File Types

Test document type routing:

```bash
# Create test files
echo "Test content" > test.txt
echo "CSV content" > test.csv
touch test.pdf test.docx test.xlsx

# Upload via API
for file in test.*; do
  curl -X POST "http://localhost:8000/upload/single" -F "file=@$file"
done

# Verify routing in logs or S3:
# - test.txt  → mba/text/test.txt
# - test.csv  → mba/text/test.csv
# - test.pdf  → mba/pdf/test.pdf
# - test.docx → mba/word/test.docx
# - test.xlsx → mba/excel/test.xlsx
```

### Scenario 2: Test Duplicate Detection

```bash
# Upload original file
curl -X POST "http://localhost:8000/upload/single" \
  -F "file=@document.pdf" | jq .

# Create a copy with different name
cp document.pdf document_copy.pdf

# Upload copy (should detect duplicate)
curl -X POST "http://localhost:8000/upload/single" \
  -F "file=@document_copy.pdf" | jq .

# Verify: is_duplicate = true
```

### Scenario 3: Batch Upload with Mixed Results

```bash
# Create test files
echo "Valid content" > valid.txt
dd if=/dev/zero of=toolarge.bin bs=1M count=150  # Exceeds 100MB limit

# Upload both (one should fail validation)
curl -X POST "http://localhost:8000/upload/multi" \
  -F "files=@valid.txt" \
  -F "files=@toolarge.bin" | jq .

# Verify: successful=1, failed=1
```

## Troubleshooting

### Issue: Services Not Initialized

**Error:** `503 Service Unavailable: Services not initialized`

**Solution:**
1. Check `.env` file exists and has valid AWS credentials
2. Verify bucket name is correct
3. Check logs for initialization errors
4. Restart the service

### Issue: Upload Fails with Access Denied

**Error:** `Failed to upload: AccessDenied`

**Solution:**
1. Verify AWS credentials have S3 write permissions
2. Check bucket policy allows PutObject
3. Verify bucket exists in the specified region
4. Check IAM role/user permissions

### Issue: File Validation Failed

**Error:** `File validation failed`

**Possible causes:**
- File extension not in allowed list
- File size exceeds 100MB limit
- File is corrupted or empty

**Solution:**
1. Check file extension is supported
2. Verify file size is under limit
3. Ensure file is readable and not corrupted

### Issue: Streamlit Won't Start

**Error:** `ModuleNotFoundError: No module named 'streamlit'`

**Solution:**
```bash
uv pip install streamlit
# or
pip install streamlit
```

## Logs

View application logs:

```bash
# Real-time logs
tail -f logs/app.log

# Search for errors
grep ERROR logs/app.log

# View recent uploads
grep "Successfully uploaded" logs/app.log | tail -20
```

## Cleanup

Clear test data:

```bash
# Clear duplicate cache in Streamlit UI
# Or programmatically:
python -c "
from MBA.services.duplicate_detector import DuplicateDetector
detector = DuplicateDetector()
detector.clear_cache()
print('Cache cleared')
"

# Remove test files
rm -rf test.* document_copy.pdf
```

## Next Steps

1. **Production Deployment:**
   - Add authentication/authorization
   - Configure CORS policies
   - Set up monitoring and alerting
   - Use production-grade WSGI server

2. **Enhanced Features:**
   - Add file preview functionality
   - Implement search and filtering
   - Add batch operations (delete, move)
   - Enable file metadata editing

3. **Performance Optimization:**
   - Implement async uploads for large files
   - Add upload progress tracking
   - Cache frequently accessed data
   - Optimize duplicate detection for large datasets