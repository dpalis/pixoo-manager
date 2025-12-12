---
id: "020"
title: "O(n²) nested loops in image processing"
status: pending
priority: p3
category: performance
source: performance-oracle-review
created: 2025-12-12
---

# O(n²) Nested Loops in Image Processing

## Problem

The `remove_dark_halos` function uses nested loops to process every pixel, which is O(n²) for n×n images. For 64×64 images this is 4096 iterations - acceptable but could be optimized.

## Location

- `app/services/gif_converter.py` - `remove_dark_halos()` function (lines 195-243)

## Current Code

```python
def remove_dark_halos(img: Image.Image) -> Image.Image:
    pixels = img.load()
    for y in range(img.height):
        for x in range(img.width):
            # Check each pixel and neighbors
            # O(n²) complexity
            ...
```

## Analysis

For 64×64 images:
- Current: 4,096 iterations (acceptable)
- For larger images: Could be slow

The nested loop structure is inherent to pixel-by-pixel operations. Optimizations:

## Potential Optimizations

1. **Use NumPy vectorization**:
```python
import numpy as np

def remove_dark_halos_optimized(img: Image.Image) -> Image.Image:
    arr = np.array(img)
    # Vectorized operations on array
    # Convolution for neighbor checking
    from scipy.ndimage import convolve
    kernel = np.array([[1,1,1], [1,0,1], [1,1,1]]) / 8
    avg_neighbors = convolve(arr, kernel[:,:,np.newaxis])
    # Apply threshold
    ...
    return Image.fromarray(arr)
```

2. **Use Pillow filters** (if applicable):
```python
from PIL import ImageFilter
img = img.filter(ImageFilter.MedianFilter(size=3))
```

## Impact

- Severity: Nice-to-have (current performance is acceptable for 64×64)
- Effect: Marginal improvement for target use case
- Note: Only optimize if processing larger images or batches
