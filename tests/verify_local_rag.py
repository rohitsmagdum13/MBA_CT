"""
Verification script for Local RAG dependencies.

This script tests all required libraries for the Local RAG Agent:
- PyMuPDF (fitz) for PDF text extraction
- Tabula for PDF table extraction
- Sentence Transformers for local embeddings
- ChromaDB for local vector storage
- Cross-encoder for reranking

Run this script after installing requirements.txt to verify everything is working.
"""

import sys
import os
from pathlib import Path

# Fix Windows console encoding for emojis
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')


def test_pymupdf():
    """Test PyMuPDF installation."""
    print("\n" + "=" * 60)
    print("Testing PyMuPDF (PDF Text Extraction)")
    print("=" * 60)
    try:
        import fitz
        print(f"✅ PyMuPDF installed successfully")
        print(f"   Version: {fitz.version}")
        print(f"   VersionBind: {fitz.VersionBind}")
        return True
    except ImportError as e:
        print(f"❌ PyMuPDF not installed: {e}")
        print("   Install with: uv pip install PyMuPDF")
        return False


def test_tabula():
    """Test Tabula installation."""
    print("\n" + "=" * 60)
    print("Testing Tabula (PDF Table Extraction)")
    print("=" * 60)
    try:
        import tabula
        print(f"✅ Tabula-py installed successfully")

        # Test Java availability
        try:
            import jpype
            if jpype.isJVMStarted():
                print(f"   ✅ JVM already running")
            else:
                print(f"   ⚠️  JVM not started yet (will start on first use)")
            print(f"   JPype version: {jpype.__version__}")
        except Exception as e:
            print(f"   ⚠️  JPype warning: {e}")

        print(f"\n   📌 NOTE: Tabula requires Java 8+ to be installed")
        print(f"   To check Java: run 'java -version' in terminal")
        print(f"   To install Java on Windows: choco install openjdk")
        return True
    except ImportError as e:
        print(f"❌ Tabula not installed: {e}")
        print("   Install with: uv pip install tabula-py jpype1")
        return False


def test_sentence_transformers():
    """Test Sentence Transformers installation."""
    print("\n" + "=" * 60)
    print("Testing Sentence Transformers (Local Embeddings)")
    print("=" * 60)
    try:
        from sentence_transformers import SentenceTransformer
        print(f"✅ Sentence Transformers installed successfully")

        # Try loading the model
        print(f"\n   Loading embedding model 'all-MiniLM-L6-v2'...")
        print(f"   (First run will download ~90 MB model)")

        model = SentenceTransformer('all-MiniLM-L6-v2')
        print(f"   ✅ Model loaded successfully")
        print(f"   Model max sequence length: {model.max_seq_length}")
        print(f"   Embedding dimension: {model.get_sentence_embedding_dimension()}")

        # Test encoding
        test_text = "This is a test sentence."
        embedding = model.encode(test_text)
        print(f"\n   Testing encoding...")
        print(f"   ✅ Generated embedding shape: {embedding.shape}")

        return True
    except ImportError as e:
        print(f"❌ Sentence Transformers not installed: {e}")
        print("   Install with: uv pip install sentence-transformers torch transformers")
        return False
    except Exception as e:
        print(f"❌ Error loading model: {e}")
        return False


def test_chromadb():
    """Test ChromaDB installation."""
    print("\n" + "=" * 60)
    print("Testing ChromaDB (Local Vector Database)")
    print("=" * 60)
    try:
        import chromadb
        print(f"✅ ChromaDB installed successfully")
        print(f"   Version: {chromadb.__version__}")

        # Create ephemeral client for testing
        client = chromadb.Client()
        print(f"   ✅ ChromaDB client created")

        # Test collection creation
        collection = client.create_collection("test_collection")
        print(f"   ✅ Test collection created")

        # Test adding documents
        collection.add(
            documents=["This is a test document"],
            ids=["test_id_1"]
        )
        print(f"   ✅ Document added to collection")

        # Test querying
        results = collection.query(
            query_texts=["test document"],
            n_results=1
        )
        print(f"   ✅ Query executed successfully")

        # Clean up
        client.delete_collection("test_collection")
        print(f"   ✅ Test collection cleaned up")

        return True
    except ImportError as e:
        print(f"❌ ChromaDB not installed: {e}")
        print("   Install with: uv pip install chromadb")
        return False
    except Exception as e:
        print(f"❌ Error testing ChromaDB: {e}")
        return False


def test_cross_encoder():
    """Test Cross-encoder for reranking."""
    print("\n" + "=" * 60)
    print("Testing Cross-Encoder (Local Reranking)")
    print("=" * 60)
    try:
        from sentence_transformers import CrossEncoder
        print(f"✅ Cross-Encoder support available")

        # Try loading reranker model
        print(f"\n   Loading reranker model 'cross-encoder/ms-marco-MiniLM-L-6-v2'...")
        print(f"   (First run will download ~80 MB model)")

        reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
        print(f"   ✅ Reranker model loaded successfully")

        # Test reranking
        query = "What is the capital of France?"
        documents = [
            "Paris is the capital of France.",
            "London is the capital of England.",
            "Berlin is the capital of Germany."
        ]

        scores = reranker.predict([(query, doc) for doc in documents])
        print(f"\n   Testing reranking...")
        print(f"   ✅ Generated {len(scores)} relevance scores")
        print(f"   Top score: {max(scores):.4f} (should be for Paris)")

        return True
    except ImportError as e:
        print(f"❌ Cross-Encoder not available: {e}")
        return False
    except Exception as e:
        print(f"❌ Error loading cross-encoder: {e}")
        return False


def test_pdfplumber():
    """Test pdfplumber installation."""
    print("\n" + "=" * 60)
    print("Testing pdfplumber (Alternative PDF Processing)")
    print("=" * 60)
    try:
        import pdfplumber
        print(f"✅ pdfplumber installed successfully")
        print(f"   Version: {pdfplumber.__version__}")
        return True
    except ImportError as e:
        print(f"❌ pdfplumber not installed: {e}")
        print("   Install with: uv pip install pdfplumber")
        return False


def check_java():
    """Check if Java is installed."""
    print("\n" + "=" * 60)
    print("Checking Java Installation (Required for Tabula)")
    print("=" * 60)

    import subprocess
    try:
        result = subprocess.run(
            ['java', '-version'],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            # Java version output goes to stderr
            version_output = result.stderr.split('\n')[0]
            print(f"✅ Java is installed")
            print(f"   {version_output}")
            return True
        else:
            print(f"❌ Java command failed")
            print(f"   Install Java: choco install openjdk")
            return False

    except FileNotFoundError:
        print(f"❌ Java is NOT installed")
        print(f"\n   📌 Installation instructions:")
        print(f"   Windows (with Chocolatey): choco install openjdk")
        print(f"   Windows (manual): Download from https://adoptium.net/")
        print(f"   After installing, restart your terminal")
        return False
    except Exception as e:
        print(f"❌ Error checking Java: {e}")
        return False


def main():
    """Run all verification tests."""
    print("\n" + "=" * 60)
    print("LOCAL RAG DEPENDENCIES VERIFICATION")
    print("=" * 60)
    print("This script will verify all Local RAG Agent dependencies")

    results = {}

    # Run all tests
    results['Java'] = check_java()
    results['PyMuPDF'] = test_pymupdf()
    results['Tabula'] = test_tabula()
    results['pdfplumber'] = test_pdfplumber()
    results['Sentence Transformers'] = test_sentence_transformers()
    results['ChromaDB'] = test_chromadb()
    results['Cross-Encoder'] = test_cross_encoder()

    # Summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)

    for component, status in results.items():
        icon = "✅" if status else "❌"
        print(f"{icon} {component}")

    all_passed = all(results.values())

    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ALL TESTS PASSED!")
        print("=" * 60)
        print("\nYour Local RAG Agent is ready to use!")
        print("\nNext steps:")
        print("1. Restart Streamlit app: uv run mba-app")
        print("2. Navigate to the 'Local RAG' tab (Tab 10)")
        print("3. Upload a PDF and start querying!")
    else:
        print("⚠️  SOME TESTS FAILED")
        print("=" * 60)
        print("\nPlease install missing dependencies:")
        print("1. Run: uv pip install -r requirements.txt")
        if not results['Java']:
            print("2. Install Java: choco install openjdk")
            print("3. Restart your terminal after Java installation")
        print("\nThen run this script again to verify.")

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
