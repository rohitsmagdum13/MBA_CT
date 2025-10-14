"""
MySQL RDS client with connection pooling and DDL/DML operations.

This module provides the RDSClient class for managing MySQL database connections
and executing DDL (schema) and DML (data) operations with proper error handling,
connection pooling, and transaction management.

Module Input:
    - Database credentials from settings
    - SQL queries and parameters
    - Schema definitions and data batches

Module Output:
    - Query results and row counts
    - Schema creation/modification confirmations
    - Transaction commit/rollback status
"""

import pymysql
from pymysql.cursors import DictCursor
from contextlib import contextmanager
from typing import List, Dict, Any, Optional, Tuple
from threading import Lock
import time

from MBA.core.exceptions import DatabaseError, ConfigError
from MBA.core.logging_config import get_logger
from MBA.core.settings import settings

logger = get_logger(__name__)


class RDSClient:
    """
    MySQL RDS client with connection pooling and transaction support.
    
    Provides a robust interface for interacting with AWS RDS MySQL instances,
    including connection pooling, automatic retry logic, DDL operations for
    schema management, and efficient DML operations for data loading.
    
    The client uses PyMySQL for database connectivity and implements
    connection pooling with configurable pool size and overflow limits.
    
    Attributes:
        host (str): RDS endpoint hostname
        port (int): MySQL port
        database (str): Database name
        user (str): Database user
        _pool (List): Connection pool
        _pool_lock (Lock): Thread-safe pool access
        _pool_size (int): Maximum pool size
        
    Thread Safety:
        Thread-safe for all operations via connection pooling and locking.
    """
    
    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        database: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        pool_size: Optional[int] = None
    ):
        """
        Initialize RDS client with connection parameters.
        
        Creates connection pool and validates database connectivity.
        Defaults to settings values if parameters not provided.
        
        Args:
            host (Optional[str]): RDS endpoint (default: from settings)
            port (Optional[int]): MySQL port (default: from settings)
            database (Optional[str]): Database name (default: from settings)
            user (Optional[str]): Database user (default: from settings)
            password (Optional[str]): Database password (default: from settings)
            pool_size (Optional[int]): Connection pool size (default: from settings)
            
        Raises:
            ConfigError: If required connection parameters are missing
            DatabaseError: If initial connection test fails
            
        Side Effects:
            - Creates connection pool
            - Tests database connectivity
            - Logs initialization status
        """
        # Load configuration from settings or parameters
        self.host = host or settings.rds_host
        self.port = port or settings.rds_port
        self.database = database or settings.rds_database
        self.user = user or settings.rds_username
        self._password = password or settings.rds_password
        self._pool_size = pool_size or settings.rds_pool_size
        
        # Validate required parameters
        if not all([self.host, self.database, self.user, self._password]):
            raise ConfigError(
                "Missing required database connection parameters",
                details={
                    "host": bool(self.host),
                    "database": bool(self.database),
                    "user": bool(self.user),
                    "password": bool(self._password)
                }
            )
        
        # Initialize connection pool
        self._pool: List[pymysql.connections.Connection] = []
        self._pool_lock = Lock()
        
        # Test connection
        try:
            conn = self._create_connection()
            conn.close()
            logger.info(
                f"RDS client initialized: {self.user}@{self.host}:{self.port}/{self.database}"
            )
        except Exception as e:
            raise DatabaseError(
                f"Failed to connect to RDS: {str(e)}",
                details={
                    "host": self.host,
                    "port": self.port,
                    "database": self.database
                }
            )
    
    def _create_connection(self) -> pymysql.connections.Connection:
        """
        Create new MySQL connection.
        
        Returns:
            pymysql.connections.Connection: New database connection
            
        Raises:
            DatabaseError: If connection creation fails
        """
        try:
            connection = pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self._password,
                database=self.database,
                charset='utf8mb4',
                cursorclass=DictCursor,
                autocommit=False,
                connect_timeout=10,
                read_timeout=30,  # Add read timeout
                write_timeout=30  # Add write timeout
            )
            return connection
        except Exception as e:
            raise DatabaseError(
                f"Failed to create database connection: {str(e)}",
                details={"host": self.host, "database": self.database}
            )
    
    @contextmanager
    def get_connection(self):
        """
        Get connection from pool with automatic return.
        
        Context manager that acquires a connection from the pool
        and ensures it's returned after use.
        
        Yields:
            pymysql.connections.Connection: Database connection
            
        Side Effects:
            - Acquires connection from pool
            - Returns connection to pool on exit
            - Closes connection on error
            
        Example:
            >>> with client.get_connection() as conn:
            ...     cursor = conn.cursor()
            ...     cursor.execute("SELECT * FROM users")
        """
        conn = None
        try:
            # Try to get connection from pool
            with self._pool_lock:
                if self._pool:
                    conn = self._pool.pop()
            
            # Create new connection if pool empty
            if conn is None:
                conn = self._create_connection()
            
            # Verify connection is alive
            if not conn.open:
                conn = self._create_connection()
            
            yield conn
            
            # Return healthy connection to pool
            with self._pool_lock:
                if len(self._pool) < self._pool_size and conn.open:
                    self._pool.append(conn)
                else:
                    conn.close()
        
        except Exception as e:
            if conn and conn.open:
                conn.close()
            raise
    
    def execute_query(
        self,
        query: str,
        params: Optional[Tuple] = None,
        fetch: bool = True
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Execute SELECT query and return results.
        
        Args:
            query (str): SQL SELECT query
            params (Optional[Tuple]): Query parameters for safe substitution
            fetch (bool): Whether to fetch results (default: True)
            
        Returns:
            Optional[List[Dict[str, Any]]]: Query results as list of dicts,
                or None if fetch=False
                
        Raises:
            DatabaseError: If query execution fails
            
        Example:
            >>> results = client.execute_query(
            ...     "SELECT * FROM users WHERE id = %s",
            ...     params=(123,)
            ... )
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, params or ())
                    
                    if fetch:
                        results = cursor.fetchall()
                        logger.debug(
                            f"Query returned {len(results)} rows: {query[:100]}..."
                        )
                        return results
                    
                    return None
                    
        except Exception as e:
            raise DatabaseError(
                f"Query execution failed: {str(e)}",
                details={"query": query[:200], "params": str(params)}
            )
    
    def execute_update(
        self,
        query: str,
        params: Optional[Tuple] = None,
        commit: bool = True
    ) -> int:
        """
        Execute INSERT/UPDATE/DELETE query.
        
        Args:
            query (str): SQL modification query
            params (Optional[Tuple]): Query parameters
            commit (bool): Auto-commit transaction (default: True)
            
        Returns:
            int: Number of affected rows
            
        Raises:
            DatabaseError: If query execution fails
            
        Example:
            >>> rows = client.execute_update(
            ...     "UPDATE users SET status = %s WHERE id = %s",
            ...     params=("active", 123)
            ... )
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, params or ())
                    affected_rows = cursor.rowcount
                    
                    if commit:
                        conn.commit()
                    
                    logger.debug(
                        f"Updated {affected_rows} rows: {query[:100]}..."
                    )
                    
                    return affected_rows
                    
        except Exception as e:
            raise DatabaseError(
                f"Update execution failed: {str(e)}",
                details={"query": query[:200], "params": str(params)}
            )
    
    def execute_many(
        self,
        query: str,
        data: List[Tuple],
        commit: bool = True
    ) -> int:
        """
        Execute query with multiple parameter sets (batch insert/update).
        
        Args:
            query (str): SQL query with parameter placeholders
            data (List[Tuple]): List of parameter tuples
            commit (bool): Auto-commit transaction (default: True)
            
        Returns:
            int: Total number of affected rows
            
        Raises:
            DatabaseError: If batch execution fails
            
        Example:
            >>> data = [(1, 'Alice'), (2, 'Bob'), (3, 'Carol')]
            >>> client.execute_many(
            ...     "INSERT INTO users (id, name) VALUES (%s, %s)",
            ...     data
            ... )
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.executemany(query, data)
                    affected_rows = cursor.rowcount
                    
                    if commit:
                        conn.commit()
                    
                    logger.info(
                        f"Batch executed {len(data)} statements, "
                        f"affected {affected_rows} rows"
                    )
                    
                    return affected_rows
                    
        except Exception as e:
            raise DatabaseError(
                f"Batch execution failed: {str(e)}",
                details={
                    "query": query[:200],
                    "batch_size": len(data)
                }
            )
    
    def table_exists(self, table_name: str) -> bool:
        """
        Check if table exists in database.
        
        Args:
            table_name (str): Name of table to check
            
        Returns:
            bool: True if table exists
            
        Example:
            >>> if not client.table_exists("users"):
            ...     client.create_table("users", schema)
        """
        query = """
            SELECT COUNT(*) as count
            FROM information_schema.tables
            WHERE table_schema = %s
            AND table_name = %s
        """
        
        try:
            result = self.execute_query(query, params=(self.database, table_name))
            exists = result[0]['count'] > 0
            
            logger.debug(f"Table '{table_name}' exists: {exists}")
            return exists
            
        except Exception as e:
            raise DatabaseError(
                f"Failed to check table existence: {str(e)}",
                details={"table": table_name}
            )
    
    def get_table_columns(self, table_name: str) -> List[Dict[str, Any]]:
        """
        Get column definitions for existing table.
        
        Args:
            table_name (str): Name of table
            
        Returns:
            List[Dict[str, Any]]: Column information with keys:
                - column_name (str)
                - data_type (str)
                - is_nullable (str)
                - column_key (str)
                
        Raises:
            DatabaseError: If query fails
            
        Example:
            >>> columns = client.get_table_columns("users")
            >>> for col in columns:
            ...     print(f"{col['column_name']}: {col['data_type']}")
        """
        query = """
            SELECT 
                column_name,
                data_type,
                is_nullable,
                column_key,
                column_type
            FROM information_schema.columns
            WHERE table_schema = %s
            AND table_name = %s
            ORDER BY ordinal_position
        """
        
        try:
            columns = self.execute_query(query, params=(self.database, table_name))
            logger.debug(f"Retrieved {len(columns)} columns from '{table_name}'")
            return columns
            
        except Exception as e:
            raise DatabaseError(
                f"Failed to get table columns: {str(e)}",
                details={"table": table_name}
            )
    
    def create_table(
        self,
        table_name: str,
        columns: List[Dict[str, str]],
        primary_key: Optional[str] = None
    ):
        """
        Create new table with specified schema.
        
        Args:
            table_name (str): Name for new table
            columns (List[Dict[str, str]]): Column definitions with keys:
                - name (str): Column name
                - type (str): MySQL data type
                - nullable (bool): Allow NULL values (default: True)
            primary_key (Optional[str]): Name of primary key column
            
        Raises:
            DatabaseError: If table creation fails
            
        Side Effects:
            - Creates table in database
            - Logs creation status
            
        Example:
            >>> columns = [
            ...     {"name": "id", "type": "INT", "nullable": False},
            ...     {"name": "name", "type": "VARCHAR(255)", "nullable": False},
            ...     {"name": "email", "type": "VARCHAR(255)", "nullable": True}
            ... ]
            >>> client.create_table("users", columns, primary_key="id")
        """
        try:
            # Build column definitions
            col_defs = []
            for col in columns:
                col_def = f"`{col['name']}` {col['type']}"
                if not col.get('nullable', True):
                    col_def += " NOT NULL"
                col_defs.append(col_def)
            
            # Add primary key if specified
            if primary_key:
                col_defs.append(f"PRIMARY KEY (`{primary_key}`)")
            
            # Create table statement
            query = f"""
                CREATE TABLE `{table_name}` (
                    {', '.join(col_defs)}
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
            
            self.execute_update(query, commit=True)
            
            logger.info(
                f"Created table '{table_name}' with {len(columns)} columns"
            )
            
        except Exception as e:
            raise DatabaseError(
                f"Failed to create table '{table_name}': {str(e)}",
                details={"table": table_name, "columns": columns}
            )
    
    def add_columns(
        self,
        table_name: str,
        columns: List[Dict[str, str]]
    ):
        """
        Add new columns to existing table.
        
        Args:
            table_name (str): Name of existing table
            columns (List[Dict[str, str]]): Column definitions (same format as create_table)
            
        Raises:
            DatabaseError: If column addition fails
            
        Side Effects:
            - Alters table schema
            - Logs modification
            
        Example:
            >>> new_cols = [
            ...     {"name": "created_at", "type": "TIMESTAMP", "nullable": True}
            ... ]
            >>> client.add_columns("users", new_cols)
        """
        try:
            for col in columns:
                col_def = f"`{col['name']}` {col['type']}"
                if not col.get('nullable', True):
                    col_def += " NOT NULL"
                
                query = f"ALTER TABLE `{table_name}` ADD COLUMN {col_def}"
                self.execute_update(query, commit=True)
            
            logger.info(
                f"Added {len(columns)} columns to table '{table_name}'"
            )
            
        except Exception as e:
            raise DatabaseError(
                f"Failed to add columns to '{table_name}': {str(e)}",
                details={"table": table_name, "columns": columns}
            )
    
    def truncate_table(self, table_name: str):
        """
        Truncate table (delete all rows, reset auto-increment).
        
        Args:
            table_name (str): Name of table to truncate
            
        Raises:
            DatabaseError: If truncate fails
            
        Side Effects:
            - Removes all table data
            - Resets auto-increment counter
            - Logs operation
        """
        try:
            query = f"TRUNCATE TABLE `{table_name}`"
            self.execute_update(query, commit=True)
            
            logger.info(f"Truncated table '{table_name}'")
            
        except Exception as e:
            raise DatabaseError(
                f"Failed to truncate table '{table_name}': {str(e)}",
                details={"table": table_name}
            )
    
    def close_all_connections(self):
        """
        Close all connections in pool.
        
        Should be called on application shutdown to cleanly
        release database connections.
        
        Side Effects:
            - Closes all pooled connections
            - Clears connection pool
            - Logs shutdown
        """
        with self._pool_lock:
            for conn in self._pool:
                try:
                    if conn.open:
                        conn.close()
                except Exception as e:
                    logger.warning(f"Error closing connection: {e}")
            
            self._pool.clear()
            logger.info("Closed all database connections")