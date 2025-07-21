import cv2
import numpy as np
import requests
from io import BytesIO
from PIL import Image

def analyze_single_image(image_source, threshold=100):
    """
    Analyze blur for a single image from path or URL.
    Returns: dict with blur analysis results.
    """
    # Load image from different sources
    if image_source.startswith(('http://', 'https://')):
        response = requests.get(image_source)
        img = np.array(Image.open(BytesIO(response.content)))
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    else:
        img = cv2.imread(image_source)
    
    if img is None:
        return {"error": "Image loading failed"}
    
    # Standardize size for consistent analysis
    img = cv2.resize(img, (1280, 720))
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Method 1: Laplacian Variance
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    
    # Method 2: Spatial Blur Detection
    from blur_detector import detectBlur
    blur_map = detectBlur(gray, downsampling_factor=4)
    blur_percentage = np.mean(blur_map) * 100
    
    # Combined decision logic
    is_blurry = laplacian_var < threshold or blur_percentage > 15
    
    return {
        "source": image_source,
        "is_blurry": is_blurry,
        "laplacian_score": round(laplacian_var, 2),
        "blur_percentage": round(blur_percentage, 1),
        "threshold": threshold
    }

if __name__ == "__main__":
    # Replace with your image path or URL
    image_path_or_url = "studio7.png"
    result = analyze_single_image(image_path_or_url)
    print(result)
