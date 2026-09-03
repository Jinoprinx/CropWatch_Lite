"""
Generates synthetic high-resolution sample leaf images with realistic pathological lesion patterns
and drone canopy orthomosaic tiles for immediate testing and demonstration.
"""

import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

def create_leaf_sample(output_path: str, disease_type: str = "tomato_early_blight"):
    width, height = 512, 512
    # Create background (clean lab neutral grey/white)
    img = Image.new("RGB", (width, height), color=(240, 242, 240))
    draw = ImageDraw.Draw(img)

    # Draw main leaf blade outline (elliptical polygon)
    center_x, center_y = width // 2, height // 2
    
    # Generate leaf base shape
    points = []
    num_pts = 60
    for i in range(num_pts):
        angle = (2 * np.pi * i) / num_pts
        # Leaf contour equation: r = a * (1 - sin(t)) or elongated ellipse
        r_x = 160 * np.sin(angle) + 18 * np.sin(4 * angle)
        r_y = 230 * np.cos(angle)
        # Taper tip at top
        if r_y < 0:
            r_x *= (1.0 + r_y / 300.0)
        points.append((center_x + r_x, center_y + r_y))

    # Base leaf green color with organic shading
    leaf_green = (46, 139, 45) if disease_type != "healthy_crop" else (34, 160, 48)
    draw.polygon(points, fill=leaf_green, outline=(30, 95, 30))

    # Add leaf veins
    draw.line([(center_x, center_y - 210), (center_x, center_y + 215)], fill=(65, 175, 60), width=4)
    for y_offset in range(-160, 180, 35):
        draw.line([(center_x, center_y + y_offset), (center_x - 110, center_y + y_offset - 25)], fill=(60, 160, 55), width=2)
        draw.line([(center_x, center_y + y_offset), (center_x + 110, center_y + y_offset - 25)], fill=(60, 160, 55), width=2)

    # Convert to array to inject organic noise & pathology lesions
    np_img = np.array(img).astype(np.float32)
    # Add subtle natural texture
    texture = np.random.normal(0, 7.0, (height, width, 3))
    np_img = np.clip(np_img + texture, 0, 255).astype(np.uint8)
    img = Image.fromarray(np_img)
    draw = ImageDraw.Draw(img)

    if disease_type == "tomato_early_blight":
        # Concentric dark brown target spots with chlorotic yellow halo
        spots = [(center_x - 45, center_y - 60, 38), (center_x + 55, center_y + 40, 44), (center_x - 30, center_y + 80, 30), (center_x + 35, center_y - 120, 26)]
        for sx, sy, rad in spots:
            # Yellow chlorotic halo
            draw.ellipse([sx - rad - 12, sy - rad - 12, sx + rad + 12, sy + rad + 12], fill=(195, 180, 30))
            # Dark necrotic target rings
            draw.ellipse([sx - rad, sy - rad, sx + rad, sy + rad], fill=(85, 48, 20))
            draw.ellipse([sx - rad + 8, sy - rad + 8, sx + rad - 8, sy + rad - 8], fill=(120, 70, 30))
            draw.ellipse([sx - rad + 16, sy - rad + 16, sx + rad - 16, sy + rad - 16], fill=(65, 35, 15))

    elif disease_type == "corn_northern_leaf_blight":
        # Cigar-shaped elongated tan/gray lesions
        lesions = [(center_x - 40, center_y - 90, 80, 22), (center_x + 30, center_y + 20, 95, 26), (center_x - 20, center_y + 110, 70, 20)]
        for lx, ly, l_len, l_w in lesions:
            draw.ellipse([lx - l_w, ly - l_len//2, lx + l_w, ly + l_len//2], fill=(160, 140, 95), outline=(105, 85, 50))
            draw.ellipse([lx - l_w//2, ly - l_len//3, lx + l_w//2, ly + l_len//3], fill=(130, 110, 70))

    elif disease_type == "corn_common_rust" or disease_type == "wheat_yellow_rust":
        # Cinnamon-brown powdery rust pustules
        np.random.seed(99)
        for _ in range(85):
            px = center_x + int(np.random.normal(0, 55))
            py = center_y + int(np.random.normal(0, 120))
            prad = np.random.randint(3, 7)
            draw.ellipse([px - prad, py - prad, px + prad, py + prad], fill=(185, 75, 20), outline=(215, 115, 30))

    elif disease_type == "potato_late_blight":
        # Large irregular water-soaked blackened lesions
        spots = [(center_x - 35, center_y - 40, 55), (center_x + 40, center_y + 60, 65)]
        for sx, sy, rad in spots:
            draw.ellipse([sx - rad - 10, sy - rad - 10, sx + rad + 10, sy + rad + 10], fill=(140, 150, 60))
            draw.ellipse([sx - rad, sy - rad, sx + rad, sy + rad], fill=(45, 38, 30))

    # Soften lesion transitions
    img = img.filter(ImageFilter.SMOOTH_MORE)
    img.save(output_path, quality=92)
    print(f"Generated sample leaf: {output_path}")

def create_drone_canopy_sample(output_path: str):
    width, height = 640, 640
    # Create farm soil baseline
    soil = np.random.normal(120, 15, (height, width, 3))
    soil[:, :, 0] += 30 # reddish-brown
    soil[:, :, 1] += 10
    soil[:, :, 2] -= 25
    soil = np.clip(soil, 40, 200).astype(np.uint8)
    img = Image.fromarray(soil)
    draw = ImageDraw.Draw(img)

    # Draw crop rows (parallel emerald green hedgerows)
    for row_x in range(40, width, 65):
        for y in range(0, height, 8):
            crop_radius = np.random.randint(18, 26)
            jitter_x = row_x + np.random.randint(-4, 5)
            # Inject disease stress in top-right quadrant
            is_stressed = (jitter_x > width * 0.55) and (y < height * 0.45)
            if is_stressed:
                fill_color = (175, 160, 45) if np.random.rand() > 0.4 else (135, 75, 35) # yellowing / rust
            else:
                fill_color = (35 + np.random.randint(-5, 10), 155 + np.random.randint(-15, 15), 45) # lush green
            draw.ellipse([jitter_x - crop_radius, y - crop_radius, jitter_x + crop_radius, y + crop_radius], fill=fill_color)

    img = img.filter(ImageFilter.GaussianBlur(1.2))
    img.save(output_path, quality=90)
    print(f"Generated sample drone canopy: {output_path}")

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    leaf_dir = os.path.join(base_dir, "sample_leaves")
    drone_dir = os.path.join(base_dir, "sample_drone")
    os.makedirs(leaf_dir, exist_ok=True)
    os.makedirs(drone_dir, exist_ok=True)

    create_leaf_sample(os.path.join(leaf_dir, "tomato_early_blight.jpg"), "tomato_early_blight")
    create_leaf_sample(os.path.join(leaf_dir, "corn_northern_leaf_blight.jpg"), "corn_northern_leaf_blight")
    create_leaf_sample(os.path.join(leaf_dir, "corn_common_rust.jpg"), "corn_common_rust")
    create_leaf_sample(os.path.join(leaf_dir, "potato_late_blight.jpg"), "potato_late_blight")
    create_leaf_sample(os.path.join(leaf_dir, "healthy_corn_leaf.jpg"), "healthy_crop")
    create_drone_canopy_sample(os.path.join(drone_dir, "drone_crop_canopy_ortho.jpg"))
