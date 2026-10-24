import os
from PIL import Image, ImageDraw

def generate_icons():
    """Generate simple PWA icons"""
    sizes = [72, 96, 128, 144, 152, 192, 384, 512]
    output_dir = 'hiring/static/hiring/icons'
    
    os.makedirs(output_dir, exist_ok=True)
    
    for size in sizes:
        # Create a red square with "T" logo
        img = Image.new('RGB', (size, size), color='#c62828')
        draw = ImageDraw.Draw(img)
        
        # Draw border
        border = size // 20
        draw.rectangle(
            [(border, border), (size - border, size - border)],
            outline='white',
            width=border
        )
        
        # Add "T" text
        text = 'T'
        font_size = size // 2
        # Use default font
        try:
            from PIL import ImageFont
            font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', font_size)
        except:
            font = ImageFont.load_default()
        
        # Center text
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (size - text_width) // 2
        y = (size - text_height) // 2
        
        draw.text((x, y), text, fill='white', font=font)
        
        # Save
        output_path = os.path.join(output_dir, f'icon-{size}.png')
        img.save(output_path, 'PNG')
        print(f'✅ Generated: {output_path}')
    
    # Also create badge icon (72x72)
    badge_path = os.path.join(output_dir, 'icon-72x72.png')
    if not os.path.exists(badge_path):
        # Copy the 72px icon
        import shutil
        shutil.copy(os.path.join(output_dir, 'icon-72.png'), badge_path)
        print(f'✅ Created badge: {badge_path}')
    
    print('\n🎉 All icons generated!')

if __name__ == '__main__':
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print('📦 Installing Pillow...')
        import subprocess
        subprocess.check_call(['pip', 'install', 'Pillow'])
        from PIL import Image, ImageDraw, ImageFont
    
    generate_icons()
