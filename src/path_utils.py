"""
Path utilities for environment-agnostic path resolution.
This module provides functions to resolve paths in a way that works both locally and in Docker containers.
"""

import os
import sys
from pathlib import Path
from typing import Optional, Union


def get_environment() -> str:
    """Detect the current environment (local, docker, production)."""
    # Check for Docker environment
    if os.path.exists('/.dockerenv') or os.environ.get('DOCKER_ENV'):
        return 'docker'
    
    # Check for production environment
    if os.environ.get('FLASK_ENV') == 'production':
        return 'production'
    
    # Default to local development
    return 'local'


def get_project_root() -> str:
    """
    Get the project root directory in an environment-agnostic way.
    
    Returns:
        str: Path to the project root directory
    """
    # Try to get from environment variable first
    project_root = os.environ.get('PROJECT_ROOT')
    if project_root:
        return project_root
    
    # Fallback to relative path resolution
    current_file = Path(__file__)
    project_root = current_file.parent.parent
    return str(project_root)


def get_data_directory() -> str:
    """
    Get the data directory path in an environment-agnostic way.
    
    Returns:
        str: Path to the data directory
    """
    project_root = get_project_root()
    data_dir = os.path.join(project_root, 'data')
    
    # Ensure the directory exists
    os.makedirs(data_dir, exist_ok=True)
    
    return data_dir


def get_database_path() -> str:
    """
    Get the database file path in an environment-agnostic way.
    
    Returns:
        str: Path to the database file
    """
    data_dir = get_data_directory()
    db_path = os.path.join(data_dir, 'website_monitor.db')
    return db_path


def get_snapshots_directory() -> str:
    """
    Get the snapshots directory path in an environment-agnostic way.
    
    Returns:
        str: Path to the snapshots directory
    """
    data_dir = get_data_directory()
    snapshots_dir = os.path.join(data_dir, 'snapshots')
    
    # Ensure the directory exists
    os.makedirs(snapshots_dir, exist_ok=True)
    
    return snapshots_dir


def get_config_path_for_environment() -> str:
    """
    Get the appropriate config file path for the current environment.
    
    Returns:
        str: Path to the config file
    """
    project_root = get_project_root()
    environment = get_environment()
    
    if environment in ['docker', 'production']:
        config_path = os.path.join(project_root, 'config', 'config.production.yaml')
        if os.path.exists(config_path):
            return config_path
    
    # Default to main config
    return os.path.join(project_root, 'config', 'config.yaml')


def ensure_directory_exists(path: str) -> bool:
    """
    Ensure a directory exists, creating it if necessary.
    
    Args:
        path (str): Directory path to ensure exists
        
    Returns:
        bool: True if directory exists or was created successfully
    """
    try:
        os.makedirs(path, exist_ok=True)
        return True
    except OSError:
        return False


def resolve_path(relative_path: str, base_path: Optional[str] = None) -> str:
    """
    Resolve a relative path to an absolute path in an environment-agnostic way.
    
    Args:
        relative_path (str): Relative path to resolve
        base_path (str, optional): Base path to resolve from. Defaults to project root.
        
    Returns:
        str: Resolved absolute path
    """
    if base_path is None:
        base_path = get_project_root()
    
    # Handle absolute paths
    if os.path.isabs(relative_path):
        return relative_path
    
    # Resolve relative to base path
    resolved_path = os.path.join(base_path, relative_path)
    return os.path.normpath(resolved_path)


def get_relative_path_from_data(file_path: str) -> str:
    """
    Get a path relative to the data directory.
    
    Args:
        file_path (str): Full path to a file
        
    Returns:
        str: Path relative to the data directory
    """
    data_dir = get_data_directory()
    
    try:
        # Get relative path from data directory
        rel_path = os.path.relpath(file_path, data_dir)
        return rel_path
    except ValueError:
        # If the path is not relative to data directory, return as is
        return file_path


def get_web_accessible_path(file_path: str) -> str:
    """
    Convert a file path to a web-accessible path for the data_files endpoint.
    
    Args:
        file_path (str): Full path to a file
        
    Returns:
        str: Web-accessible path
    """
    # Get path relative to data directory
    rel_path = get_relative_path_from_data(file_path)
    
    # Ensure forward slashes for web compatibility
    web_path = rel_path.replace('\\', '/')
    
    return web_path


def is_docker_environment() -> bool:
    """
    Check if running in a Docker environment.
    
    Returns:
        bool: True if running in Docker
    """
    return get_environment() == 'docker'


def get_environment_specific_path(base_path: str, environment: Optional[str] = None) -> str:
    """
    Get an environment-specific path.
    
    Args:
        base_path (str): Base path
        environment (str, optional): Environment name. Defaults to detected environment.
        
    Returns:
        str: Environment-specific path
    """
    if environment is None:
        environment = get_environment()
    
    # For Docker/production, ensure paths are relative
    if environment in ['docker', 'production']:
        return base_path
    
    # For local development, can use absolute paths
    return base_path


def get_log_directory() -> str:
    """
    Get the log directory path in an environment-agnostic way.
    
    Returns:
        str: Path to the log directory
    """
    data_dir = get_data_directory()
    log_dir = os.path.join(data_dir, 'logs')
    
    # Ensure the directory exists
    os.makedirs(log_dir, exist_ok=True)
    
    return log_dir


def get_temp_directory() -> str:
    """
    Get the temporary directory path in an environment-agnostic way.
    
    Returns:
        str: Path to the temporary directory
    """
    data_dir = get_data_directory()
    temp_dir = os.path.join(data_dir, 'temp')
    
    # Ensure the directory exists
    os.makedirs(temp_dir, exist_ok=True)
    
    return temp_dir


def clean_path_for_logging(path: str) -> str:
    """
    Clean a path for logging to avoid exposing sensitive information.
    
    Args:
        path (str): Path to clean
        
    Returns:
        str: Cleaned path suitable for logging
    """
    # Remove project root from path for cleaner logs
    project_root = get_project_root()
    if path.startswith(project_root):
        rel_path = os.path.relpath(path, project_root)
        return rel_path
    
    return path


def validate_path_safety(path: str, allowed_base: Optional[str] = None) -> bool:
    """
    Validate that a path is safe to access (within allowed directory).
    
    Args:
        path (str): Path to validate
        allowed_base (str, optional): Base directory that's allowed. Defaults to project root.
        
    Returns:
        bool: True if path is safe to access
    """
    if allowed_base is None:
        allowed_base = get_project_root()
    
    try:
        # Resolve both paths to absolute
        abs_path = os.path.abspath(path)
        abs_base = os.path.abspath(allowed_base)
        
        # Check if path is within allowed base
        return abs_path.startswith(abs_base)
    except (OSError, ValueError):
        return False 