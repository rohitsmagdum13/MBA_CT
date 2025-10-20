"""
Content-based duplicate detection using cryptographic hashing.

This module provides the DuplicateDetector class for computing file content
hashes and detecting duplicate files using an in-memory cache. Supports
multiple hash algorithms and efficient duplicate tracking.

Module Input:
    - File paths for hash computation
    - Previously computed hashes for comparison
    - Cache persistence/loading operations

Module Output:
    - SHA-256 content hashes
    - Duplicate detection results
    - Cache statistics and contents
"""

import hashlib
from pathlib import Path
from typing import Dict, Set, Optional, List, Tuple
from collections import defaultdict
from threading import Lock

from MBA.core.exceptions import FileDiscoveryError, ValidationError
from MBA.core.logging_config import get_logger

logger = get_logger(__name__)


class DuplicateDetector:
    """
    Content-based duplicate file detector using cryptographic hashing.
    
    Computes SHA-256 hashes of file contents and maintains an in-memory
    cache to detect duplicate files across ingestion operations. Provides
    thread-safe operations for concurrent duplicate detection.
    
    The cache maps content hashes to lists of file paths that share that
    hash, enabling identification of all duplicates of a given file.
    
    Attributes:
        algorithm (str): Hash algorithm name (default: "sha256")
        chunk_size (int): File read chunk size in bytes
        _cache (Dict[str, List[str]]): Hash to file paths mapping
        _lock (Lock): Thread synchronization lock
        
    Thread Safety:
        Thread-safe for all operations via internal locking.
    """
    
    def __init__(
        self,
        algorithm: str = "sha256",
        chunk_size: int = 8192
    ):
        """
        Initialize duplicate detector with hash configuration.
        
        Args:
            algorithm (str): Hash algorithm (default: "sha256")
                Supported: "md5", "sha1", "sha256", "sha512"
            chunk_size (int): Bytes to read per chunk (default: 8192)
                
        Raises:
            ValidationError: If algorithm is not supported
            
        Side Effects:
            - Validates hash algorithm availability
            - Initializes empty cache
            - Logs detector initialization
        """
        # Validate algorithm
        if algorithm not in hashlib.algorithms_available:
            raise ValidationError(
                f"Hash algorithm '{algorithm}' not available. "
                f"Supported: {sorted(hashlib.algorithms_available)}",
                details={
                    "requested_algorithm": algorithm,
                    "available_algorithms": sorted(hashlib.algorithms_available)
                }
            )
        
        self.algorithm = algorithm
        self.chunk_size = chunk_size
        
        # Hash -> List of file paths with that hash
        self._cache: Dict[str, List[str]] = defaultdict(list)
        self._lock = Lock()
        
        logger.info(
            f"Initialized DuplicateDetector: "
            f"algorithm={algorithm}, chunk_size={chunk_size}"
        )
    
    def compute_hash(self, file_path: Path) -> str:
        """
        Compute cryptographic hash of file contents.
        
        Reads file in chunks to handle large files efficiently, computing
        hash incrementally to minimize memory usage.
        
        Args:
            file_path (Path): Path to file for hashing
            
        Returns:
            str: Hexadecimal hash digest
            
        Raises:
            FileDiscoveryError: If file cannot be read or doesn't exist
            
        Side Effects:
            - Reads file from disk
            - Logs hash computation
            
        Example:
            >>> detector = DuplicateDetector()
            >>> hash_val = detector.compute_hash(Path("document.pdf"))
            >>> print(hash_val)
            '2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae'
        """
        if not file_path.exists():
            raise FileDiscoveryError(
                f"Cannot hash non-existent file: {file_path}",
                details={"file_path": str(file_path)}
            )
        
        if not file_path.is_file():
            raise FileDiscoveryError(
                f"Cannot hash non-file path: {file_path}",
                details={"file_path": str(file_path)}
            )
        
        try:
            hasher = hashlib.new(self.algorithm)
            
            with open(file_path, "rb") as f:
                # Read file in chunks to handle large files
                while chunk := f.read(self.chunk_size):
                    hasher.update(chunk)
            
            hash_value = hasher.hexdigest()
            
            logger.debug(
                f"Computed {self.algorithm} hash for {file_path.name}: "
                f"{hash_value[:16]}..."
            )
            
            return hash_value
            
        except OSError as e:
            raise FileDiscoveryError(
                f"Failed to read file for hashing: {file_path}",
                details={"file_path": str(file_path), "error": str(e)}
            )
        except Exception as e:
            raise FileDiscoveryError(
                f"Hash computation failed: {str(e)}",
                details={"file_path": str(file_path), "error": str(e)}
            )
    
    def is_duplicate(
        self,
        file_path: Path,
        compute_if_missing: bool = True
    ) -> Tuple[bool, Optional[str], Optional[List[str]]]:
        """
        Check if file is a duplicate of previously seen file.
        
        Computes hash for file and checks cache for existing entries.
        Optionally adds file to cache if not found.
        
        Args:
            file_path (Path): File to check for duplication
            compute_if_missing (bool): Add to cache if not duplicate
                (default: True)
                
        Returns:
            Tuple[bool, Optional[str], Optional[List[str]]]:
                - bool: True if file is a duplicate
                - str: Content hash of the file
                - List[str]: Paths of duplicate files (if any)
                
        Side Effects:
            - Computes file hash
            - May add file to cache
            - Logs duplicate detection results
            
        Example:
            >>> detector = DuplicateDetector()
            >>> 
            >>> # First file - not a duplicate
            >>> is_dup, hash_val, dups = detector.is_duplicate(Path("doc1.pdf"))
            >>> print(is_dup)
            False
            >>> 
            >>> # Identical file - is a duplicate
            >>> is_dup, hash_val, dups = detector.is_duplicate(Path("doc1_copy.pdf"))
            >>> print(is_dup, dups)
            True ['doc1.pdf']
        """
        # Compute hash for file
        file_hash = self.compute_hash(file_path)
        file_path_str = str(file_path)
        
        with self._lock:
            # Check if hash exists in cache
            if file_hash in self._cache:
                existing_paths = self._cache[file_hash]
                
                # Check if this exact path already in cache
                if file_path_str in existing_paths:
                    logger.debug(
                        f"File already in cache: {file_path.name} "
                        f"(hash: {file_hash[:16]}...)"
                    )
                    # It's the same entry, not a new duplicate
                    return False, file_hash, None
                
                # Found duplicate(s)
                logger.info(
                    f"Duplicate detected: {file_path.name} matches "
                    f"{len(existing_paths)} existing file(s) "
                    f"(hash: {file_hash[:16]}...)"
                )
                
                # Optionally add this duplicate to cache
                if compute_if_missing:
                    self._cache[file_hash].append(file_path_str)
                
                return True, file_hash, existing_paths.copy()
            
            # Not a duplicate - add to cache if requested
            if compute_if_missing:
                self._cache[file_hash].append(file_path_str)
                logger.debug(
                    f"Added to cache: {file_path.name} "
                    f"(hash: {file_hash[:16]}...)"
                )
            
            return False, file_hash, None
    
    def add_to_cache(self, file_path: Path, file_hash: Optional[str] = None) -> str:
        """
        Explicitly add file to duplicate detection cache.
        
        Adds file to cache with either provided hash or newly computed hash.
        Useful for pre-populating cache from external sources.
        
        Args:
            file_path (Path): File to add to cache
            file_hash (Optional[str]): Pre-computed hash (default: None)
                If None, hash will be computed
                
        Returns:
            str: Content hash used for caching
            
        Side Effects:
            - May compute file hash
            - Adds entry to cache
            - Logs cache addition
            
        Example:
            >>> detector = DuplicateDetector()
            >>> # Add with computed hash
            >>> hash1 = detector.add_to_cache(Path("file1.pdf"))
            >>> 
            >>> # Add with known hash
            >>> hash2 = detector.add_to_cache(
            ...     Path("file2.pdf"),
            ...     file_hash="abc123..."
            ... )
        """
        # Compute hash if not provided
        if file_hash is None:
            file_hash = self.compute_hash(file_path)
        
        file_path_str = str(file_path)
        
        with self._lock:
            # Only add if not already present
            if file_path_str not in self._cache[file_hash]:
                self._cache[file_hash].append(file_path_str)
                logger.debug(
                    f"Added to cache: {file_path.name} "
                    f"(hash: {file_hash[:16]}...)"
                )
        
        return file_hash
    
    def get_duplicates(self, file_path: Path) -> Optional[List[str]]:
        """
        Get list of files that duplicate the given file.
        
        Computes hash for file and returns all cached paths with same hash,
        excluding the query file itself.
        
        Args:
            file_path (Path): File to find duplicates of
            
        Returns:
            Optional[List[str]]: List of duplicate file paths, or None if
                no duplicates found
                
        Example:
            >>> detector.add_to_cache(Path("doc1.pdf"))
            >>> detector.add_to_cache(Path("doc1_copy.pdf"))
            >>> 
            >>> duplicates = detector.get_duplicates(Path("doc1.pdf"))
            >>> print(duplicates)
            ['doc1_copy.pdf']
        """
        file_hash = self.compute_hash(file_path)
        file_path_str = str(file_path)
        
        with self._lock:
            if file_hash in self._cache:
                # Return all paths except the query file
                duplicates = [
                    path for path in self._cache[file_hash]
                    if path != file_path_str
                ]
                return duplicates if duplicates else None
            
            return None
    
    def get_all_duplicates(self) -> Dict[str, List[str]]:
        """
        Get all duplicate file groups in cache.
        
        Returns dictionary mapping content hashes to lists of files that
        share that hash. Only includes hashes with multiple files.
        
        Returns:
            Dict[str, List[str]]: Hash -> list of duplicate file paths
            
        Example:
            >>> duplicates = detector.get_all_duplicates()
            >>> for hash_val, files in duplicates.items():
            ...     print(f"Hash {hash_val[:16]}: {len(files)} duplicates")
            ...     for file in files:
            ...         print(f"  - {file}")
        """
        with self._lock:
            return {
                hash_val: paths.copy()
                for hash_val, paths in self._cache.items()
                if len(paths) > 1
            }
    
    def clear_cache(self):
        """
        Clear all entries from duplicate detection cache.
        
        Removes all cached file hashes and paths, resetting detector
        to initial state.
        
        Side Effects:
            - Empties cache dictionary
            - Logs cache clearing
        """
        with self._lock:
            cache_size = len(self._cache)
            total_files = sum(len(paths) for paths in self._cache.values())
            
            self._cache.clear()
            
            logger.info(
                f"Cleared cache: removed {cache_size} unique hashes "
                f"({total_files} file entries)"
            )
    
    def get_cache_stats(self) -> Dict[str, int]:
        """
        Get statistics about current cache state.
        
        Returns:
            Dict[str, int]: Statistics dictionary with keys:
                - unique_hashes: Number of unique content hashes
                - total_files: Total number of cached files
                - duplicate_groups: Number of hash groups with duplicates
                - duplicate_files: Total files involved in duplication
                
        Example:
            >>> stats = detector.get_cache_stats()
            >>> print(f"Tracking {stats['total_files']} files")
            >>> print(f"Found {stats['duplicate_groups']} duplicate groups")
        """
        with self._lock:
            unique_hashes = len(self._cache)
            total_files = sum(len(paths) for paths in self._cache.values())
            
            # Count groups with duplicates
            duplicate_groups = sum(
                1 for paths in self._cache.values() if len(paths) > 1
            )
            
            # Count files involved in duplication
            duplicate_files = sum(
                len(paths) for paths in self._cache.values() if len(paths) > 1
            )
            
            return {
                "unique_hashes": unique_hashes,
                "total_files": total_files,
                "duplicate_groups": duplicate_groups,
                "duplicate_files": duplicate_files
            }
    
    def export_cache(self) -> Dict[str, List[str]]:
        """
        Export cache contents for persistence or analysis.
        
        Returns full cache mapping for serialization to JSON, database,
        or other storage formats.
        
        Returns:
            Dict[str, List[str]]: Complete hash -> paths mapping
            
        Side Effects:
            - Logs export operation
            
        Example:
            >>> import json
            >>> cache_data = detector.export_cache()
            >>> with open("cache.json", "w") as f:
            ...     json.dump(cache_data, f)
        """
        with self._lock:
            cache_copy = {
                hash_val: paths.copy()
                for hash_val, paths in self._cache.items()
            }
            
            logger.info(
                f"Exported cache: {len(cache_copy)} hashes, "
                f"{sum(len(paths) for paths in cache_copy.values())} files"
            )
            
            return cache_copy
    
    def import_cache(self, cache_data: Dict[str, List[str]], merge: bool = False):
        """
        Import cache contents from external source.
        
        Loads cache data from dictionary, either replacing or merging with
        existing cache contents.
        
        Args:
            cache_data (Dict[str, List[str]]): Hash -> paths mapping to import
            merge (bool): Merge with existing cache (default: False)
                If False, replaces entire cache
                
        Side Effects:
            - Modifies cache contents
            - Logs import operation
            
        Example:
            >>> import json
            >>> with open("cache.json") as f:
            ...     cache_data = json.load(f)
            >>> detector.import_cache(cache_data, merge=True)
        """
        with self._lock:
            if not merge:
                self._cache.clear()
            
            for hash_val, paths in cache_data.items():
                if merge and hash_val in self._cache:
                    # Merge paths, avoiding duplicates
                    existing = set(self._cache[hash_val])
                    for path in paths:
                        if path not in existing:
                            self._cache[hash_val].append(path)
                else:
                    self._cache[hash_val] = list(paths)
            
            total_hashes = len(self._cache)
            total_files = sum(len(paths) for paths in self._cache.values())
            
            logger.info(
                f"Imported cache ({'merged' if merge else 'replaced'}): "
                f"{total_hashes} hashes, {total_files} files"
            )