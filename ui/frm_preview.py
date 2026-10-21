"""Draws a schematic preview of VB6 forms (position, size, caption of the controls).

Usage:  python3 frm_preview.py form.frm [more.frm ...] [--out FOLDER]
The preview shows how the dimensions are laid out after the conversion (1 pixel = 15 twips). It does not replace a view in Qt,
but serves to check the translation against the view in the VB6 IDE. Invisible controls are dashed.
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

from frmparse import Control, form_client_px, geometry_px, parse_frm, vb_color_rgb as vb_color

try:
    FONT = ImageFont.truetype("DejaVuSans.ttf", 11)
except OSError:
    FONT = ImageFont.load_default()

SKIP = ("VB.Menu", "VB.Timer", "MediaMaker.ShellPipe")
MENU_H = 20


def label_of(c: Control) -> str:
    text = c.get("Caption") or c.get("Text") or ""
    if isinstance(text, str):
        text = text.replace("&", "")
    name = c.name + (f"({c.index})" if c.index is not None else "")
    return text if text and c.type in ("VB.CommandButton", "VB.Label", "VB.Frame", "VB.CheckBox", "VB.OptionButton") else name + (f": {text}" if text else "")


def dashed(d: ImageDraw.ImageDraw, box, color):
    x0, y0, x1, y1 = box
    for x in range(x0, x1, 6):
        d.line([(x, y0), (min(x + 3, x1), y0)], fill=color)
        d.line([(x, y1), (min(x + 3, x1), y1)], fill=color)
    for y in range(y0, y1, 6):
        d.line([(x0, y), (x0, min(y + 3, y1))], fill=color)
        d.line([(x1, y), (x1, min(y + 3, y1))], fill=color)


def draw(d, c: Control, ox: int, oy: int):
    for ch in reversed(c.children):                 # in the .frm the topmost control comes first
        if ch.type in SKIP:
            continue
        x, y, w, h = geometry_px(ch)
        x0, y0 = ox + x, oy + y
        box = (x0, y0, x0 + max(w, 1) - 1, y0 + max(h, 1) - 1)
        visible = ch.flag("Visible", True)
        t = ch.type
        line = (150, 150, 150) if not visible else (60, 60, 60)
        fill, text_color = None, (0, 0, 0) if visible else (150, 150, 150)
        if t == "VB.CommandButton":
            fill = (225, 225, 225)
        elif t in ("VB.TextBox", "VB.ComboBox", "MSComctlLib.ListView"):
            fill = (255, 255, 255)
        elif t == "VB.PictureBox":
            fill = vb_color(ch.get("BackColor"), (235, 235, 235))
        elif t == "VB.Label":
            fill = vb_color(ch.get("BackColor")) if ch.get("BackStyle", "1") == "1" else None
            line = None if ch.get("BorderStyle", "0") == "0" else line
        elif t == "VB.Frame":
            fill = vb_color(ch.get("BackColor")) if ch.get("BorderStyle", "1") == "0" else None
        d.rectangle(box, fill=fill, outline=line) if visible or t != "VB.Frame" else None
        if not visible:
            dashed(d, box, (170, 170, 170))
        if t == "MSComctlLib.ListView":
            d.rectangle((box[0], box[1], box[2], box[1] + 16), fill=(225, 225, 225), outline=line)
        if t == "MSComctlLib.TabStrip":
            d.rectangle((box[0], box[1], box[2], box[1] + 20), fill=(235, 235, 235), outline=line)
        if t in ("VB.VScrollBar", "VB.HScrollBar", "MSComctlLib.Slider"):
            d.rectangle(box, fill=(210, 225, 245), outline=line)
        d.text((x0 + 3, y0 + 1), label_of(ch), fill=text_color, font=FONT)
        draw(d, ch, x0, y0)


def render(path: str, out_dir: str) -> str:
    form = parse_frm(path)
    w, h = form_client_px(form)
    menus = [c for c in form.root.children if c.type == "VB.Menu" and c.flag("Visible", True)]
    top = MENU_H if menus else 0
    img = Image.new("RGB", (w, h + top), (240, 240, 240))
    d = ImageDraw.Draw(img)
    if menus:
        d.rectangle((0, 0, w, MENU_H - 1), fill=(250, 250, 250), outline=(200, 200, 200))
        x = 6
        for m in menus:
            cap = str(m.get("Caption", m.name)).replace("&", "")
            d.text((x, 4), cap, fill=(0, 0, 0), font=FONT)
            x += int(d.textlength(cap, font=FONT)) + 14
    draw_root = Control("root", "root", {}, {}, form.root.children, None)
    draw_root.props = {}
    # children belong to the form; coordinates relative to the client area
    for ch in form.root.children:
        pass
    sub = Image.new("RGB", (w, h), (240, 240, 240))
    sd = ImageDraw.Draw(sub)
    draw(sd, form.root, 0, 0)
    img.paste(sub, (0, top))
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, os.path.splitext(os.path.basename(path))[0] + ".png")
    img.save(out)
    return out


def main():
    files = [a for a in sys.argv[1:] if not a.startswith("--") and sys.argv[sys.argv.index(a) - 1] != "--out"]
    out_dir = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "preview"
    if not files:
        sys.exit(__doc__)
    for f in files:
        print(render(f, out_dir))


if __name__ == "__main__":
    main()
