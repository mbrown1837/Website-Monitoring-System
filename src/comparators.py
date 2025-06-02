import difflib
from bs4 import BeautifulSoup
from src.logger_setup import setup_logging
from PIL import Image, ImageChops, ImageDraw
import numpy as np
import os
import diff_match_patch as dmp_module # Import the library

# Attempt to import OpenCV and scikit-image for SSIM, but make it optional
try:
    import cv2
    from skimage.metrics import structural_similarity_index as ssim
    OPENCV_SKIMAGE_AVAILABLE = True
except ImportError:
    OPENCV_SKIMAGE_AVAILABLE = False
    cv2 = None
    ssim = None

logger = setup_logging()

def _apply_ignore_regions(image: Image.Image, regions: list[list[int]]) -> Image.Image:
    """Applies ignore regions to an image by drawing black rectangles.

    Args:
        image (Image.Image): The input PIL Image.
        regions (list[list[int]]): A list of regions, where each region is [x, y, width, height].

    Returns:
        Image.Image: A new image with the specified regions blacked out.
    """
    if not regions:
        return image

    # Work on a copy to avoid modifying the original image
    img_copy = image.copy()
    draw = ImageDraw.Draw(img_copy)

    for region in regions:
        if len(region) == 4:
            x, y, w, h = region
            # Define the bounding box for the rectangle: (x1, y1, x2, y2)
            bbox = (x, y, x + w, y + h)
            try:
                draw.rectangle(bbox, fill="black")
                logger.debug(f"Applied ignore region: {bbox} to image.")
            except Exception as e:
                logger.error(f"Error applying ignore region {bbox}: {e}")
        else:
            logger.warning(f"Skipping invalid ignore region (must have 4 elements [x,y,w,h]): {region}")
    return img_copy

def extract_text_from_html(html_content: str) -> str:
    """
    Extracts and cleans text content from HTML.
    Removes script and style tags, and normalizes whitespace.
    """
    if not html_content:
        return ""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        # Remove script and style elements
        for script_or_style in soup(['script', 'style']):
            script_or_style.decompose()

        # Get text and normalize whitespace
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        return text
    except Exception as e:
        logger.error(f"Error extracting text from HTML: {e}", exc_info=True)
        return "" # Return empty string on error to avoid breaking comparisons

def compare_html_text_content(old_html: str, new_html: str) -> tuple[float, list[str]]:
    """
    Compares the textual content of two HTML documents.

    Args:
        old_html (str): The old HTML content.
        new_html (str): The new HTML content.

    Returns:
        tuple[float, list[str]]: 
            - Similarity ratio (0.0 to 1.0, where 1.0 is identical).
            - A list of strings representing the differences in a human-readable format.
    """
    old_text = extract_text_from_html(old_html)
    new_text = extract_text_from_html(new_html)

    if not old_text and not new_text:
        return 1.0, [] # Both empty, considered identical
    if not old_text or not new_text: # One is empty, the other is not
        # Could return 0.0 or handle as a major change; for now, 0.0
        # Diff might be large, so let's list all lines from the non-empty one
        diff_output = list(difflib.unified_diff(
            old_text.splitlines(),
            new_text.splitlines(),
            fromfile='old_version',
            tofile='new_version',
            lineterm=''
        ))
        return 0.0, diff_output


    # Using SequenceMatcher for similarity ratio
    similarity_ratio = difflib.SequenceMatcher(None, old_text, new_text).ratio()

    # Using unified_diff for human-readable differences
    # splitlines() is important for difflib
    diff_output = list(difflib.unified_diff(
        old_text.splitlines(),
        new_text.splitlines(),
        fromfile='old_version',
        tofile='new_version',
        lineterm='' # Keep newlines if any, but primarily for splitting
    ))
    
    logger.debug(f"HTML text comparison similarity: {similarity_ratio:.4f}")
    return similarity_ratio, diff_output

def compare_text_semantic(text1: str, text2: str) -> tuple[float, list[tuple[int, str]]]:
    """
    Compares two texts using diff-match-patch for a semantic diff.

    Args:
        text1 (str): The first text string.
        text2 (str): The second text string.

    Returns:
        tuple[float, list[tuple[int, str]]]:
            - Similarity score (0.0 to 1.0). Calculated as levenshtein_distance / max_len. 
              Closer to 1.0 means more similar (less distance).
            - A list of diffs in the format [(dmp_module.DIFF_DELETE, "text"), 
                                           (dmp_module.DIFF_INSERT, "text"), 
                                           (dmp_module.DIFF_EQUAL, "text")]
    """
    dmp = dmp_module.diff_match_patch()
    diffs = dmp.diff_main(text1, text2)
    dmp.diff_cleanupSemantic(diffs) # Improves human readability

    # Calculate similarity based on Levenshtein distance
    # Levenshtein distance: The number of single-character edits (insertions, deletions or substitutions)
    # required to change one word into the other.
    lev_distance = dmp.diff_levenshtein(diffs)
    
    # Normalize the distance to a similarity score (0.0 to 1.0)
    # A higher score means more similar (less distance)
    len1 = len(text1)
    len2 = len(text2)
    max_len = max(len1, len2)
    if max_len == 0: # Both strings are empty
        similarity = 1.0
    else:
        similarity = (max_len - lev_distance) / max_len
    
    logger.debug(f"Semantic text comparison similarity: {similarity:.4f}, Levenshtein distance: {lev_distance}")
    return similarity, diffs

def compare_html_structure(old_html: str, new_html: str) -> tuple[float, list[str]]:
    """
    Compares the structure of two HTML documents, ignoring text content within tags for the primary comparison.
    It serializes the parsed HTML (minus script, style, comments, and text nodes) and compares these representations.

    Args:
        old_html (str): The old HTML content.
        new_html (str): The new HTML content.

    Returns:
        tuple[float, list[str]]:
            - Similarity ratio of the structural representations (0.0 to 1.0).
            - A list of strings representing the differences in the serialized structure.
    """
    def get_structural_representation(html_content: str) -> str:
        if not html_content:
            return ""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            # Remove script, style, and comment tags
            for unwanted_tag in soup(['script', 'style', 'comment']):
                unwanted_tag.decompose()
            # Remove all text nodes to focus on tags and their attributes
            for element in soup.find_all(text=True):
                element.extract()
            # Return a string representation of the cleaned soup, pretty-printed for consistent formatting
            return soup.prettify()
        except Exception as e:
            logger.error(f"Error generating structural representation from HTML: {e}", exc_info=True)
            return "" # Return empty on error

    old_structure_str = get_structural_representation(old_html)
    new_structure_str = get_structural_representation(new_html)

    if not old_structure_str and not new_structure_str:
        return 1.0, []
    if not old_structure_str or not new_structure_str:
        # If one is empty, consider it a 0 similarity and show the diff
        diff_output = list(difflib.unified_diff(
            old_structure_str.splitlines(),
            new_structure_str.splitlines(),
            fromfile='old_structure',
            tofile='new_structure',
            lineterm=''
        ))
        return 0.0, diff_output

    similarity_ratio = difflib.SequenceMatcher(None, old_structure_str, new_structure_str).ratio()
    
    diff_output = list(difflib.unified_diff(
        old_structure_str.splitlines(),
        new_structure_str.splitlines(),
        fromfile='old_structure',
        tofile='new_structure',
        lineterm=''
    ))

    logger.debug(f"HTML structural comparison similarity: {similarity_ratio:.4f}")
    return similarity_ratio, diff_output

def extract_meta_tags(html_content: str, meta_names: list[str]) -> dict[str, str | None]:
    """Extracts specified meta tags (by name) from HTML content."""
    if not html_content:
        return {name: None for name in meta_names}
    soup = BeautifulSoup(html_content, 'html.parser')
    extracted_tags = {}
    for name in meta_names:
        tag = soup.find('meta', attrs={'name': name})
        extracted_tags[name] = tag['content'] if tag and tag.has_attr('content') else None
    return extracted_tags

def compare_meta_tags(old_html: str, new_html: str, meta_names: list[str]) -> dict[str, dict[str, str | None]] :
    """Compares specified meta tags between old and new HTML content."""
    old_tags = extract_meta_tags(old_html, meta_names)
    new_tags = extract_meta_tags(new_html, meta_names)
    
    changes = {}
    for name in meta_names:
        if old_tags.get(name) != new_tags.get(name):
            changes[name] = {'old': old_tags.get(name), 'new': new_tags.get(name)}
            logger.debug(f"Meta tag '{name}' changed from '{old_tags.get(name)}' to '{new_tags.get(name)}'")
    return changes

def extract_links(html_content: str) -> set[str]:
    """Extracts all unique href values from anchor tags."""
    if not html_content:
        return set()
    soup = BeautifulSoup(html_content, 'html.parser')
    links = set()
    for a_tag in soup.find_all('a', href=True):
        links.add(a_tag['href'].strip())
    return links

def compare_links(old_html: str, new_html: str) -> dict[str, set[str]]:
    """Compares links found in old and new HTML content."""
    old_links = extract_links(old_html)
    new_links = extract_links(new_html)
    
    added_links = new_links - old_links
    removed_links = old_links - new_links
    
    changes = {}
    if added_links:
        changes['added'] = added_links
        logger.debug(f"Links added: {added_links}")
    if removed_links:
        changes['removed'] = removed_links
        logger.debug(f"Links removed: {removed_links}")
    return changes

def extract_canonical_url(html_content: str) -> str | None:
    """Extracts the canonical URL from the HTML content."""
    if not html_content:
        return None
    soup = BeautifulSoup(html_content, 'html.parser')
    canonical_tag = soup.find('link', rel='canonical', href=True)
    return canonical_tag['href'] if canonical_tag else None

def compare_canonical_urls(old_html: str, new_html: str) -> dict[str, str | None] | None:
    """Compares canonical URLs from old and new HTML content."""
    old_canonical = extract_canonical_url(old_html)
    new_canonical = extract_canonical_url(new_html)

    if old_canonical != new_canonical:
        change = {'old': old_canonical, 'new': new_canonical}
        logger.debug(f"Canonical URL changed from '{old_canonical}' to '{new_canonical}'")
        return change
    return None

def extract_image_sources(html_content: str) -> set[str]:
    """Extracts all unique src values from img tags."""
    if not html_content:
        return set()
    soup = BeautifulSoup(html_content, 'html.parser')
    img_sources = set()
    for img_tag in soup.find_all('img', src=True):
        img_sources.add(img_tag['src'].strip())
    return img_sources

def compare_image_sources(old_html: str, new_html: str) -> dict[str, set[str]]:
    """Compares image sources found in old and new HTML content.
    This checks if the URLs of images have changed, not the image content itself.
    """
    old_img_sources = extract_image_sources(old_html)
    new_img_sources = extract_image_sources(new_html)
    
    added_sources = new_img_sources - old_img_sources
    removed_sources = old_img_sources - new_img_sources
    
    changes = {}
    if added_sources:
        changes['added_images'] = added_sources
        logger.debug(f"Image sources added: {added_sources}")
    if removed_sources:
        changes['removed_images'] = removed_sources
        logger.debug(f"Image sources removed: {removed_sources}")
    return changes

def compare_screenshots(image_path1: str, image_path2: str, diff_image_path: str = None, ignore_regions: list[list[int]] = None) -> tuple[float, Image.Image | None]:
    """
    Compares two images and returns a difference score and optionally a difference image.
    Uses Mean Squared Error (MSE) for the score. Lower MSE means more similar.
    A score of 0 means identical images.

    Args:
        image_path1 (str): Path to the first image.
        image_path2 (str): Path to the second image.
        diff_image_path (str, optional): Path to save the difference image. If None, not saved.
        ignore_regions (list[list[int]], optional): List of [x,y,w,h] regions to ignore.

    Returns:
        tuple[float, Image.Image | None]:
            - Normalized MSE (0.0 to 1.0, where 0.0 is identical). Higher means more different.
            - A PIL Image object of the difference, or None if images are identical or error occurs.
    """
    try:
        img1_pil = Image.open(image_path1).convert('RGB')
        img2_pil = Image.open(image_path2).convert('RGB')
    except FileNotFoundError:
        logger.error(f"Error: One or both image files not found: {image_path1}, {image_path2}")
        return 1.0, None # Max difference if a file is missing
    except Exception as e:
        logger.error(f"Error opening images {image_path1}, {image_path2}: {e}")
        return 1.0, None # Max difference on error

    # Apply ignore regions before any other processing
    if ignore_regions:
        img1_pil = _apply_ignore_regions(img1_pil, ignore_regions)
        img2_pil = _apply_ignore_regions(img2_pil, ignore_regions)

    if img1_pil.size != img2_pil.size:
        logger.warning(f"Images have different sizes: {img1_pil.size} vs {img2_pil.size}. Resizing the second image to match the first for MSE comparison.")
        try:
            img2_pil = img2_pil.resize(img1_pil.size, Image.Resampling.LANCZOS) # Use a high-quality downsampling filter
        except Exception as e:
            logger.error(f"Error resizing image {image_path2}: {e}")
            return 1.0, None # Max difference if resize fails

    # MSE Calculation
    arr1 = np.array(img1_pil, dtype=np.float32)
    arr2 = np.array(img2_pil, dtype=np.float32)
    
    if arr1.shape != arr2.shape:
        logger.error(f"Numpy array shapes do not match after potential resize: {arr1.shape} vs {arr2.shape}. Cannot compute MSE.")
        return 1.0, None # Max difference

    mse = np.mean((arr1 - arr2) ** 2)
    
    # Normalize MSE to a 0-1 range. Max possible MSE is 255^2 if images are 8-bit.
    normalized_mse = mse / (255**2) 
    # Cap at 1.0 for safety
    normalized_mse = min(normalized_mse, 1.0) 

    diff_image = None
    if normalized_mse > 0: # Only generate diff image if there's a difference
        try:
            # ImageChops.difference requires images of the same mode and size.
            diff_pil_image = ImageChops.difference(img1_pil, img2_pil)
            
            diff_gray = diff_pil_image.convert('L')
            enhanced_diff_image = Image.eval(diff_gray, lambda x: 255 if x > 10 else 0) # Thresholding
            diff_image = enhanced_diff_image.convert('RGB') 

            if diff_image_path:
                os.makedirs(os.path.dirname(diff_image_path), exist_ok=True)
                diff_image.save(diff_image_path)
                logger.info(f"Difference image saved to {diff_image_path}")
        except Exception as e:
            logger.error(f"Error creating or saving difference image: {e}")
            diff_image = None # Ensure it's None if saving failed
    else:
        logger.info("Images are identical (MSE=0). No difference image generated.")

    logger.debug(f"Image comparison MSE: {mse:.4f}, Normalized MSE: {normalized_mse:.4f}")
    return normalized_mse, diff_image

def compare_screenshots_ssim(image_path1: str, image_path2: str, ignore_regions: list[list[int]] = None) -> float | None:
    """
    Compares two images using Structural Similarity Index (SSIM).
    Returns SSIM score ( -1 to 1, where 1 is perfect similarity). Returns None if error.
    Requires OpenCV and scikit-image.

    Args:
        image_path1 (str): Path to the first image.
        image_path2 (str): Path to the second image.
        ignore_regions (list[list[int]], optional): List of [x,y,w,h] regions to ignore.

    Returns:
        float | None: SSIM score or None if error.
    """
    if not OPENCV_SKIMAGE_AVAILABLE:
        logger.warning("OpenCV or scikit-image not available. Cannot perform SSIM comparison.")
        return None

    try:
        img1_cv = cv2.imread(image_path1)
        img2_cv = cv2.imread(image_path2)

        if img1_cv is None:
            logger.error(f"Failed to load image {image_path1} with OpenCV.")
            return None
        if img2_cv is None:
            logger.error(f"Failed to load image {image_path2} with OpenCV.")
            return None

        # Convert to PIL for applying ignore regions, then convert back to OpenCV format
        if ignore_regions:
            try:
                pil_img1 = Image.fromarray(cv2.cvtColor(img1_cv, cv2.COLOR_BGR2RGB))
                pil_img2 = Image.fromarray(cv2.cvtColor(img2_cv, cv2.COLOR_BGR2RGB))

                pil_img1_ignored = _apply_ignore_regions(pil_img1, ignore_regions)
                pil_img2_ignored = _apply_ignore_regions(pil_img2, ignore_regions)

                img1_cv = cv2.cvtColor(np.array(pil_img1_ignored), cv2.COLOR_RGB2BGR)
                img2_cv = cv2.cvtColor(np.array(pil_img2_ignored), cv2.COLOR_RGB2BGR)
                logger.debug(f"Successfully applied ignore regions for SSIM comparison.")
            except Exception as e:
                logger.error(f"Error applying ignore regions for SSIM: {e}")
                # Continue without ignore regions. Alternatively, could return None here.

        # Convert images to grayscale for SSIM, as it's typically applied on single channel
        img1_gray = cv2.cvtColor(img1_cv, cv2.COLOR_BGR2GRAY)
        img2_gray = cv2.cvtColor(img2_cv, cv2.COLOR_BGR2GRAY)

        # Resize img2_gray to match img1_gray if dimensions are different
        if img1_gray.shape != img2_gray.shape:
            logger.warning(f"Images have different sizes for SSIM: {img1_gray.shape} vs {img2_gray.shape}. Resizing second image.")
            img2_gray = cv2.resize(img2_gray, (img1_gray.shape[1], img1_gray.shape[0]), interpolation=cv2.INTER_AREA)

        # SSIM requires images to have a minimum window size (e.g., 7x7 by default).
        min_dim = 7 
        if img1_gray.shape[0] < min_dim or img1_gray.shape[1] < min_dim or \
           img2_gray.shape[0] < min_dim or img2_gray.shape[1] < min_dim:
            logger.warning(
                f"One or both images are too small for SSIM calculation (min dimension {min_dim}). Min image shape encountered: {min(img1_gray.shape, img2_gray.shape)}"
            )
            return None 

        ssim_score = ssim(img1_gray, img2_gray, data_range=img1_gray.max() - img1_gray.min())
        
        logger.debug(f"Image comparison SSIM score: {ssim_score:.4f}")
        return ssim_score

    except FileNotFoundError:
        logger.error(f"SSIM Error: One or both image files not found: {image_path1}, {image_path2}")
        return None
    except Exception as e:
        logger.error(f"Error during SSIM comparison of {image_path1} and {image_path2}: {e}", exc_info=True)
        return None

if __name__ == '__main__':
    logger.info("----- Comparators Demo: HTML Text Content -----")

    html_old_1 = """
    <html><head><title>Old Page</title></head>
    <body><h1>Welcome</h1><p>This is the old content.</p><script>console.log("old script")</script></body>
    </html>
    """
    html_new_1 = """
    <html><head><title>New Page</title></head>
    <body><h1>Welcome!</h1><p>This is the <strong>new</strong> content.</p><style>body { color: blue; }</style></body>
    </html>
    """
    html_new_1_minor_change = """
    <html><head><title>Old Page</title></head>
    <body><h1>Welcome</h1><p>This is the old content, with a tiny change.</p><script>console.log("old script")</script></body>
    </html>
    """
    html_identical_structure_diff_text = """
    <html><head><title>Old Page</title></head>
    <body><h1>Bienvenue</h1><p>Ceci est l'ancien contenu.</p></body>
    </html>
    """

    print("\n--- Test Case 1: Significant Change ---")
    ratio1, diff1 = compare_html_text_content(html_old_1, html_new_1)
    print(f"Similarity Ratio: {ratio1:.4f}")
    if diff1:
        print("Differences:")
        for line in diff1:
            print(line)
    else:
        print("No textual differences detected.")

    print("\n--- Test Case 2: Minor Change ---")
    ratio2, diff2 = compare_html_text_content(html_old_1, html_new_1_minor_change)
    print(f"Similarity Ratio: {ratio2:.4f}")
    if diff2:
        print("Differences:")
        for line in diff2:
            print(line)
    else:
        print("No textual differences detected.")

    print("\n--- Test Case 3: Identical Text (despite title/script/style changes) ---")
    # Modify html_new_1 to have same text as html_old_1 but different title/style/script
    html_new_3_same_text = """
    <html><head><title>Totally Different Title</title><style>p {font-size: 20px;}</style></head>
    <body><h1>Welcome</h1><p>This is the old content.</p><script>alert("new script")</script></body>
    </html>
    """
    ratio3, diff3 = compare_html_text_content(html_old_1, html_new_3_same_text)
    print(f"Similarity Ratio: {ratio3:.4f}")
    if diff3:
        print("Differences:")
        for line in diff3:
            print(line)
    else:
        print("No textual differences detected (this is the expected outcome for text comparison).")


    print("\n--- Test Case 4: Completely Different Text, Same Structure ---")
    ratio4, diff4 = compare_html_text_content(html_old_1, html_identical_structure_diff_text)
    print(f"Similarity Ratio: {ratio4:.4f}")
    if diff4:
        print("Differences:")
        for line in diff4:
            print(line)
    else:
        print("No textual differences detected.")

    print("\n--- Test Case 5: Old HTML is empty ---")
    html_empty = ""
    ratio5, diff5 = compare_html_text_content(html_empty, html_new_1)
    print(f"Similarity Ratio (old empty): {ratio5:.4f}")
    if diff5:
        print("Differences (old empty):")
        for line in diff5:
            print(line)

    print("\n--- Test Case 6: New HTML is empty ---")
    ratio6, diff6 = compare_html_text_content(html_old_1, html_empty)
    print(f"Similarity Ratio (new empty): {ratio6:.4f}")
    if diff6:
        print("Differences (new empty):")
        for line in diff6:
            print(line)

    print("\n--- Test Case 7: Both HTML are empty ---")
    ratio7, diff7 = compare_html_text_content(html_empty, html_empty)
    print(f"Similarity Ratio (both empty): {ratio7:.4f}")
    if diff7:
        print("Differences (both empty):")
        for line in diff7:
            print(line)
    
    logger.info("----- Comparators Demo: HTML Text Content Finished -----")

    logger.info("\n----- Comparators Demo: HTML Structure -----")
    html_struct_old = """<body><div><p><span>Text 1</span></p></div><script>var a=1;</script></body>"""
    html_struct_new_same = """<body><div><p><span>Text 2 DIFFERNT TEXT</span></p></div><style>.p{}</style></body>""" # Same structure, diff text/script/style
    html_struct_new_diff = """<body><ul><li>Item 1</li></ul><p>Extra</p></body>""" # Different structure
    html_struct_new_attr_change = """<body><div id=\"main\"><p class=\"content\"><span>Text 1</span></p></div></body>""" # Attributes changed

    print("\n--- Structure Test Case 1: Same Structure (Text/Script/Style changes ignored by this specific comparison) ---")
    struct_ratio1, struct_diff1 = compare_html_structure(html_struct_old, html_struct_new_same)
    print(f"Structure Similarity Ratio: {struct_ratio1:.4f}")
    if struct_diff1:
        print("Structural Differences:")
        for line in struct_diff1: print(line)
    else:
        print("No structural differences detected.") # Expected

    print("\n--- Structure Test Case 2: Different Structure ---")
    struct_ratio2, struct_diff2 = compare_html_structure(html_struct_old, html_struct_new_diff)
    print(f"Structure Similarity Ratio: {struct_ratio2:.4f}")
    if struct_diff2:
        print("Structural Differences:")
        for line in struct_diff2: print(line)

    print("\n--- Structure Test Case 3: Attribute Changes ---")
    # Note: prettify() might normalize attributes, so this test depends on its output.
    # And current get_structural_representation keeps attributes.
    struct_ratio3, struct_diff3 = compare_html_structure(html_struct_old, html_struct_new_attr_change)
    print(f"Structure Similarity Ratio: {struct_ratio3:.4f}") # Expect some difference due to attrs
    if struct_diff3:
        print("Structural Differences (attributes count as part of structure here):")
        for line in struct_diff3: print(line)
    
    logger.info("----- Comparators Demo: HTML Structure Finished -----")

    logger.info("\n----- Comparators Demo: Technical Elements -----")
    html_tech_old = """
    <html><head><title>Tech Page Old</title>
    <meta name="description" content="Old description">
    <meta name="keywords" content="old, key, words">
    <link rel="canonical" href="https://example.com/old-page">
    </head><body>
    <a href="/link1">Link 1</a> <a href="/link2">Link 2</a>
    <a href="/common-link">Common</a>
    </body></html>
    """
    html_tech_new = """
    <html><head><title>Tech Page New</title>
    <meta name="description" content="New exciting description!">
    <meta name="keywords" content="new, key, words, fresh">
    <link rel="canonical" href="https://example.com/new-page-canonical">
    </head><body>
    <a href="/link3">Link 3</a> <a href="/link4">Link 4</a>
    <a href="/common-link">Common Link Text Changed</a>
    </body></html>
    """
    html_tech_new_minor = """
    <html><head><title>Tech Page Old</title>
    <meta name="description" content="Old description">
    <meta name="keywords" content="old, key, words, added">
    <link rel="canonical" href="https://example.com/old-page">
    </head><body>
    <a href="/link1">Link 1</a> <a href="/link2">Link 2</a> <a href="/link_new">New Link</a>
    <a href="/common-link">Common</a>
    </body></html>
    """

    print("\n--- Technical Test Case 1: Meta Tags Comparison (Significant Change) ---")
    meta_changes = compare_meta_tags(html_tech_old, html_tech_new, ['description', 'keywords', 'author'])
    print(f"Meta Tag Changes: {meta_changes if meta_changes else 'None'}")

    print("\n--- Technical Test Case 2: Meta Tags Comparison (Minor Change) ---")
    meta_changes_minor = compare_meta_tags(html_tech_old, html_tech_new_minor, ['description', 'keywords'])
    print(f"Meta Tag Changes (Minor): {meta_changes_minor if meta_changes_minor else 'None'}")

    print("\n--- Technical Test Case 3: Link Comparison (Significant Change) ---")
    link_changes = compare_links(html_tech_old, html_tech_new)
    print(f"Link Changes: {link_changes if link_changes else 'None'}")

    print("\n--- Technical Test Case 4: Link Comparison (Minor Change - one added) ---")
    link_changes_minor = compare_links(html_tech_old, html_tech_new_minor)
    print(f"Link Changes (Minor): {link_changes_minor if link_changes_minor else 'None'}")

    print("\n--- Technical Test Case 5: Canonical URL Comparison (Change) ---")
    canonical_change = compare_canonical_urls(html_tech_old, html_tech_new)
    print(f"Canonical URL Change: {canonical_change if canonical_change else 'None'}")

    print("\n--- Technical Test Case 6: Canonical URL Comparison (No Change) ---")
    canonical_no_change = compare_canonical_urls(html_tech_old, html_tech_new_minor)
    print(f"Canonical URL Change (None expected): {canonical_no_change if canonical_no_change else 'None'}")

    logger.info("----- Comparators Demo: Technical Elements Finished -----")

    logger.info("\n----- Comparators Demo: Media Change (Image Sources) -----")
    html_img_old = """<body><img src=\"img1.jpg\"><img src=\"common.png\"></body>"""
    html_img_new_changed = """<body><img src=\"img_new.jpg\"><img src=\"common.png\"></body>"""
    html_img_new_added = """<body><img src=\"img1.jpg\"><img src=\"common.png\"><img src=\"extra.gif\"></body>"""
    html_img_new_removed = """<body><img src=\"common.png\"></body>"""

    print("\n--- Image Source Test Case 1: Changed source ---")
    img_src_changes1 = compare_image_sources(html_img_old, html_img_new_changed)
    print(f"Image Source Changes: {img_src_changes1 if img_src_changes1 else 'None'}")

    print("\n--- Image Source Test Case 2: Added source ---")
    img_src_changes2 = compare_image_sources(html_img_old, html_img_new_added)
    print(f"Image Source Changes: {img_src_changes2 if img_src_changes2 else 'None'}")

    print("\n--- Image Source Test Case 3: Removed source ---")
    img_src_changes3 = compare_image_sources(html_img_old, html_img_new_removed)
    print(f"Image Source Changes: {img_src_changes3 if img_src_changes3 else 'None'}")

    print("\n--- Image Source Test Case 4: No change ---")
    img_src_changes4 = compare_image_sources(html_img_old, html_img_old)
    print(f"Image Source Changes: {img_src_changes4 if img_src_changes4 else 'None'}")

    logger.info("----- Comparators Demo: Media Change (Image Sources) Finished -----")

    logger.info("\n----- Comparators Demo: Visual Screenshot Comparison -----")

    # Create dummy image files for testing
    def create_dummy_image(path, size=(100,100), color1=(255,0,0), color2=(0,0,255)):
        img = Image.new('RGB', size, color1)
        # Create a small square of a different color for non-identical images
        if color1 != color2:
            for i in range(size[0]//4):
                for j in range(size[1]//4):
                    img.putpixel((i,j), color2)
        img.save(path)
        return path

    # Ensure data/test_images directory exists
    test_img_dir = os.path.join("data", "test_images")
    if not os.path.exists(test_img_dir):
        os.makedirs(test_img_dir)

    img_path_1 = create_dummy_image(os.path.join(test_img_dir, "img_A.png"), color1=(200,200,200))
    img_path_2_identical = create_dummy_image(os.path.join(test_img_dir, "img_A_identical.png"), color1=(200,200,200))
    img_path_3_minor_diff = create_dummy_image(os.path.join(test_img_dir, "img_B_minor.png"), color1=(200,200,200), color2=(190,200,200))
    img_path_4_major_diff = create_dummy_image(os.path.join(test_img_dir, "img_C_major.png"), color1=(255,0,0), color2=(0,0,255))
    img_path_5_diff_size = create_dummy_image(os.path.join(test_img_dir, "img_D_diff_size.png"), size=(50,50), color1=(0,255,0))
    diff_save_path = os.path.join(test_img_dir, "diff_output.png")

    print("\n--- Screenshot Compare Test 1: Identical Images ---")
    score1, diff_img1 = compare_screenshots(img_path_1, img_path_2_identical)
    print(f"Score (Identical): {score1:.4f} (Expected near 0.0)")
    assert score1 < 0.0001, "Identical images should have near zero score."
    assert diff_img1 is None, "Diff image should be None for identical images."

    print("\n--- Screenshot Compare Test 2: Minor Difference ---")
    score2, diff_img2 = compare_screenshots(img_path_1, img_path_3_minor_diff, diff_image_path=diff_save_path + "_minor.png")
    print(f"Score (Minor Diff): {score2:.4f}")
    assert 0 < score2 < 0.1, "Minor diff score out of expected range."
    assert diff_img2 is not None, "Diff image should exist for minor differences."

    print("\n--- Screenshot Compare Test 3: Major Difference ---")
    score3, diff_img3 = compare_screenshots(img_path_1, img_path_4_major_diff, diff_image_path=diff_save_path + "_major.png")
    print(f"Score (Major Diff): {score3:.4f}")
    assert score3 > 0.1, "Major diff score too low."
    assert diff_img3 is not None, "Diff image should exist for major differences."

    print("\n--- Screenshot Compare Test 4: Different Sizes ---")
    score4, diff_img4 = compare_screenshots(img_path_1, img_path_5_diff_size)
    print(f"Score (Different Sizes): {score4:.4f} (Expected 1.0)")
    assert score4 == 1.0, "Different sized images should have score 1.0"
    assert diff_img4 is None, "Diff image should be None for different sized images by this logic."

    print("\n--- Screenshot Compare Test 5: File Not Found ---")
    score5, diff_img5 = compare_screenshots(img_path_1, "non_existent_image.png")
    print(f"Score (File Not Found): {score5:.4f} (Expected 1.0)")
    assert score5 == 1.0, "Missing file should result in score 1.0"
    assert diff_img5 is None

    logger.info("----- Comparators Demo: Visual Screenshot Comparison Finished -----") 