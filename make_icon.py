from PIL import Image, ImageDraw

size = 512
img = Image.new("RGBA", (size, size), (13, 110, 253, 255))
draw = ImageDraw.Draw(img)

cx, cy = size // 2, size // 2
w, h = 260, 200
x0, y0 = cx - w // 2, cy - h // 2 + 20
draw.rounded_rectangle([x0, y0, x0 + w, y0 + h], radius=24, fill="white")
draw.rounded_rectangle([cx - 70, y0 - 40, cx + 70, y0 + 10], radius=14, outline="white", width=18)
draw.rectangle([cx - 20, cy - 10, cx + 20, cy + 30], fill=(13, 110, 253, 255))

img.save("hiring/static/hiring/icons/shortcut-jobs.png")
print("saved -> hiring/static/hiring/icons/shortcut-jobs.png")
