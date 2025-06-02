import logging
import logging.handlers
import os
from src.config_loader import get_config

# Cache for logger instances to avoid re-configuring the same logger
_loggers = {}

def setup_logging(config_path=None, logger_name='WebsiteMonitor'):
    """
    Sets up logging for the application.
    Reads configuration from config_loader, optionally using a specific config_path.
    Returns a configured logger instance.
    """
    # If a logger with this name is already configured and has handlers, return it
    # This check is basic; for true idempotency, one might check if config has changed
    if logger_name in _loggers and _loggers[logger_name].hasHandlers():
        return _loggers[logger_name]

    current_config = None
    if config_path:
        # Ensure get_config can accept config_path
        # Forcing a reload of config if a specific path is given, 
        # as it might differ from a globally cached one.
        from src.config_loader import load_config # Use load_config directly for specific path
        current_config = load_config(config_path=config_path)
    else:
        current_config = get_config() # Uses global/default config if no path given
    
    log_level_str = current_config.get('log_level', 'INFO').upper()
    
    # Determine log file path based on logger name
    # This allows different log files for different parts of the app (e.g. main vs dashboard)
    if logger_name == 'FlaskDashboard':
        log_file_path = current_config.get('log_file_dashboard', 'data/dashboard.log')
    else: # Default for 'WebsiteMonitor' and any other loggers
        log_file_path = current_config.get('log_file_path', 'data/monitoring.log')

    numeric_level = getattr(logging, log_level_str, logging.INFO)

    # Ensure the directory for the log file exists
    log_dir = os.path.dirname(log_file_path)
    if log_dir and not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir, exist_ok=True)
        except OSError as e:
            print(f"Error creating log directory {log_dir} for {logger_name}: {e}. Logging to console only for this handler.")
            log_file_path = None # Disable file logging if dir creation fails

    logger = logging.getLogger(logger_name)
    logger.setLevel(numeric_level)
    
    # Remove existing handlers to prevent duplicate logs if this function is called again for the same logger
    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s')

    # Console handler (always add for visibility)
    ch = logging.StreamHandler()
    ch.setLevel(numeric_level)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # File handler (RotatingFileHandler)
    if log_file_path: # Only add file handler if path is valid and directory was created
        try:
            # Max 5MB per file, keep 3 backup logs
            fh = logging.handlers.RotatingFileHandler(log_file_path, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
            fh.setLevel(numeric_level)
            fh.setFormatter(formatter)
            logger.addHandler(fh)
        except Exception as e:
            # Log to console if file handler fails (e.g. permissions)
            logger.error(f"Failed to set up file logging at {log_file_path} for {logger_name}: {e}", exc_info=True)
    
    # Cache the configured logger
    _loggers[logger_name] = logger
    logger.info(f"Logging for '{logger_name}' setup complete. Level: {log_level_str}, File: {log_file_path if log_file_path else 'Console Only'}")
    return logger

if __name__ == '__main__':
    # Example usage:
    # Test with default config for WebsiteMonitor logger
    print("--- Testing logger with default config (WebsiteMonitor) ---")
    logger_default = setup_logging() # logger_name defaults to 'WebsiteMonitor'
    logger_default.info("Default WebsiteMonitor logger: Info message.")
    logger_default.debug("Default WebsiteMonitor logger: Debug message (should not appear if default level is INFO).")

    # Test with default config for FlaskDashboard logger
    print("\n--- Testing logger with default config (FlaskDashboard) ---")
    # This assumes config.yaml might have 'log_file_dashboard' or will use 'data/dashboard.log'
    logger_dashboard = setup_logging(logger_name='FlaskDashboard')
    logger_dashboard.info("FlaskDashboard logger: Info message.")

    # Test with a specific config file (dummy_test_config.yaml)
    dummy_config_content = {
        'log_level': 'DEBUG',
        'log_file_path': 'data/test_specific_monitor.log',
        'log_file_dashboard': 'data/test_specific_dashboard.log'
    }
    project_root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    dummy_config_path = os.path.join(project_root_dir, 'config', 'dummy_test_config.yaml')
    os.makedirs(os.path.dirname(dummy_config_path), exist_ok=True)
    import yaml
    with open(dummy_config_path, 'w') as f_yaml:
        yaml.dump(dummy_config_content, f_yaml)

    print(f"\n--- Testing WebsiteMonitor logger with specific config: {dummy_config_path} ---")
    logger_specific_monitor = setup_logging(config_path=dummy_config_path, logger_name='TestSpecificMonitor')
    logger_specific_monitor.debug("Specific Monitor logger: Debug message (should appear).")
    logger_specific_monitor.info("Specific Monitor logger: Info message.")

    print(f"\n--- Testing FlaskDashboard logger with specific config: {dummy_config_path} ---")
    logger_specific_dashboard = setup_logging(config_path=dummy_config_path, logger_name='TestSpecificDashboard')
    logger_specific_dashboard.debug("Specific Dashboard logger: Debug message (should appear).")
    logger_specific_dashboard.info("Specific Dashboard logger: Info message.")

    # Clean up notes
    print("\nNOTE: Dummy config and log files were created for testing in 'config' and 'data' directories.")
    print(f"Dummy config: {dummy_config_path}")
    print(f"Test monitor log: {dummy_config_content['log_file_path']}")
    print(f"Test dashboard log: {dummy_config_content['log_file_dashboard']}")
    print("Please review or remove them manually if desired.")

    print("\nLogging setup tests finished.") 