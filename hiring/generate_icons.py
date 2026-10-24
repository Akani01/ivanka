
import os
from django.core.management.base import BaseCommand, CommandError
from PIL import Image

SIZES = [72, 96, 128, 144, 152, 192, 384, 512]
DEFAULT_OUTPUT = os.path.join("static", "hiring", "icons")
DEFAULT_COLOR = "#0d823c"
MASKABLE_SAFE_SCALE = 0.80  # keep content inside the 80% "safe zone"


def hex_to_rgb(hex_color: str):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


class Command(BaseCommand):
    help = "Generate the full PWA icon set (all manifest sizes, any + maskable) from a master logo."

    def add_arguments(self, parser):
        parser.add_argument("master_logo", type=str, help="Path to the master logo image (square, full-bleed).")
        parser.add_argument("--output", type=str, default=DEFAULT_OUTPUT, help="Output folder for generated icons.")
        parser.add_argument("--color", type=str, default=DEFAULT_COLOR, help="Hex background color for maskable padding.")

    def handle(self, *args, **options):
        src_path = options["master_logo"]
        output_dir = options["output"]
        bg_color = hex_to_rgb(options["color"])

        if not os.path.isfile(src_path):
            raise CommandError(f"Master logo not found: {src_path}")

        os.makedirs(output_dir, exist_ok=True)

        master = Image.open(src_path).convert("RGB")
        if master.width != master.height:
            self.stdout.write(self.style.WARNING(
                f"Warning: master logo is {master.width}x{master.height}, not square. "
                "It will be stretched to fit — consider cropping to 1:1 first."
            ))
        if master.width < 512:
            self.stdout.write(self.style.WARNING(
                f"Warning: master logo is only {master.width}px wide. "
                "Icons above this size will be upscaled and may look soft."
            ))

        for size in SIZES:
            any_icon = master.resize((size, size), Image.LANCZOS)
            any_icon.save(os.path.join(output_dir, f"icon-{size}.png"))

            inner = int(size * MASKABLE_SAFE_SCALE)
            inner_icon = master.resize((inner, inner), Image.LANCZOS)
            canvas = Image.new("RGB", (size, size), bg_color)
            offset = ((size - inner) // 2, (size - inner) // 2)
            canvas.paste(inner_icon, offset)
            canvas.save(os.path.join(output_dir, f"icon-{size}-maskable.png"))

            self.stdout.write(f"  wrote icon-{size}.png + icon-{size}-maskable.png")

        favicon_sizes = [16, 32, 48]
        favicon_imgs = [master.resize((s, s), Image.LANCZOS) for s in favicon_sizes]
        favicon_imgs[0].save(
            os.path.join(output_dir, "favicon.ico"),
            format="ICO",
            sizes=[(s, s) for s in favicon_sizes],
        )
        self.stdout.write("  wrote favicon.ico")

        master.resize((180, 180), Image.LANCZOS).save(
            os.path.join(output_dir, "apple-touch-icon.png")
        )
        self.stdout.write("  wrote apple-touch-icon.png")

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. {len(SIZES) * 2 + 2} files written to {output_dir}/"
        ))