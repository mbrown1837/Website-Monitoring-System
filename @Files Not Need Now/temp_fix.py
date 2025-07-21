@app.route('/data_files/<path:filepath>')
def data_files(filepath):
    # Ensure the path is secure and within the intended directory
    logger.debug(f"Attempting to serve file from data directory: {filepath}")
    
    # Check if the file exists first
    full_path = os.path.join(DATA_DIRECTORY, filepath)
    if not os.path.isfile(full_path):
        logger.warning(f"File not found in data directory: {full_path}")
        # Check if this is a snapshot path that might be in an alternative format
        # Try to normalize the path by handling common path variations
        
        # If it's a baseline path, try alternative locations
        if 'baseline' in filepath:
            # Try different baseline path patterns
            variations = [
                filepath,
                # For paths from older versions
                filepath.replace('/baseline_', '/baseline/baseline_'),
                filepath.replace('/baseline/', '/'),
                # For newer path format
                filepath.replace('baseline.png', 'home.png'),
                filepath.replace('baseline.png', 'homepage.pn')
            ]
            
            # Try each variation
            for var_path in variations:
                var_full_path = os.path.join(DATA_DIRECTORY, var_path)
                if os.path.isfile(var_full_path):
                    logger.info(f"Found file at alternative path: {var_path}")
                    return send_from_directory(DATA_DIRECTORY, var_path, as_attachment=False)
                    
            # If we get here, none of the variations worked
            logger.error(f"Could not find any matching file for {filepath}")
            # Return placeholder image
            return redirect(url_for('static', filename='img/placeholder.png'))
    
    # Standard case - file exists at expected path
    try:
        return send_from_directory(DATA_DIRECTORY, filepath, as_attachment=False)
    except Exception as e:
        logger.error(f"Error serving file {filepath}: {e}")
        # Return placeholder image on error
        return redirect(url_for('static', filename='img/placeholder.png'))
