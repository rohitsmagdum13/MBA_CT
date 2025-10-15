# Local RAG Agent Setup Guide

Complete guide to install and verify all dependencies for the Local RAG Agent.

---

## 📋 Prerequisites

- Python 3.10+ with uv package manager
- Windows 10/11 (PowerShell)
- Administrator access (for Java installation)

---

## 🚀 Quick Installation

### Option 1: Automated Installation (Recommended)

Run the automated installation script:

```batch
# In your terminal (from MBA_CT directory)
install_local_rag_deps.bat
```

This script will:
- ✅ Install all Python dependencies from requirements.txt
- ✅ Check for Java installation
- ✅ Provide instructions if Java is missing

---

### Option 2: Manual Step-by-Step Installation

#### Step 1: Install Java (Required for Tabula)

**Using Chocolatey (Recommended):**

1. Open **PowerShell as Administrator**
2. Run the Java installation script:

```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force
.\install_java.ps1
```

**Manual Installation:**

1. Download OpenJDK from: https://adoptium.net/
2. Run the installer
3. Verify installation: `java -version`

---

#### Step 2: Install Python Dependencies

```bash
uv pip install -r requirements.txt
```

This installs:
- **PyMuPDF** - PDF text extraction
- **Tabula-py** - PDF table extraction
- **Sentence Transformers** - Local embeddings (384-dim)
- **ChromaDB** - Local vector database
- **Cross-Encoder** - Local reranking
- **pdfplumber** - Alternative PDF processing

---

#### Step 3: Verify Installation

Run the verification script:

```bash
python verify_local_rag.py
```

This will test:
- ✅ Java installation
- ✅ PyMuPDF
- ✅ Tabula
- ✅ pdfplumber
- ✅ Sentence Transformers (will download ~90 MB model on first run)
- ✅ ChromaDB
- ✅ Cross-Encoder (will download ~80 MB model on first run)

**Expected Output:**

```
============================================================================
VERIFICATION SUMMARY
============================================================================
✅ Java
✅ PyMuPDF
✅ Tabula
✅ pdfplumber
✅ Sentence Transformers
✅ ChromaDB
✅ Cross-Encoder

============================================================================
🎉 ALL TESTS PASSED!
============================================================================
```

---

## 📦 What Gets Downloaded?

On first run, these AI models are downloaded and cached locally:

| Model | Size | Purpose | Cache Location |
|-------|------|---------|----------------|
| `all-MiniLM-L6-v2` | ~90 MB | Sentence embeddings (384-dim) | `~/.cache/huggingface/` |
| `ms-marco-MiniLM-L-6-v2` | ~80 MB | Cross-encoder reranking | `~/.cache/huggingface/` |

Total download: **~170 MB** (one-time only)

---

## 🧪 Testing the Local RAG Agent

After successful installation:

### 1. Start Streamlit App

```bash
uv run mba-app
```

### 2. Navigate to "Local RAG" Tab

The app will open in your browser. Click on the **"📁 Local RAG"** tab (Tab 10).

### 3. Upload a PDF

**Mode: Upload PDF**
- Click file uploader
- Select `benefit_coverage.pdf` (or any PDF)
- Click **"🚀 Extract Content"**
- Wait for extraction (text + tables)

### 4. Prepare RAG Pipeline

**Mode: Prepare Pipeline**
- Select your extracted JSON file
- Preview metadata
- Click **"🚀 Prepare Pipeline"**
- Wait for embeddings generation

### 5. Query the Document

**Mode: Query Documents**
- Enter a question (e.g., "Is massage therapy covered?")
- Adjust retrieval parameters:
  - **Number of documents to retrieve**: 10
  - **Top documents after reranking**: 5
- Click **"🔍 Query"**
- View answer with source citations!

---

## 📝 Example Queries (for benefit_coverage.pdf)

Try these queries to test the system:

### Basic Coverage Questions
1. **"Is massage therapy covered?"**
2. **"What is the deductible for this plan?"**
3. **"What is the out-of-pocket maximum?"**
4. **"Are chiropractic services covered?"**
5. **"What is the emergency room copay?"**

### Specific Benefit Questions
6. **"What services require preauthorization?"**
7. **"Is acupuncture covered and what are the limits?"**
8. **"What is the hearing aid benefit?"**
9. **"Are preventive services covered at 100%?"**
10. **"What is the home health care visit limit?"**

### Complex Questions
11. **"Which services have the deductible waived?"**
12. **"What mental health benefits are available?"**
13. **"Is infertility treatment covered?"**
14. **"What is covered for newborns?"**
15. **"What are the ambulance coverage limits?"**

---

## 🔧 Troubleshooting

### Java Not Found

**Error:** `java: command not found`

**Solution:**
1. Install Java using `install_java.ps1` (as Administrator)
2. **Restart your terminal**
3. Verify: `java -version`

---

### Import Error: "No module named 'fitz'"

**Solution:**
```bash
uv pip install PyMuPDF
```

---

### ChromaDB Error: "Could not import chromadb"

**Solution:**
```bash
uv pip install chromadb
```

---

### Sentence Transformers Model Download Fails

**Error:** Network error downloading models

**Solution:**
1. Check internet connection
2. Models are downloaded from Hugging Face Hub
3. If behind proxy, configure: `export HF_ENDPOINT=...`
4. Manual download: https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2

---

### Tabula Error: "JVMNotFoundException"

**Error:** Cannot start JVM

**Solution:**
1. Verify Java installed: `java -version`
2. Check JAVA_HOME environment variable
3. Reinstall Java and restart terminal

---

## 📚 Architecture

```
Local RAG Pipeline Flow:
┌─────────────────────────────────────────────────────────────────┐
│ 1. PDF Upload                                                   │
│    └─> PyMuPDF (text) + Tabula (tables) → JSON                 │
├─────────────────────────────────────────────────────────────────┤
│ 2. Prepare Pipeline                                             │
│    ├─> Load JSON                                                │
│    ├─> Intelligent Chunking (600-1500 chars)                    │
│    ├─> Generate Embeddings (Sentence Transformers, 384-dim)     │
│    └─> Store in ChromaDB (local vector DB)                      │
├─────────────────────────────────────────────────────────────────┤
│ 3. Query                                                        │
│    ├─> Encode query (Sentence Transformers)                     │
│    ├─> Semantic search (ChromaDB, retrieve top-k)               │
│    ├─> Rerank results (Cross-Encoder)                           │
│    └─> Generate answer (AWS Bedrock Claude)                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🎯 Key Features

### ✅ Privacy-First
- All document processing happens locally
- No external API calls for text extraction or embeddings
- Only Bedrock Claude called for final answer generation

### ✅ Cost-Effective
- Free local processing (text, tables, embeddings, vector storage)
- Only pay for Bedrock Claude API calls (~$0.003 per query)

### ✅ Fast
- Local processing eliminates network latency
- ChromaDB provides sub-second vector search
- Sentence Transformers: ~1000 tokens/sec on CPU

### ✅ Offline Capable
- Works without internet (except for final LLM answer)
- Perfect for sensitive documents that can't leave your network

---

## 📊 Performance Benchmarks

| Operation | Time | Details |
|-----------|------|---------|
| PDF Upload + Extract | ~2-5 sec | For 5-page PDF with tables |
| Prepare Pipeline | ~10-30 sec | Depends on document size |
| Query (search + rerank) | ~0.5-2 sec | Local operations only |
| Answer Generation | ~2-5 sec | AWS Bedrock Claude API |
| **Total Query Time** | **~3-7 sec** | End-to-end |

---

## 🆚 Local RAG vs Cloud RAG

| Feature | Local RAG | Cloud RAG |
|---------|-----------|-----------|
| **Text Extraction** | PyMuPDF (local) | AWS Textract |
| **Table Extraction** | Tabula (local) | AWS Textract |
| **Embeddings** | Sentence Transformers (384-dim) | Bedrock Titan (1536-dim) |
| **Vector Store** | ChromaDB (local) | OpenSearch/Qdrant |
| **Reranking** | Cross-Encoder (local) | Bedrock Cohere |
| **Cost per Query** | ~$0.003 (LLM only) | ~$0.02-0.05 |
| **Privacy** | ✅ Full | ⚠️ Cloud processing |
| **Offline** | ✅ Mostly | ❌ Requires internet |
| **Setup** | Java + Python packages | AWS services |

---

## 💡 When to Use Local RAG

**Use Local RAG when:**
- Processing sensitive/confidential documents
- Need offline capability
- Want to minimize cloud costs
- Developing/testing without cloud charges
- Don't have AWS Textract output

**Use Cloud RAG when:**
- Already using AWS Textract for OCR
- Need highest accuracy embeddings (1536-dim)
- Want advanced reranking (Bedrock Cohere)
- Have complex PDF layouts requiring Textract

---

## 📞 Support

If you encounter issues:

1. Run `python verify_local_rag.py` to diagnose
2. Check the troubleshooting section above
3. Verify all dependencies installed: `uv pip list`
4. Check logs in Streamlit app for detailed errors

---

## ✅ Next Steps

After successful setup:

1. ✅ Verified all dependencies
2. ✅ Tested with sample PDF
3. ✅ Queried documents successfully

**You're ready to use the Local RAG Agent!**

Start the app and navigate to the "Local RAG" tab:
```bash
uv run mba-app
```

---

**Happy Querying! 🚀**
