"""draws the welcome / goodbye card for the join log."""
import io, math, os
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
A = lambda f: os.path.join(HERE, "assets", f)
W, H = 1100, 440
BLUE = (40, 136, 208)
LIGHT = (90, 190, 245)
RED = (231, 76, 60)


def _font(name, size):
    return ImageFont.truetype(A(name), size)


def _background(accent):
    bg = Image.new("RGB", (W, H), (10, 14, 24))
    d = ImageDraw.Draw(bg)
    cx, cy = W // 2, H // 2 - 30
    # soft rays like the logo
    rays = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    rd = ImageDraw.Draw(rays)
    for i in range(36):
        a0 = i * (2 * math.pi / 36)
        a1 = a0 + math.pi / 60
        r = 900
        rd.polygon([(cx, cy), (cx + r * math.cos(a0), cy + r * math.sin(a0)),
                    (cx + r * math.cos(a1), cy + r * math.sin(a1))], fill=accent + (28,))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((cx - 260, cy - 200, cx + 260, cy + 200), fill=accent + (90,))
    glow = glow.filter(ImageFilter.GaussianBlur(90))
    bg = Image.alpha_composite(bg.convert("RGBA"), rays)
    bg = Image.alpha_composite(bg, glow)
    # vignette
    vig = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vig).rectangle((0, 0, W, H), fill=0)
    edge = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ed = ImageDraw.Draw(edge)
    for i in range(60):
        ed.rectangle((i, i, W - i, H - i), outline=(0, 0, 0, int(140 * (1 - i / 60))))
    bg = Image.alpha_composite(bg, edge)
    return bg


def _circle(img, size, ring):
    img = img.convert("RGBA").resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size * 4, size * 4), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size * 4, size * 4), fill=255)
    mask = mask.resize((size, size), Image.LANCZOS)
    out = Image.new("RGBA", (size + 16, size + 16), (0, 0, 0, 0))
    rmask = Image.new("L", ((size + 16) * 4,) * 2, 0)
    ImageDraw.Draw(rmask).ellipse((0, 0, (size + 16) * 4, (size + 16) * 4), fill=255)
    out.paste(Image.new("RGBA", out.size, ring + (255,)), (0, 0), rmask.resize(out.size, Image.LANCZOS))
    out.paste(img, (8, 8), mask)
    return out


def _fit(draw, text, font_name, size, max_w):
    while size > 18:
        f = _font(font_name, size)
        if draw.textlength(text, font=f) <= max_w:
            return f
        size -= 2
    return _font(font_name, size)


def card(kind, avatar_bytes, display_name, username, member_no):
    """kind: 'join' or 'leave'. returns png bytes."""
    accent = BLUE if kind == "join" else RED
    img = _background(accent)
    d = ImageDraw.Draw(img)

    av = Image.open(io.BytesIO(avatar_bytes)) if avatar_bytes else Image.open(A("logo.png"))
    a = _circle(av, 170, LIGHT if kind == "join" else (255, 140, 120))
    img.alpha_composite(a, ((W - a.width) // 2, 34))

    title = "WELCOME" if kind == "join" else "GOODBYE"
    tf = _font("InterDisplay-Black.otf", 92)
    tw = d.textlength(title, font=tf)
    ty = 222
    d.text(((W - tw) / 2 + 4, ty + 5), title, font=tf, fill=(0, 0, 0, 160))
    d.text(((W - tw) / 2, ty), title, font=tf, fill=(255, 255, 255))

    nf = _fit(d, display_name, "Poppins-Bold.ttf", 40, W - 300)
    nw = d.textlength(display_name, font=nf)
    d.text(((W - nw) / 2, 330), display_name, font=nf, fill=LIGHT if kind == "join" else (255, 170, 160))

    sub = (f"member #{member_no} of PureLogic Community" if kind == "join"
           else f"@{username} left PureLogic Community")
    sf = _fit(d, sub, "Poppins-Medium.ttf", 24, W - 300)
    sw = d.textlength(sub, font=sf)
    d.text(((W - sw) / 2, 384), sub, font=sf, fill=(200, 210, 225))

    logo = Image.open(A("logo.png")).convert("RGBA")
    img.alpha_composite(_circle(logo, 74, accent), (W - 112, H - 112))

    out = io.BytesIO()
    img.convert("RGB").save(out, "PNG", optimize=True)
    return out.getvalue()


if __name__ == "__main__":
    import sys
    av = open(A("logo.png"), "rb").read()
    open(sys.argv[1], "wb").write(card("join", av, "Evil Dao", "evil_dao", 19))
    open(sys.argv[2], "wb").write(card("leave", None, "powerful_lamb", "powerful_lamb_98010", 18))
