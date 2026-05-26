"""Generate PWA icons for TradingAI Pro"""
from PIL import Image, ImageDraw
import os

# Create icons directory
icons_dir = 'src/api/static/icons'
os.makedirs(icons_dir, exist_ok=True)

# Icon sizes
sizes = [72, 96, 128, 144, 152, 192, 384, 512]

for size in sizes:
    # Create image
    img = Image.new('RGBA', (size, size), (26, 26, 46, 255))
    draw = ImageDraw.Draw(img)
    
    # Draw rounded rectangle background
    margin = size // 10
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=size // 5,
        fill=(15, 52, 96, 255)
    )
    
    # Draw chart line
    points = [
        (size * 0.2, size * 0.7),
        (size * 0.35, size * 0.55),
        (size * 0.5, size * 0.65),
        (size * 0.65, size * 0.4),
        (size * 0.8, size * 0.3)
    ]
    
    line_width = max(2, size // 30)
    for i in range(len(points) - 1):
        draw.line([points[i], points[i+1]], fill=(0, 212, 170, 255), width=line_width)
    
    # Draw dots
    dot_radius = max(2, size // 40)
    for point in points:
        draw.ellipse(
            [point[0] - dot_radius, point[1] - dot_radius,
             point[0] + dot_radius, point[1] + dot_radius],
            fill=(0, 212, 170, 255)
        )
    
    # Save
    img.save(f'{icons_dir}/icon-{size}x{size}.png', 'PNG')
    print(f'✅ Created icon-{size}x{size}.png')

print('\n✅ All PWA icons created!')
