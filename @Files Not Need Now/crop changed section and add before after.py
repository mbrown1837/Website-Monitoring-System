from PIL import Image, ImageChops, ImageDraw, ImageFont

def get_change_region_with_labels(base_path, latest_path, output_path):
    base = Image.open(base_path).convert('RGB')
    latest = Image.open(latest_path).convert('RGB')
    
    # Calculate pixel difference
    diff = ImageChops.difference(base, latest)
    
    # Convert to grayscale and threshold
    diff_gray = diff.convert('L')
    diff_thresh = diff_gray.point(lambda p: 255 if p > 30 else 0)
    
    # Get bounding box of changes
    bbox = diff_thresh.getbbox()
    
    if bbox:
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
        print(f"Before/After comparison saved to: {output_path}")
        print(f"Changed region coordinates: {bbox}")
        return bbox
    else:
        print("No changes detected between the images")
        return None

# Usage example:
if __name__ == "__main__":
    # Replace these paths with your actual image paths
    base_image = 'base.png'
    latest_image = 'latest.png'
    output_image = 'before_after_comparison.png'
    
    # Run the comparison
    change_bbox = get_change_region_with_labels(base_image, latest_image, output_image)
    
    if change_bbox:
        print("Comparison completed successfully!")
    else:
        print("No changes found between images.")
