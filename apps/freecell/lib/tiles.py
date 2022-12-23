from play32sys import path
from graphic.pbm import read_image
from graphic.framebuf_helper import get_white_color, ensure_same_format, crop_framebuffer
import framebuf

TILES = []

def init(app_path, scr_format):
    WHITE = get_white_color(scr_format)
    res_path = path.join(app_path, "images", "cards.pbm")
    with open(res_path, "rb") as stream:
        w, h, _f, data, _c = read_image(stream)
    img = framebuf.FrameBuffer(data, w, h, framebuf.MONO_HLSB)
    support_subframe = hasattr(img, "subframe")
    # 4 * 6 tiles
    for row in range(6):
        for col in range(4):
            off_x = col * 8
            off_y = row * 8
            if not support_subframe:
                s_img = crop_framebuffer(img, off_x, off_y, 8, 8, framebuf.MONO_HLSB)
            else:
                s_img = img.subframe(off_x, off_y, 8, 8)
            s_img = ensure_same_format(s_img, framebuf.MONO_HLSB, 8, 8, scr_format, WHITE)
            TILES.append(s_img)

def get_tile(id):
    """ 0-3: type
        4-5: card bottom
        6-18: value
        19: blank
        20-21: cursor
        22-23: card top
    """
    return TILES[id]
