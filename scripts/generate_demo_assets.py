"""Regenerate the embedded design frames and Inter glyphs from repo-local inputs."""

import argparse
import io
import itertools
import tempfile
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).resolve().parents[1]


def generate(output):
    (output / "docs/design").mkdir(parents=True, exist_ok=True)
    (output / "firmware/src").mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(root / "docs/design/netlink-bedienpaneel.pdf")
    if len(doc) != 17:
        raise ValueError("This renderer expects exactly 17 design pages")
    out = [
        "// Generated from the supplied design. Regenerate with scripts/generate_demo_assets.py.",
        '#include "demo_assets.h"',
    ]
    header = [
        "#pragma once",
        "#include <stdint.h>",
        "#include <stddef.h>",
        "struct DemoGlyph { uint32_t offset; uint16_t width,height; int16_t x,y,advance; };",
        "struct DemoFont { const uint8_t *pixels; const DemoGlyph *glyphs; int size; };",
        "extern const uint16_t *const demoFrames[17];",
        "extern const uint32_t demoFrameWords[17];",
        "extern const DemoFont demoFonts[11];",
    ]
    wordcounts = []
    for n, page in enumerate(doc):
        im = (
            Image.open(io.BytesIO(doc.extract_image(page.get_images()[0][0])["image"]))
            .convert("RGB")
            .resize((640, 180), Image.Resampling.LANCZOS)
        )
        im.save(output / f"docs/design/reference-{n + 1:02}.png")
        im = im.quantize(
            colors=256 if n in (3, 12, 13, 14, 15) else 64, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE
        ).convert("RGB")
        pixels = [((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3) for r, g, b in im.getdata()]
        rle = []
        for value, items in itertools.groupby(pixels):
            count = sum(1 for _ in items)
            while count:
                step = min(count, 65535)
                rle.extend((step, value))
                count -= step
        wordcounts.append(len(rle))
        out.append(f"static const uint16_t frame{n}[] = {{" + ",".join(map(str, rle)) + "};")
    fonts = [
        (12, 650),
        (12, 550),
        (16, 600),
        (20, 550),
        (24, 400),
        (36, 400),
        (56, 300),
        (60, 300),
        (72, 300),
        (44, 300),
        (26, 400),
    ]
    for i, (size, weight) in enumerate(fonts):
        font = ImageFont.truetype(root / "preview/assets/inter.ttf", size, layout_engine=ImageFont.Layout.BASIC)
        font.set_variation_by_axes([14, weight])
        alphas = []
        glyphs = []
        for code in range(32, 127):
            c = chr(code)
            x0, y0, x1, y1 = font.getbbox(c, anchor="ls")
            w, h = x1 - x0, y1 - y0
            image = Image.new("L", (max(1, w), max(1, h)))
            ImageDraw.Draw(image).text((-x0, -y0), c, font=font, fill=255, anchor="ls")
            values = [round(v / 17) for v in image.getdata()] if w * h else []
            glyphs.append((len(alphas), w, h, x0, y0, round(font.getlength(c) * 16)))
            for k in range(0, len(values), 2):
                alphas.append((values[k] << 4) | (values[k + 1] if k + 1 < len(values) else 0))
        out.append(f"static const uint8_t fontPixels{i}[] = {{" + ",".join(map(str, alphas)) + "};")
        out.append(
            f"static const DemoGlyph fontGlyphs{i}[] = {{"
            + ",".join("{" + ",".join(map(str, g)) + "}" for g in glyphs)
            + "};"
        )
    out += [
        "const uint16_t *const demoFrames[17] = {" + ",".join(f"frame{i}" for i in range(17)) + "};",
        "const uint32_t demoFrameWords[17] = {" + ",".join(map(str, wordcounts)) + "};",
        "const DemoFont demoFonts[11] = {"
        + ",".join("{fontPixels%d,fontGlyphs%d,%d}" % (i, i, s) for i, (s, w) in enumerate(fonts))
        + "};",
    ]
    (output / "firmware/src/demo_assets.h").write_text("\n".join(header) + "\n")
    (output / "firmware/src/demo_assets.cpp").write_text("\n".join(out) + "\n")
    print("RLE frame bytes", sum(wordcounts) * 2, "source size", sum(len(line) for line in out))


def same_asset(generated, committed):
    if not committed.exists():
        return False
    if generated.suffix == ".png":
        # PNG compression/metadata differ between zlib builds. Compare exactly
        # the RGBA pixels consumed by visual QA, not platform-specific encoding.
        with Image.open(generated) as left, Image.open(committed) as right:
            return left.size == right.size and left.convert("RGBA").tobytes() == right.convert("RGBA").tobytes()
    return generated.read_bytes() == committed.read_bytes()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Compare regenerated files without modifying the checkout")
    args = parser.parse_args()
    if not args.check:
        generate(root)
        return
    with tempfile.TemporaryDirectory() as temp:
        generated = Path(temp)
        generate(generated)
        changed = [
            str(path.relative_to(generated))
            for path in generated.rglob("*")
            if path.is_file() and not same_asset(path, root / path.relative_to(generated))
        ]
        if changed:
            raise SystemExit("Generated assets differ: " + ", ".join(sorted(changed)))
    print("Generated assets match the committed PDF/font inputs")


if __name__ == "__main__":
    main()
