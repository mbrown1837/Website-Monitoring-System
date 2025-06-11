import yaml
import os

# Default configuration path
DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yaml')

# Global cache for the default configuration
_default_config_cache = None
_default_config_loaded = False

# Legacy compatibility dictionary used by unit tests
# Mirrors the default configuration cache for easier test resets
_config_cache = {}

def load_config(config_path: str = DEFAULT_CONFIG_PATH, force_reload: bool = False) -> dict:
    """
    Loads configuration from the specified YAML file.

    Args:
        config_path (str): Path to the configuration file.
        force_reload (bool): If True, reloads the config even if cached (applies only to default config path).

    Returns:
        dict: The loaded configuration data.
    """
    global _default_config_cache, _default_config_loaded

    # If it's the default path and it's cached and not forcing reload, return cache
    if config_path == DEFAULT_CONFIG_PATH and _default_config_loaded and not force_reload:
        return _default_config_cache if _default_config_cache is not None else {}

    loaded_data = {}
    try:
        # Ensure the directory exists if it's the default path (for initial setup)
        if config_path == DEFAULT_CONFIG_PATH:
            config_dir = os.path.dirname(config_path)
            if config_dir and not os.path.exists(config_dir):
                os.makedirs(config_dir, exist_ok=True)
        
        if not os.path.exists(config_path):
            print(f"Warning: Configuration file not found at {config_path}. Returning empty config.")
            # If it's the default path and it doesn't exist, create an empty one.
            if config_path == DEFAULT_CONFIG_PATH:
                with open(config_path, 'w') as f: # Create empty config file
                    yaml.dump({}, f)
                print(f"Created empty default config file at {config_path}")
        else:
            with open(config_path, 'r', encoding='utf-8') as f:
                loaded_data = yaml.safe_load(f)
            if loaded_data is None: # Handle empty YAML file
                loaded_data = {}
        
    except FileNotFoundError:
        print(f"Error: Configuration file not found at {config_path}. Returning empty config.")
        # No explicit error for non-default paths not found, just return empty.
    except yaml.YAMLError as e:
        print(f"Error parsing YAML configuration file at {config_path}: {e}. Returning empty config.")
    except Exception as e:
        print(f"Unexpected error loading config from {config_path}: {e}. Returning empty config.")

    # Update cache only if it's the default configuration path
    if config_path == DEFAULT_CONFIG_PATH:
        _default_config_cache = loaded_data
        _default_config_loaded = True
        _config_cache.clear()
        _config_cache.update(loaded_data)
        
    return loaded_data

def get_config(config_path: str = None, force_reload: bool = False) -> dict:
    """
    Returns the configuration data.
    If config_path is provided, loads from that path.
    Otherwise, returns the (potentially cached) default configuration.

    Args:
        config_path (str, optional): Specific path to a configuration file.
        force_reload (bool): If True and using default path, forces a reload from disk.

    Returns:
        dict: The configuration data.
    """
    if config_path:
        # Load specific config file, do not use/update global default cache directly unless path is default
        return load_config(config_path=config_path, force_reload=force_reload)
    else:
        # Ensure default config is loaded if not already
        global _default_config_loaded
        if not _default_config_loaded or force_reload:
            load_config(config_path=DEFAULT_CONFIG_PATH, force_reload=True) # Will populate cache
        return _default_config_cache if _default_config_cache is not None else {}

def save_config(config_data: dict, config_path: str = DEFAULT_CONFIG_PATH) -> None:
    """
    Saves the provided configuration data to the YAML file.
    Updates the global default config cache if saving to the default path.

    Args:
        config_data (dict): The configuration dictionary to save.
        config_path (str, optional): The path to the configuration file.
                                     Defaults to DEFAULT_CONFIG_PATH.
    """
    global _default_config_cache, _default_config_loaded
    try:
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, sort_keys=False, default_flow_style=False)
        
        # If saved to the default path, update the cache
        if config_path == DEFAULT_CONFIG_PATH:
            _default_config_cache = config_data
            _default_config_loaded = True  # Mark as loaded/current
            _config_cache.clear()
            _config_cache.update(config_data)
        print(f"Configuration saved to {config_path}")
    except Exception as e:
        print(f"Error saving configuration to {config_path}: {e}")
        raise

if __name__ == '__main__':
    print("--- Config Loader Demo --- Donaldson ")

    # 1. Get default config (should load or create if not exists)
    print("\n1. Loading default config...")
    default_conf = get_config()
    print(f"Default config (initial): {default_conf}")
    if not default_conf:
        print("Default config is empty or was just created.")

    # 2. Save some data to default config
    print("\n2. Saving to default config...")
    default_conf['sample_setting'] = 'Hello World'
    default_conf['log_level'] = 'INFO' # Ensure a log_level for logger tests
    save_config(default_conf) # Saves to DEFAULT_CONFIG_PATH
    reloaded_default_conf = get_config(force_reload=True)
    print(f"Reloaded default config: {reloaded_default_conf}")
    assert reloaded_default_conf.get('sample_setting') == 'Hello World'

    # 3. Create and load a specific, temporary config file
    print("\n3. Testing specific config file...")
    specific_config_content = {'specific_key': 'specific_value', 'log_level': 'DEBUG'}
    temp_config_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'temp_config_test')
    os.makedirs(temp_config_dir, exist_ok=True)
    specific_config_file = os.path.join(temp_config_dir, 'specific.yaml')
    with open(specific_config_file, 'w') as f:
        yaml.dump(specific_config_content, f)
    
    loaded_specific = get_config(config_path=specific_config_file)
    print(f"Loaded specific config from {specific_config_file}: {loaded_specific}")
    assert loaded_specific.get('specific_key') == 'specific_value'

    # Verify default config was not affected by loading specific config
    current_default_conf = get_config()
    print(f"Current default config (should be unchanged): {current_default_conf}")
    assert current_default_conf.get('sample_setting') == 'Hello World'
    assert current_default_conf.get('specific_key') is None

    # 4. Save to the specific config file
    print("\n4. Saving to specific config file...")
    loaded_specific['new_specific_key'] = 'another value'
    save_config(loaded_specific, config_path=specific_config_file)
    reloaded_specific = get_config(config_path=specific_config_file, force_reload=True)
    print(f"Reloaded specific config: {reloaded_specific}")
    assert reloaded_specific.get('new_specific_key') == 'another value'

    # 5. Test get_config for non-existent specific file
    print("\n5. Test loading non-existent specific config...")
    non_existent_path = os.path.join(temp_config_dir, 'non_existent.yaml')
    non_existent_conf = get_config(config_path=non_existent_path)
    print(f"Config from non-existent path '{non_existent_path}': {non_existent_conf}")
    assert non_existent_conf == {}

    # Clean up temporary specific config file and directory
    if os.path.exists(specific_config_file):
        os.remove(specific_config_file)
    if os.path.exists(temp_config_dir):
        try:
            os.rmdir(temp_config_dir) # Only removes if empty
            print(f"Cleaned up {temp_config_dir}")
        except OSError:
            print(f"Could not remove {temp_config_dir} as it might not be empty.")
    
    print("\n--- Config Loader Demo Finished --- Donaldson") 