"""
Environment Configuration Module
Handles environment variable overrides for configuration settings.
"""

import os
import logging
from typing import Any, Dict, Optional
# Import will be done locally to avoid circular imports

logger = logging.getLogger(__name__)

# Environment variable prefix
ENV_PREFIX = "WEBSITE_MONITOR_"

# Configuration mapping from environment variables to config keys
ENV_CONFIG_MAPPING = {
    # Logging
    "LOG_LEVEL": "log_level",
    "LOG_FILE_PATH": "log_file_path",
    "LOG_FILE_DASHBOARD": "log_file_dashboard",
    
    # Database and Storage
    "DATABASE_PATH": "database_path",
    "WEBSITES_FILE_PATH": "website_list_file_path",
    "SNAPSHOT_DIRECTORY": "snapshot_directory",
    "CHECK_HISTORY_FILE_PATH": "check_history_file_path",
    
    # Monitoring Settings
    "DEFAULT_MONITORING_INTERVAL_HOURS": "default_monitoring_interval_hours",
    "MONITORING_INTERVAL_SECONDS": "monitoring_interval_seconds",
    "ENABLE_SCHEDULER": "enable_scheduler",
    
    # Playwright Configuration
    "PLAYWRIGHT_BROWSER_TYPE": "playwright_browser_type",
    "PLAYWRIGHT_HEADLESS_MODE": "playwright_headless_mode",
    "PLAYWRIGHT_USER_AGENT": "playwright_user_agent",
    "PLAYWRIGHT_RENDER_DELAY_MS": "playwright_render_delay_ms",
    "PLAYWRIGHT_NAVIGATION_TIMEOUT_MS": "playwright_navigation_timeout_ms",
    "PLAYWRIGHT_RETRIES": "playwright_retries",
    
    # Network Settings
    "FETCH_RETRY_TOTAL": "fetch_retry_total",
    "FETCH_RETRY_BACKOFF_FACTOR": "fetch_retry_backoff_factor",
    "FETCH_RETRY_STATUS_FORCELIST": "fetch_retry_status_forcelist",
    
    # Greenflare Settings
    "GREENFLARE_TIMEOUT": "greenflare_timeout",
    "GREENFLARE_RETRIES": "greenflare_retries",
    "GREENFLARE_BACKOFF_BASE": "greenflare_backoff_base",
    "GREENFLARE_EXTRACT_IMAGES": "greenflare_extract_images",
    "GREENFLARE_EXTRACT_ALT_TEXT": "greenflare_extract_alt_text",
    
    # Crawler Settings
    "CRAWLER_MAX_DEPTH": "crawler_max_depth",
    "CRAWLER_RESPECT_ROBOTS": "crawler_respect_robots",
    "CRAWLER_CHECK_EXTERNAL_LINKS": "crawler_check_external_links",
    "CRAWLER_USER_AGENT": "crawler_user_agent",
    
    # Change Detection Thresholds
    "CONTENT_CHANGE_THRESHOLD": "content_change_threshold",
    "IMAGE_DIFF_THRESHOLD": "image_diff_threshold",
    "STRUCTURE_CHANGE_THRESHOLD": "structure_change_threshold",
    "SEMANTIC_SIMILARITY_THRESHOLD": "semantic_similarity_threshold",
    "SSIM_SIMILARITY_THRESHOLD": "ssim_similarity_threshold",
    "VISUAL_CHANGE_ALERT_THRESHOLD_PERCENT": "visual_change_alert_threshold_percent",
    "VISUAL_DIFFERENCE_THRESHOLD": "visual_difference_threshold",
    
    # Blur Detection Settings
    "BLUR_DETECTION_THRESHOLD": "blur_detection_threshold",
    "BLUR_DETECTION_PERCENTAGE_THRESHOLD": "blur_detection_percentage_threshold",
    "BLUR_DETECTION_MIN_IMAGE_SIZE": "blur_detection_min_image_size",
    "BLUR_DETECTION_TIMEOUT": "blur_detection_timeout",
    "BLUR_DETECTION_CLEANUP_DAYS": "blur_detection_cleanup_days",
    
    # Dashboard Settings
    "DASHBOARD_PORT": "dashboard_port",
    "DASHBOARD_HISTORY_LIMIT": "dashboard_history_limit",
    "DASHBOARD_API_HISTORY_LIMIT": "dashboard_api_history_limit",
    
    # Email Settings
    "NOTIFICATION_EMAIL_FROM": "notification_email_from",
    "NOTIFICATION_EMAIL_TO": "notification_email_to",
    "DEFAULT_NOTIFICATION_EMAIL": "default_notification_email",
    "SMTP_SERVER": "smtp_server",
    "SMTP_PORT": "smtp_port",
    "SMTP_USERNAME": "smtp_username",
    "SMTP_PASSWORD": "smtp_password",
    "SMTP_USE_TLS": "smtp_use_tls",
    
    # Scheduler Settings
    "SCHEDULER_ENABLED": "scheduler_enabled",
    "SCHEDULER_STARTUP_DELAY_SECONDS": "scheduler_startup_delay_seconds",
    "SCHEDULER_CHECK_INTERVAL_SECONDS": "scheduler_check_interval_seconds",
    
    # Google PageSpeed API
    "GOOGLE_PAGESPEED_API_KEY": "google_pagespeed_api_key",
    
    # Snapshot Settings
    "SNAPSHOT_FORMAT": "snapshot_format",
}

def get_environment_overrides() -> Dict[str, Any]:
    """
    Get configuration overrides from environment variables.
    
    Returns:
        Dict containing configuration overrides from environment variables.
    """
    overrides = {}
    
    for env_key, config_key in ENV_CONFIG_MAPPING.items():
        env_var_name = f"{ENV_PREFIX}{env_key}"
        env_value = os.getenv(env_var_name)
        
        if env_value is not None:
            # Convert value to appropriate type
            converted_value = convert_env_value(env_value, env_key)
            overrides[config_key] = converted_value
            logger.debug(f"Environment override: {config_key} = {converted_value} (from {env_var_name})")
    
    return overrides

def convert_env_value(value: str, env_key: str) -> Any:
    """
    Convert environment variable string value to appropriate type.
    
    Args:
        value: The environment variable string value
        env_key: The environment variable key for type determination
        
    Returns:
        Converted value with appropriate type
    """
    # Boolean conversions
    if env_key in [
        "PLAYWRIGHT_HEADLESS_MODE", "ENABLE_SCHEDULER", "CRAWLER_RESPECT_ROBOTS",
        "CRAWLER_CHECK_EXTERNAL_LINKS", "GREENFLARE_EXTRACT_IMAGES",
        "GREENFLARE_EXTRACT_ALT_TEXT", "SMTP_USE_TLS", "SCHEDULER_ENABLED"
    ]:
        return value.lower() in ('true', '1', 'yes', 'on')
    
    # Integer conversions
    elif env_key in [
        "DEFAULT_MONITORING_INTERVAL_HOURS", "MONITORING_INTERVAL_SECONDS",
        "PLAYWRIGHT_RENDER_DELAY_MS", "PLAYWRIGHT_NAVIGATION_TIMEOUT_MS",
        "PLAYWRIGHT_RETRIES", "FETCH_RETRY_TOTAL", "GREENFLARE_TIMEOUT",
        "GREENFLARE_RETRIES", "CRAWLER_MAX_DEPTH", "DASHBOARD_PORT",
        "DASHBOARD_HISTORY_LIMIT", "DASHBOARD_API_HISTORY_LIMIT",
        "SMTP_PORT", "SCHEDULER_STARTUP_DELAY_SECONDS",
        "SCHEDULER_CHECK_INTERVAL_SECONDS", "BLUR_DETECTION_THRESHOLD",
        "BLUR_DETECTION_PERCENTAGE_THRESHOLD", "BLUR_DETECTION_MIN_IMAGE_SIZE",
        "BLUR_DETECTION_TIMEOUT", "BLUR_DETECTION_CLEANUP_DAYS"
    ]:
        try:
            return int(value)
        except ValueError:
            logger.warning(f"Invalid integer value for {env_key}: {value}")
            return 0
    
    # Float conversions
    elif env_key in [
        "FETCH_RETRY_BACKOFF_FACTOR", "GREENFLARE_BACKOFF_BASE",
        "CONTENT_CHANGE_THRESHOLD", "IMAGE_DIFF_THRESHOLD",
        "STRUCTURE_CHANGE_THRESHOLD", "SEMANTIC_SIMILARITY_THRESHOLD",
        "SSIM_SIMILARITY_THRESHOLD", "VISUAL_CHANGE_ALERT_THRESHOLD_PERCENT",
        "VISUAL_DIFFERENCE_THRESHOLD"
    ]:
        try:
            return float(value)
        except ValueError:
            logger.warning(f"Invalid float value for {env_key}: {value}")
            return 0.0
    
    # List conversions (comma-separated)
    elif env_key in ["FETCH_RETRY_STATUS_FORCELIST", "GREENFLARE_EXTRACT_META_TAGS"]:
        return [item.strip() for item in value.split(',') if item.strip()]
    
    # Default to string
    else:
        return value

def merge_config_with_env(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge configuration with environment variable overrides.
    
    Args:
        config: The base configuration dictionary
        
    Returns:
        Merged configuration with environment overrides
    """
    env_overrides = get_environment_overrides()
    
    # Create a copy of the config to avoid modifying the original
    merged_config = config.copy()
    
    # Apply environment overrides
    for key, value in env_overrides.items():
        merged_config[key] = value
        logger.info(f"Applied environment override: {key} = {value}")
    
    return merged_config

def get_env_config(config_path: Optional[str] = None, force_reload: bool = False) -> Dict[str, Any]:
    """
    Get configuration with environment variable overrides applied.
    
    Args:
        config_path: Optional specific config path
        force_reload: Whether to force reload the config
        
    Returns:
        Configuration dictionary with environment overrides applied
    """
    # Import here to avoid circular imports
    try:
        from .config_loader import load_config, get_config_path_for_environment
        from .config_loader import _default_config_cache, _default_config_loaded
        
        # Get base configuration
        if config_path:
            base_config = load_config(config_path=config_path, force_reload=force_reload)
        else:
            env_config_path = get_config_path_for_environment()
            if not _default_config_loaded or force_reload:
                load_config(config_path=env_config_path, force_reload=True)
            base_config = _default_config_cache if _default_config_cache is not None else {}
        
        # Apply environment overrides
        final_config = merge_config_with_env(base_config)
        
        return final_config
    except ImportError:
        # Fallback if config_loader is not available
        return {}

def list_environment_variables() -> Dict[str, str]:
    """
    List all available environment variables for configuration.
    
    Returns:
        Dictionary mapping environment variable names to their descriptions
    """
    env_vars = {}
    
    for env_key, config_key in ENV_CONFIG_MAPPING.items():
        env_var_name = f"{ENV_PREFIX}{env_key}"
        env_vars[env_var_name] = {
            "config_key": config_key,
            "description": f"Override {config_key} setting",
            "current_value": os.getenv(env_var_name, "Not set")
        }
    
    return env_vars

def validate_environment_config() -> Dict[str, Any]:
    """
    Validate environment variable configuration.
    
    Returns:
        Dictionary with validation results
    """
    validation_results = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "overrides_applied": 0
    }
    
    env_overrides = get_environment_overrides()
    validation_results["overrides_applied"] = len(env_overrides)
    
    # Check for required environment variables in production
    if os.getenv('ENVIRONMENT', '').lower() == 'production':
        required_vars = [
            "WEBSITE_MONITOR_SMTP_SERVER",
            "WEBSITE_MONITOR_SMTP_USERNAME",
            "WEBSITE_MONITOR_SMTP_PASSWORD"
        ]
        
        for required_var in required_vars:
            if not os.getenv(required_var):
                validation_results["errors"].append(f"Required environment variable {required_var} not set in production")
                validation_results["valid"] = False
    
    # Check for invalid values
    for env_key, config_key in ENV_CONFIG_MAPPING.items():
        env_var_name = f"{ENV_PREFIX}{env_key}"
        env_value = os.getenv(env_var_name)
        
        if env_value is not None:
            try:
                convert_env_value(env_value, env_key)
            except Exception as e:
                validation_results["errors"].append(f"Invalid value for {env_var_name}: {str(e)}")
                validation_results["valid"] = False
    
    return validation_results 