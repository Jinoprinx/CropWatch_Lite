"""
CropWatch Lite - Remote Sensing Indices Engine
Vectorized mathematical formulations for Satellite Multispectral and Drone RGB / Multispectral bands.
"""

from typing import Dict, Union
import numpy as np


class SpectralIndices:
    """
    Computes standard and visible-band vegetation indices for precision agriculture.
    Supports single pixel values, 1D timeseries, or 2D/3D geospatial raster arrays.
    """

    @staticmethod
    def ndvi(nir: np.ndarray, red: np.ndarray, eps: float = 1e-7) -> np.ndarray:
        """
        Normalized Difference Vegetation Index (NDVI)
        NDVI = (NIR - Red) / (NIR + Red)
        Range: [-1.0, 1.0]
        Indicates: Green biomass, chlorophyll concentration, photosynthetic activity.
        """
        nir = np.asarray(nir, dtype=np.float32)
        red = np.asarray(red, dtype=np.float32)
        denom = nir + red + eps
        val = (nir - red) / denom
        return np.clip(val, -1.0, 1.0)

    @staticmethod
    def ndre(nir: np.ndarray, red_edge: np.ndarray, eps: float = 1e-7) -> np.ndarray:
        """
        Normalized Difference Red Edge Index (NDRE)
        NDRE = (NIR - RedEdge) / (NIR + RedEdge)
        Range: [-1.0, 1.0]
        Indicates: Chlorophyll content in dense canopies and late growth stages.
        Crucial for early disease detection as Red-Edge reflects stress before visible yellowing.
        """
        nir = np.asarray(nir, dtype=np.float32)
        red_edge = np.asarray(red_edge, dtype=np.float32)
        denom = nir + red_edge + eps
        val = (nir - red_edge) / denom
        return np.clip(val, -1.0, 1.0)

    @staticmethod
    def evi(nir: np.ndarray, red: np.ndarray, blue: np.ndarray, eps: float = 1e-7) -> np.ndarray:
        """
        Enhanced Vegetation Index (EVI)
        EVI = 2.5 * (NIR - Red) / (NIR + 6*Red - 7.5*Blue + 1.0)
        Range: [-1.0, 1.0]
        Indicates: Canopy structural variation while minimizing atmospheric and canopy background noise.
        """
        nir = np.asarray(nir, dtype=np.float32)
        red = np.asarray(red, dtype=np.float32)
        blue = np.asarray(blue, dtype=np.float32)
        denom = nir + (6.0 * red) - (7.5 * blue) + 1.0 + eps
        val = 2.5 * (nir - red) / denom
        return np.clip(val, -1.0, 1.0)

    @staticmethod
    def ndwi(nir: np.ndarray, swir: np.ndarray, eps: float = 1e-7) -> np.ndarray:
        """
        Normalized Difference Water Index / Moisture Stress Index (NDWI)
        NDWI = (NIR - SWIR) / (NIR + SWIR)
        Range: [-1.0, 1.0]
        Indicates: Liquid water content in plant leaves and soil moisture status.
        """
        nir = np.asarray(nir, dtype=np.float32)
        swir = np.asarray(swir, dtype=np.float32)
        denom = nir + swir + eps
        val = (nir - swir) / denom
        return np.clip(val, -1.0, 1.0)

    @staticmethod
    def savi(nir: np.ndarray, red: np.ndarray, L: float = 0.5, eps: float = 1e-7) -> np.ndarray:
        """
        Soil-Adjusted Vegetation Index (SAVI)
        SAVI = ((NIR - Red) / (NIR + Red + L)) * (1.0 + L)
        Range: [-1.0, 1.0]
        Indicates: Vegetation vigor in sparse crops / early growth where soil reflectance interferes.
        """
        nir = np.asarray(nir, dtype=np.float32)
        red = np.asarray(red, dtype=np.float32)
        denom = nir + red + L + eps
        val = ((nir - red) / denom) * (1.0 + L)
        return np.clip(val, -1.0, 1.0)

    @staticmethod
    def vari(green: np.ndarray, red: np.ndarray, blue: np.ndarray, eps: float = 1e-7) -> np.ndarray:
        """
        Visual Atmospheric Resistance Index (VARI) - Visible RGB
        VARI = (Green - Red) / (Green + Red - Blue)
        Range: [-1.0, 1.0]
        Indicates: Vegetation fraction and canopy vigor from low-cost standard RGB drone cameras.
        """
        g = np.asarray(green, dtype=np.float32)
        r = np.asarray(red, dtype=np.float32)
        b = np.asarray(blue, dtype=np.float32)
        denom = g + r - b + eps
        val = (g - r) / denom
        return np.clip(val, -1.0, 1.0)

    @staticmethod
    def gli(green: np.ndarray, red: np.ndarray, blue: np.ndarray, eps: float = 1e-7) -> np.ndarray:
        """
        Green Leaf Index (GLI) - Visible RGB
        GLI = (2*Green - Red - Blue) / (2*Green + Red + Blue)
        Range: [-1.0, 1.0]
        Indicates: Leaf greenness, chlorophyll concentration and general plant vitality.
        """
        g = np.asarray(green, dtype=np.float32)
        r = np.asarray(red, dtype=np.float32)
        b = np.asarray(blue, dtype=np.float32)
        denom = (2.0 * g) + r + b + eps
        val = ((2.0 * g) - r - b) / denom
        return np.clip(val, -1.0, 1.0)

    @staticmethod
    def exg(green: np.ndarray, red: np.ndarray, blue: np.ndarray) -> np.ndarray:
        """
        Excess Green Index (ExG) - Visible RGB
        ExG = 2*Green - Red - Blue
        Normalized when RGB is [0, 1] or [0, 255].
        Indicates: Effective plant vs. bare soil / residue segmentation.
        """
        g = np.asarray(green, dtype=np.float32)
        r = np.asarray(red, dtype=np.float32)
        b = np.asarray(blue, dtype=np.float32)
        return (2.0 * g) - r - b

    @staticmethod
    def tgi(green: np.ndarray, red: np.ndarray, blue: np.ndarray, lambda_r: float = 670, lambda_g: float = 550, lambda_b: float = 480) -> np.ndarray:
        """
        Triangular Greenness Index (TGI) - Visible RGB
        TGI = -0.5 * [(lambda_r - lambda_b)*(r - g) - (lambda_r - lambda_g)*(r - b)]
        Indicates: Chlorophyll concentration in leaves and nitrogen status.
        """
        r = np.asarray(red, dtype=np.float32)
        g = np.asarray(green, dtype=np.float32)
        b = np.asarray(blue, dtype=np.float32)
        tgi_val = -0.5 * ((lambda_r - lambda_b) * (r - g) - (lambda_r - lambda_g) * (r - b))
        return tgi_val

    @classmethod
    def compute_all_satellite(cls, bands: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        """
        Computes all standard satellite indices from a dictionary of Sentinel-2 band arrays.
        Expected band keys: 'B02' (Blue), 'B03' (Green), 'B04' (Red), 'B05' (RedEdge), 'B08' (NIR), 'B11' (SWIR).
        """
        res = {}
        if 'B08' in bands and 'B04' in bands:
            res['ndvi'] = cls.ndvi(bands['B08'], bands['B04'])
            res['savi'] = cls.savi(bands['B08'], bands['B04'])
        if 'B08' in bands and 'B05' in bands:
            res['ndre'] = cls.ndre(bands['B08'], bands['B05'])
        if 'B08' in bands and 'B04' in bands and 'B02' in bands:
            res['evi'] = cls.evi(bands['B08'], bands['B04'], bands['B02'])
        if 'B08' in bands and 'B11' in bands:
            res['ndwi'] = cls.ndwi(bands['B08'], bands['B11'])
        return res

    @classmethod
    def compute_all_drone_rgb(cls, rgb_image: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Computes all visible indices for a 3-channel RGB image (Height, Width, 3) normalized in [0, 1].
        """
        if rgb_image.ndim != 3 or rgb_image.shape[2] < 3:
            raise ValueError("RGB image must be 3D with 3 channels (R, G, B)")
        
        img = rgb_image.astype(np.float32)
        if img.max() > 1.0:
            img = img / 255.0
            
        r = img[:, :, 0]
        g = img[:, :, 1]
        b = img[:, :, 2]
        
        return {
            'vari': cls.vari(g, r, b),
            'gli': cls.gli(g, r, b),
            'exg': cls.exg(g, r, b),
            'tgi': cls.tgi(g, r, b)
        }
