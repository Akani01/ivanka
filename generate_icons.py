import os
import shutil
from PIL import Image, ImageDraw, ImageFont

# ── Where to write icons ──
OUTPUT_DIRS = [
    'store/static/store',          # ◀ NEW — matches what the error asks for
    'hiring/static/hiring/icons',  # keep for the hiring app / existing references
]

# ── Ivanka brand colours (matches the template CSS) ──
BRAND_BG   = '#0A0A0A'   # --ink
BRAND_FG   = '#FFFFFF'
MASK_BG    = '#0A0A0A'   # maskable: same ink, full bleed
MASK_FG    = '#FFFFFF'

SIZES = [72, 96, 128, 144, 152, 192, 384, 512]


def _font(size):
    candidates = [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        '/System/Library/Fonts/Supplemental/Arial Bold.ttf',
        'C:\\Windows\\Fonts\\arialbd.ttf',
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _draw_icon(size, bg, fg, maskable=False):
    img  = Image.new('RGB', (size, size), color=bg)
    draw = ImageDraw.Draw(img)

    # Maskable icons need extra safe-zone padding (40% of size = safe area)
    pad = int(size * 0.20) if maskable else int(size * 0.08)

    # Rounded square inner mark (matches the .iv-brand-mark in the template)
    radius = max(4, size // 8)
    draw.rounded_rectangle(
        [(pad, pad), (size - pad, size - pad)],
        radius=radius,
        fill=fg if not maskable else '#FFFFFF',
    )

    # "I" letter on top of the mark — brand initial
    text = 'I'
    font = _font(int(size * 0.42))
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (size - tw) // 2 - bbox[0]
    y = (size - th) // 2 - bbox[1]
    draw.text((x, y), text, fill=bg, font=font)

    return img


def generate_icons():
    for out_dir in OUTPUT_DIRS:
        os.makedirs(out_dir, exist_ok=True)

        for size in SIZES:
            # Any-purpose icon
            _draw_icon(size, BRAND_BG, BRAND_FG, maskable=False).save(
                os.path.join(out_dir, f'icon-{size}.png'), 'PNG'
            )
            print(f'✅ {out_dir}/icon-{size}.png')

            # Maskable icon (for the `purpose: maskable` entries in settings)
            _draw_icon(size, MASK_BG, MASK_FG, maskable=True).save(
                os.path.join(out_dir, f'icon-{size}-maskable.png'), 'PNG'
            )
            print(f'✅ {out_dir}/icon-{size}-maskable.png')

        # Badge + shortcut icons (small, reused)
        _draw_icon(72, BRAND_BG, BRAND_FG).save(
            os.path.join(out_dir, 'icon-72x72.png'), 'PNG'
        )
        for name in ('shortcut-shop', 'shortcut-cart', 'shortcut-orders', 'shortcut-jobs'):
            _draw_icon(96, BRAND_BG, BRAND_FG).save(
                os.path.join(out_dir, f'{name}.png'), 'PNG'
            )
        print(f'✅ badge + shortcuts in {out_dir}')

    print('\n🎉 All icons generated.')


if __name__ == '__main__':
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        import subprocess
        subprocess.check_call(['pip', 'install', 'Pillow'])
        from PIL import Image, ImageDraw, ImageFont
    generate_icons()