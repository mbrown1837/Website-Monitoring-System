from PIL import Image, ImageChops, ImageDraw, ImageFont
import os
from datetime import datetime
from src.logger_setup import setup_logging

logger = setup_logging()

def get_change_region_with_labels(base_path, latest_path, output_path=None):
    """
    Analyze two images to detect changes, crop to the changed region, and create a before/after comparison image.
    
    Args:
        base_path (str): Path to the baseline/before image
        latest_path (str): Path to the latest/after image
        output_path (str, optional): Path where to save the comparison image. If None, one is generated.
        
    Returns:
        tuple: (bbox, output_path) where bbox is the bounding box of changes (x1, y1, x2, y2) or None if no changes,
               and output_path is the path to the saved comparison image or None if no changes or error.
    """
    try:
        # Check if both image paths exist
        if not os.path.exists(base_path):
            logger.error(f"Base image not found: {base_path}")
            return None, None
            
        if not os.path.exists(latest_path):
            logger.error(f"Latest image not found: {latest_path}")
            return None, None
            
        # Open and convert images to RGB
        base = Image.open(base_path).convert('RGB')
        latest = Image.open(latest_path).convert('RGB')
        
        # Calculate pixel difference
        diff = ImageChops.difference(base, latest)
        
        # Convert to grayscale and threshold
        diff_gray = diff.convert('L')
        diff_thresh = diff_gray.point(lambda p: 255 if p > 30 else 0)
        
        # Get bounding box of changes
        bbox = diff_thresh.getbbox()
        
        if not bbox:
            logger.info("No changes detected between the images")
            return None, None
            
        # Generate an output path if none provided
        if output_path is None:
            # Get directory from latest image
            output_dir = os.path.dirname(latest_path)
            # Create 'diffs' subdirectory if it doesn't exist
            diff_dir = os.path.join(output_dir, "diffs")
            os.makedirs(diff_dir, exist_ok=True)
            
            # Create filename based on timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_filename = os.path.basename(base_path)
            name_without_ext = os.path.splitext(base_filename)[0]
            output_path = os.path.join(diff_dir, f"{name_without_ext}_change_{timestamp}.png")
        
        # Crop changed regions from both images
        base_region = base.crop(bbox)
        latest_region = latest.crop(bbox)
        
        # Dimensions for combined image
        width, height = base_region.size
        label_height = 40  # Height for label area above images
        combined = Image.new('RGB', (width * 2, height + label_height), 'white')
        
        # Paste base and latest cropped images below the label area
        combined.paste(base_region, (0, label_height))
        combined.paste(latest_region, (width, label_height))
        
        # Draw elements
        draw = ImageDraw.Draw(combined)
        
        # Draw vertical divider line between before and after images
        draw.line((width, label_height, width, height + label_height), fill='gray', width=1)
        
        # Draw white horizontal line above images (separator)
        draw.line((0, label_height, width * 2, label_height), fill='white', width=2)
        
        # Load a bold font, fallback to default if not found
        try:
            font = ImageFont.truetype("arialbd.ttf", 24)  # Arial Bold
        except IOError:
            try:
                font = ImageFont.truetype("arial.ttf", 24)  # Regular Arial as fallback
            except IOError:
                font = ImageFont.load_default()
        
        # Calculate text positions (centered above each image)
        before_text_pos = (width // 4 - 30, 5)
        after_text_pos = (width + width // 4 - 20, 5)
        
        # Draw bold text labels
        draw.text(before_text_pos, "BEFORE", fill="black", font=font)
        draw.text(after_text_pos, "AFTER", fill="black", font=font)
        
        # Save combined image
        combined.save(output_path)
        logger.info(f"Before/After comparison saved to: {output_path}")
        logger.info(f"Changed region coordinates: {bbox}")
        
        # Get path relative to the data directory for web UI display
        try:
            # Try to make the path relative to data directory
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            data_directory = os.path.join(project_root, 'data')
            relative_path = os.path.relpath(output_path, data_directory)
            # Normalize for web display
            web_path = relative_path.replace("\\", "/")
        except:
            # If that fails, use the original path
            web_path = output_path
            
        return bbox, web_path
        
    except Exception as e:
        logger.error(f"Error generating change region with labels: {e}", exc_info=True)
        return None, None

def create_full_comparison(base_path, latest_path, output_path=None):
    """
    Create a full side-by-side comparison of two images with before/after labels.
    
    Args:
        base_path (str): Path to the baseline/before image
        latest_path (str): Path to the latest/after image
        output_path (str, optional): Path where to save the comparison image. If None, one is generated.
        
    Returns:
        str: Path to saved comparison image or None if error
    """
    try:
        # Check if both image paths exist
        if not os.path.exists(base_path):
            logger.error(f"Base image not found: {base_path}")
            return None
            
        if not os.path.exists(latest_path):
            logger.error(f"Latest image not found: {latest_path}")
            return None
            
        # Open images
        base = Image.open(base_path).convert('RGB')
        latest = Image.open(latest_path).convert('RGB')
        
        # Generate an output path if none provided
        if output_path is None:
            # Get directory from latest image
            output_dir = os.path.dirname(latest_path)
            # Create 'comparisons' subdirectory if it doesn't exist
            comp_dir = os.path.join(output_dir, "comparisons")
            os.makedirs(comp_dir, exist_ok=True)
            
            # Create filename based on timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_filename = os.path.basename(base_path)
            name_without_ext = os.path.splitext(base_filename)[0]
            output_path = os.path.join(comp_dir, f"{name_without_ext}_full_comparison_{timestamp}.png")
        
        # Resize images to same height if they differ
        if base.height != latest.height:
            # Resize proportionally to match heights
            new_width = int(latest.width * (base.height / latest.height))
            latest = latest.resize((new_width, base.height), Image.Resampling.LANCZOS)
        
        # Dimensions for combined image
        width = base.width + latest.width
        height = max(base.height, latest.height)
        label_height = 40
        
        # Create new image
        combined = Image.new('RGB', (width, height + label_height), 'white')
        
        # Paste images
        combined.paste(base, (0, label_height))
        combined.paste(latest, (base.width, label_height))
        
        # Draw elements
        draw = ImageDraw.Draw(combined)
        
        # Draw divider
        draw.line((base.width, label_height, base.width, height + label_height), fill='gray', width=1)
        
        # Load font
        try:
            font = ImageFont.truetype("arialbd.ttf", 24)
        except IOError:
            try:
                font = ImageFont.truetype("arial.ttf", 24)
            except IOError:
                font = ImageFont.load_default()
        
        # Draw labels
        before_text_pos = (base.width // 2 - 40, 5)
        after_text_pos = (base.width + latest.width // 2 - 30, 5)
        
        draw.text(before_text_pos, "BEFORE", fill="black", font=font)
        draw.text(after_text_pos, "AFTER", fill="black", font=font)
        
        # Save combined image
        combined.save(output_path)
        logger.info(f"Full before/after comparison saved to: {output_path}")
        
        # Get path relative to the data directory for web UI display
        try:
            # Try to make the path relative to data directory
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            data_directory = os.path.join(project_root, 'data')
            relative_path = os.path.relpath(output_path, data_directory)
            # Normalize for web display
            web_path = relative_path.replace("\\", "/")
            return web_path
        except:
            # If that fails, use the original path
            return output_path
            
    except Exception as e:
        logger.error(f"Error generating full comparison: {e}", exc_info=True)
        return None

if __name__ == '__main__':
    # Simple test case
    logger.info("----- Visual Change Detector Test -----")
    
    # Replace these paths with actual test images
    test_base_image = 'test_base.png'
    test_latest_image = 'test_latest.png'
    
    if os.path.exists(test_base_image) and os.path.exists(test_latest_image):
        change_bbox, diff_path = get_change_region_with_labels(test_base_image, test_latest_image)
        
        if change_bbox:
            logger.info(f"Change detected at: {change_bbox}")
            logger.info(f"Comparison image saved to: {diff_path}")
        else:
            logger.info("No changes detected between test images")
            
        # Test full comparison
        full_comp_path = create_full_comparison(test_base_image, test_latest_image)
        if full_comp_path:
            logger.info(f"Full comparison saved to: {full_comp_path}")
    else:
        logger.warning(f"Test images not found. Create {test_base_image} and {test_latest_image} for testing.")
    
    logger.info("----- Visual Change Detector Test Finished -----") 