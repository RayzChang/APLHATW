from PIL import Image
import numpy as np
import os

try:
    path = r"c:\Users\Admin\Desktop\Code\台股交易推手\frontend\public\logo.png"
    img = Image.open(path).convert('RGBA')
    arr = np.array(img).astype(float)
    
    # Estimate background color from top-left 10x10 chunk
    bg_color = np.median(arr[:10, :10, :3], axis=(0,1))
    
    # Calculate difference from background
    diff = np.sqrt(np.sum((arr[:,:,:3] - bg_color)**2, axis=2))
    
    # Smooth alpha transition
    alpha = np.clip((diff - 20) * 10, 0, 255)
    arr[:,:,3] = alpha
    
    # Save image
    Image.fromarray(arr.astype(np.uint8)).save(path)
    print("Background removed successfully.")
except Exception as e:
    print("Error:", e)
