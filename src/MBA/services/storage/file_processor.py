"""
File discovery and processing utilities for document ingestion.

This module provides the FileProcessor class for discovering, validating,
and routing files based on type. Includes path normalization, MIME type
detection, and intelligent document categorization.

Module Input:
    - Root directory paths for file discovery
    - File paths for validation and type inference
    - Document type routing rules

Module Output:
    - Lists of discovered file paths
    - Normalized, validated paths
    - Document type classifications
    - S3 key routing recommendations
"""

import mimetypes
from pathlib import Path
from typing import List, Set, Optional, Dict
from enum import Enum

from MBA.core.exceptions import FileDiscoveryError
from MBA.core.logging_config import get_logger

logger = get_logger(__name__)


class DocumentType(Enum):
    """
    Enumeration of supported document types for routing.
    
    Each document type maps to a specific S3 prefix or storage location,
    enabling organized file storage by category.
    
    Values:
        PDF: PDF documents (contracts, forms, reports)
        WORD: Microsoft Word documents (.doc, .docx)
        EXCEL: Microsoft Excel spreadsheets (.xls, .xlsx)
        CSV: CSV data files (.csv)
        TEXT: Plain text files (.txt, .md, .log)
        IMAGE: Image files (.jpg, .png, .gif)
        ARCHIVE: Compressed archives (.zip, .tar, .gz)
        UNKNOWN: Unrecognized or unsupported file types
    """
    PDF = "pdf"
    WORD = "word"
    EXCEL = "excel"
    CSV = "csv"
    TEXT = "text"
    IMAGE = "image"
    ARCHIVE = "archive"
    UNKNOWN = "unknown"


# Extension to DocumentType mapping
EXTENSION_TO_TYPE: Dict[str, DocumentType] = {
    ".pdf": DocumentType.PDF,
    ".doc": DocumentType.WORD,
    ".docx": DocumentType.WORD,
    ".xls": DocumentType.EXCEL,
    ".xlsx": DocumentType.EXCEL,
    ".xlsm": DocumentType.EXCEL,
    ".txt": DocumentType.TEXT,
    ".md": DocumentType.TEXT,
    ".log": DocumentType.TEXT,
    ".csv": DocumentType.CSV,
    ".json": DocumentType.TEXT,
    ".jpg": DocumentType.IMAGE,
    ".jpeg": DocumentType.IMAGE,
    ".png": DocumentType.IMAGE,
    ".gif": DocumentType.IMAGE,
    ".bmp": DocumentType.IMAGE,
    ".zip": DocumentType.ARCHIVE,
    ".tar": DocumentType.ARCHIVE,
    ".gz": DocumentType.ARCHIVE,
    ".7z": DocumentType.ARCHIVE,
}


class FileProcessor:
    """
    File discovery and routing processor for document ingestion.
    
    Provides utilities for discovering files in directory trees, validating
    paths, inferring document types, and generating appropriate S3 routing
    keys based on file characteristics.
    
    Attributes:
        allowed_extensions (Set[str]): Set of permitted file extensions
        follow_symlinks (bool): Whether to follow symbolic links
        max_file_size_mb (int): Maximum allowed file size in megabytes
        
    Thread Safety:
        Thread-safe for read operations. Not safe for concurrent
        modification of allowed_extensions.
    """
    
    def __init__(
        self,
        allowed_extensions: Optional[Set[str]] = None,
        follow_symlinks: bool = False,
        max_file_size_mb: int = 100
    ):
        """
        Initialize file processor with filtering rules.
        
        Args:
            allowed_extensions (Optional[Set[str]]): Set of allowed file
                extensions (e.g., {".pdf", ".docx"}). None allows all types.
            follow_symlinks (bool): Follow symbolic links during discovery
                (default: False)
            max_file_size_mb (int): Maximum file size in MB (default: 100)
            
        Side Effects:
            - Logs processor initialization
            - Initializes mimetypes database
        """
        self.allowed_extensions = (
            {ext.lower() for ext in allowed_extensions}
            if allowed_extensions else None
        )
        self.follow_symlinks = follow_symlinks
        self.max_file_size_mb = max_file_size_mb
        
        # Initialize mimetypes database
        mimetypes.init()
        
        logger.info(
            f"Initialized FileProcessor: "
            f"allowed_extensions={len(self.allowed_extensions) if self.allowed_extensions else 'all'}, "
            f"follow_symlinks={follow_symlinks}, "
            f"max_size={max_file_size_mb}MB"
        )
    
    def discover_files(
        self,
        root_path: Path,
        recursive: bool = True,
        exclude_patterns: Optional[List[str]] = None
    ) -> List[Path]:
        """
        Discover files in directory tree with filtering.
        
        Recursively scans directory for files matching configured criteria.
        Applies extension filtering, size limits, and pattern exclusions.
        
        Args:
            root_path (Path): Root directory to scan
            recursive (bool): Scan subdirectories recursively (default: True)
            exclude_patterns (Optional[List[str]]): Glob patterns to exclude
                (e.g., ["**/temp/**", "**/.git/**"])
                
        Returns:
            List[Path]: Sorted list of discovered file paths
            
        Raises:
            FileDiscoveryError: If root_path doesn't exist or isn't accessible
            
        Side Effects:
            - Logs discovery progress
            - May access filesystem extensively
            
        Example:
            >>> processor = FileProcessor(allowed_extensions={".pdf"})
            >>> files = processor.discover_files(
            ...     Path("/data/documents"),
            ...     exclude_patterns=["**/archive/**"]
            ... )
            >>> print(f"Found {len(files)} PDF files")
        """
        if not root_path.exists():
            raise FileDiscoveryError(
                f"Root path does not exist: {root_path}",
                details={"root_path": str(root_path)}
            )
        
        if not root_path.is_dir():
            raise FileDiscoveryError(
                f"Root path is not a directory: {root_path}",
                details={"root_path": str(root_path)}
            )
        
        logger.info(f"Starting file discovery in: {root_path}")
        
        discovered_files = []
        exclude_patterns = exclude_patterns or []
        
        try:
            # Choose recursive or non-recursive glob
            pattern = "**/*" if recursive else "*"
            
            for item in root_path.glob(pattern):
                # Skip directories
                if not item.is_file():
                    continue
                
                # Skip symlinks if not following
                if item.is_symlink() and not self.follow_symlinks:
                    logger.debug(f"Skipping symlink: {item}")
                    continue
                
                # Check exclusion patterns
                if any(item.match(pattern) for pattern in exclude_patterns):
                    logger.debug(f"Excluding by pattern: {item}")
                    continue
                
                # Check extension filter
                if self.allowed_extensions:
                    if item.suffix.lower() not in self.allowed_extensions:
                        logger.debug(f"Skipping unsupported extension: {item}")
                        continue
                
                # Check file size
                try:
                    size_mb = item.stat().st_size / (1024 * 1024)
                    if size_mb > self.max_file_size_mb:
                        logger.warning(
                            f"Skipping oversized file ({size_mb:.1f}MB): {item}"
                        )
                        continue
                except OSError as e:
                    logger.warning(f"Cannot stat file {item}: {e}")
                    continue
                
                discovered_files.append(item)
        
        except PermissionError as e:
            raise FileDiscoveryError(
                f"Permission denied accessing directory: {root_path}",
                details={"root_path": str(root_path), "error": str(e)}
            )
        except Exception as e:
            raise FileDiscoveryError(
                f"Error during file discovery: {str(e)}",
                details={"root_path": str(root_path), "error": str(e)}
            )
        
        # Sort for consistent ordering
        discovered_files.sort()
        
        logger.info(
            f"Discovered {len(discovered_files)} files in {root_path}"
        )
        
        return discovered_files
    
    def normalize_path(self, path: Path) -> Path:
        """
        Normalize and resolve file path.
        
        Converts path to absolute form, resolves symlinks (if configured),
        and validates path existence.
        
        Args:
            path (Path): Path to normalize
            
        Returns:
            Path: Normalized absolute path
            
        Raises:
            FileDiscoveryError: If path doesn't exist after normalization
            
        Example:
            >>> processor.normalize_path(Path("../docs/report.pdf"))
            PosixPath('/home/user/docs/report.pdf')
        """
        try:
            # Convert to absolute path
            abs_path = path.resolve(strict=False)
            
            # Resolve symlinks if configured
            if self.follow_symlinks and abs_path.is_symlink():
                abs_path = abs_path.resolve(strict=True)
            
            # Validate existence
            if not abs_path.exists():
                raise FileDiscoveryError(
                    f"Path does not exist: {path}",
                    details={"original_path": str(path), "resolved_path": str(abs_path)}
                )
            
            return abs_path
            
        except Exception as e:
            raise FileDiscoveryError(
                f"Failed to normalize path: {path}",
                details={"path": str(path), "error": str(e)}
            )
    
    def infer_mime_type(self, file_path: Path) -> str:
        """
        Infer MIME type from file extension.
        
        Uses Python's mimetypes module to determine content type based
        on file extension. Falls back to binary octet-stream for unknown.
        
        Args:
            file_path (Path): File path for type inference
            
        Returns:
            str: MIME type (e.g., "application/pdf", "text/plain")
            
        Example:
            >>> processor.infer_mime_type(Path("contract.pdf"))
            'application/pdf'
            >>> processor.infer_mime_type(Path("data.json"))
            'application/json'
        """
        mime_type, _ = mimetypes.guess_type(str(file_path))
        detected_type = mime_type or "application/octet-stream"
        
        logger.debug(
            f"Inferred MIME type for {file_path.name}: {detected_type}"
        )
        
        return detected_type
    
    def get_document_type(self, file_path: Path) -> DocumentType:
        """
        Determine document type from file extension.
        
        Maps file extension to DocumentType enum for routing and
        categorization purposes.
        
        Args:
            file_path (Path): File path for type detection
            
        Returns:
            DocumentType: Enum value representing document category
            
        Example:
            >>> processor.get_document_type(Path("report.pdf"))
            <DocumentType.PDF: 'pdf'>
            >>> processor.get_document_type(Path("data.xlsx"))
            <DocumentType.EXCEL: 'excel'>
        """
        extension = file_path.suffix.lower()
        doc_type = EXTENSION_TO_TYPE.get(extension, DocumentType.UNKNOWN)
        
        logger.debug(
            f"Document type for {file_path.name}: {doc_type.value}"
        )
        
        return doc_type
    
    def route_file(
        self,
        file_path: Path,
        base_prefix: str = "",
        use_type_folders: bool = True,
        preserve_structure: bool = False,
        source_root: Optional[Path] = None
    ) -> str:
        """
        Generate S3 key for file based on routing rules.
        
        Creates appropriate S3 object key by combining base prefix with
        optional type-based folders and preserved directory structure.
        
        Args:
            file_path (Path): File to route
            base_prefix (str): Base S3 prefix (default: "")
            use_type_folders (bool): Add document type subfolder (default: True)
            preserve_structure (bool): Preserve directory structure (default: False)
            source_root (Optional[Path]): Root path for structure preservation
                
        Returns:
            str: S3 object key for the file
            
        Raises:
            FileDiscoveryError: If preserve_structure=True but source_root missing
            
        Side Effects:
            - Logs routing decisions
            
        Example:
            >>> processor.route_file(
            ...     Path("/data/docs/contract.pdf"),
            ...     base_prefix="mba/",
            ...     use_type_folders=True
            ... )
            'mba/pdf/contract.pdf'
            
            >>> processor.route_file(
            ...     Path("/data/legal/2024/contract.pdf"),
            ...     base_prefix="mba/",
            ...     preserve_structure=True,
            ...     source_root=Path("/data")
            ... )
            'mba/legal/2024/contract.pdf'
        """
        # Normalize base prefix
        prefix = base_prefix.rstrip("/") + "/" if base_prefix else ""
        
        # Determine document type folder
        type_folder = ""
        if use_type_folders:
            doc_type = self.get_document_type(file_path)
            type_folder = f"{doc_type.value}/"
        
        # Preserve directory structure if requested
        structure = ""
        if preserve_structure:
            if not source_root:
                raise FileDiscoveryError(
                    "source_root required when preserve_structure=True",
                    details={"file_path": str(file_path)}
                )
            
            try:
                # Get relative path from source root
                rel_path = file_path.relative_to(source_root)
                if len(rel_path.parts) > 1:
                    # Include parent directories
                    structure = "/".join(rel_path.parts[:-1]) + "/"
            except ValueError:
                logger.warning(
                    f"File {file_path} is not relative to {source_root}, "
                    "structure preservation skipped"
                )
        
        # Construct final key
        s3_key = f"{prefix}{type_folder}{structure}{file_path.name}"
        
        logger.debug(f"Routed {file_path.name} to key: {s3_key}")
        
        return s3_key
    
    def validate_file(self, file_path: Path) -> bool:
        """
        Validate file meets all processing criteria.
        
        Checks file existence, type, size, and extension against
        configured rules.
        
        Args:
            file_path (Path): File path to validate
            
        Returns:
            bool: True if file is valid for processing
            
        Side Effects:
            - Logs validation failures at DEBUG level
            
        Example:
            >>> processor = FileProcessor(
            ...     allowed_extensions={".pdf"},
            ...     max_file_size_mb=10
            ... )
            >>> processor.validate_file(Path("report.pdf"))
            True
            >>> processor.validate_file(Path("huge_file.pdf"))  # 50MB
            False
        """
        # Check existence
        if not file_path.exists():
            logger.debug(f"Validation failed: file not found - {file_path}")
            return False
        
        # Check it's a file
        if not file_path.is_file():
            logger.debug(f"Validation failed: not a file - {file_path}")
            return False
        
        # Check extension
        if self.allowed_extensions:
            if file_path.suffix.lower() not in self.allowed_extensions:
                logger.debug(
                    f"Validation failed: extension not allowed - {file_path}"
                )
                return False
        
        # Check file size
        try:
            size_mb = file_path.stat().st_size / (1024 * 1024)
            if size_mb > self.max_file_size_mb:
                logger.debug(
                    f"Validation failed: file too large ({size_mb:.1f}MB) - {file_path}"
                )
                return False
        except OSError as e:
            logger.debug(f"Validation failed: cannot stat file - {file_path}: {e}")
            return False
        
        return True