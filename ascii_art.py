#!/usr/bin/env python3
"""Convert images and videos to ASCII art rendered in the terminal."""

import argparse
import os
import shutil
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Paul Bourke's 70-level ramp, reversed to go dark -> light so idx 0 = darkest.
_BOURKE_70 = " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"

CHARSETS = {
    "default": _BOURKE_70[::-1],
    "classic": "@%#*+=-:. ",
    "blocks":  "\u2588\u2593\u2592\u2591 ",
    "simple":  "#. ",
}

CHAR_ASPECT = 2.0

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    "C:/Windows/Fonts/consola.ttf",
]


def enable_ansi_on_windows():
    if os.name == "nt":
        os.system("")


def compute_size(src_h, src_w, target_cols):
    cols = max(1, target_cols)
    rows = max(1, int(src_h / src_w * cols / CHAR_ASPECT))
    return rows, cols


def frame_to_ascii(frame_bgr, target_cols, ramp):
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    rows, cols = compute_size(gray.shape[0], gray.shape[1], target_cols)
    resized = cv2.resize(gray, (cols, rows), interpolation=cv2.INTER_AREA)
    idx = (resized.astype(np.int32) * len(ramp) // 256).clip(0, len(ramp) - 1)
    ramp_arr = np.array(list(ramp))
    lines = ["".join(ramp_arr[row]) for row in idx]
    return "\n".join(lines)


def frame_to_halfblock(frame_bgr, target_cols):
    """Render using Unicode half-blocks: each char cell encodes 2 vertical pixels.

    Binary (on/off) per sub-pixel — no grayscale, but vertical resolution
    is doubled compared to single-char-per-pixel mode.
    """
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    src_h, src_w = gray.shape
    cols = max(1, target_cols)
    # In half-block mode each char = 1 horizontal px and 2 vertical px.
    # Char aspect ~2:1 (tall:wide) makes 2 vertical px visually ~ 1 horizontal px,
    # so sampling is effectively square — do NOT divide by CHAR_ASPECT here.
    rows = max(2, int(src_h / src_w * cols))
    if rows % 2:
        rows += 1
    resized = cv2.resize(gray, (cols, rows), interpolation=cv2.INTER_AREA)
    mask = resized >= 128
    top = mask[0::2]
    bottom = mask[1::2]
    chars = np.full(top.shape, " ", dtype="<U1")
    chars[top & ~bottom] = "\u2580"   # ▀ upper half
    chars[~top & bottom] = "\u2584"   # ▄ lower half
    chars[top & bottom] = "\u2588"    # █ full block
    return "\n".join("".join(r) for r in chars)


def resolve_target_width(user_width):
    if user_width is not None:
        return user_width
    return shutil.get_terminal_size((80, 24)).columns


def load_mono_font(size=14):
    for path in FONT_CANDIDATES:
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def render_png(ascii_text, out_path):
    font = load_mono_font(14)
    lines = ascii_text.split("\n") or [""]

    bbox = font.getbbox("M")
    cw = max(1, bbox[2] - bbox[0])
    ch = max(1, bbox[3] - bbox[1])
    line_h = int(ch * 1.25)

    max_len = max((len(l) for l in lines), default=1)
    pad = 6
    width = max_len * cw + pad * 2
    height = line_h * len(lines) + pad * 2

    img = Image.new("L", (width, height), 255)
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        draw.text((pad, pad + i * line_h), line, fill=0, font=font)

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)


def render_frame(frame_bgr, cols, charset, halfblock):
    if halfblock:
        return frame_to_halfblock(frame_bgr, cols)
    return frame_to_ascii(frame_bgr, cols, CHARSETS[charset])


def run_image(path, width, charset, output, halfblock):
    img = cv2.imread(path)
    if img is None:
        print(f"Error: cannot read image '{path}'", file=sys.stderr)
        sys.exit(1)
    cols = resolve_target_width(width)
    ascii_text = render_frame(img, cols, charset, halfblock)
    print(ascii_text)
    if output:
        render_png(ascii_text, output)
        print(f"\n[saved PNG -> {output}]", file=sys.stderr)


def run_video(path, width, charset, halfblock):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        print(f"Error: cannot open video '{path}'", file=sys.stderr)
        sys.exit(1)

    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    frame_delay = 1.0 / fps
    cols = resolve_target_width(width)

    sys.stdout.write("\033[2J")
    sys.stdout.flush()
    try:
        while True:
            started = time.perf_counter()
            ok, frame = cap.read()
            if not ok:
                break
            ascii_text = render_frame(frame, cols, charset, halfblock)
            sys.stdout.write("\033[H")
            sys.stdout.write(ascii_text)
            sys.stdout.flush()
            elapsed = time.perf_counter() - started
            if elapsed < frame_delay:
                time.sleep(frame_delay - elapsed)
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        sys.stdout.write("\n")
        sys.stdout.flush()


def _add_common_args(parser):
    parser.add_argument(
        "--width", type=int, default=None,
        help="output width in characters (default: fit terminal)",
    )
    parser.add_argument(
        "--charset", choices=list(CHARSETS.keys()), default="default",
        help="character density ramp (default: default — 70-level)",
    )
    parser.add_argument(
        "--halfblock", action="store_true",
        help="use Unicode half-blocks for doubled vertical resolution "
             "(binary, ignores --charset)",
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Convert images/videos to ASCII art in the terminal.",
    )
    sub = parser.add_subparsers(dest="mode", required=True)

    p_img = sub.add_parser("image", help="convert a single image")
    p_img.add_argument("path", help="path to image file")
    p_img.add_argument("--output", default=None, help="optional PNG output path")
    _add_common_args(p_img)

    p_vid = sub.add_parser("video", help="play a video as ASCII")
    p_vid.add_argument("path", help="path to video file")
    _add_common_args(p_vid)

    return parser.parse_args()


def main():
    enable_ansi_on_windows()
    args = parse_args()
    if args.mode == "image":
        run_image(args.path, args.width, args.charset, args.output, args.halfblock)
    elif args.mode == "video":
        run_video(args.path, args.width, args.charset, args.halfblock)


if __name__ == "__main__":
    main()
