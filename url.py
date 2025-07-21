import cv2
import numpy as np
import requests
from io import BytesIO
from PIL import Image
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin

def analyze_single_image(image_source, threshold=100):
    if image_source.startswith(('http://', 'https://')):
        response = requests.get(image_source)
        img = np.array(Image.open(BytesIO(response.content)))
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    else:
        img = cv2.imread(image_source)
    
    if img is None:
        return {"error": "Image loading failed", "source": image_source}
    
    img = cv2.resize(img, (1280, 720))
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    from blur_detector import detectBlur
    blur_map = detectBlur(gray, downsampling_factor=4)
    blur_percentage = np.mean(blur_map) * 100
    is_blurry = laplacian_var < threshold or blur_percentage > 15
    
    return {
        "source": image_source,
        "is_blurry": is_blurry,
        "laplacian_score": round(laplacian_var, 2),
        "blur_percentage": round(blur_percentage, 1),
        "threshold": threshold
    }

def analyze_webpage_images(page_url, threshold=100, max_workers=10):
    try:
        response = requests.get(page_url)
        soup = BeautifulSoup(response.text, 'html.parser')
        img_urls = []
        for img in soup.find_all('img'):
            src = img.get('src')
            if src:
                if src.startswith(('http://', 'https://')):
                    img_urls.append(src)
                else:
                    img_urls.append(urljoin(page_url, src))
    except Exception as e:
        return {"error": f"Page processing failed: {str(e)}"}
    
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(analyze_single_image, url, threshold) for url in img_urls]
        for future in futures:
            try:
                results.append(future.result())
            except Exception as e:
                results.append({"error": str(e)})
    return results

if __name__ == "__main__":
    # Replace with your webpage URL
    page_url = "https://thewebturtles.com/"
    results = analyze_webpage_images(page_url)
    for res in results:
        print(res)
