# assets.py
import os
import pygame
from . import settings as S

# Thư mục chứa ảnh
ASSET_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")

def asset_path(name: str) -> str:
    return os.path.join(ASSET_DIR, name)

def load_img(name: str, size=None):
    """
    Load ảnh PNG từ assets. Nếu size là tuple (w, h) thì scale;
    nếu size is None thì giữ nguyên kích thước gốc (giúp zoom không mờ).
    """
    p = asset_path(name)
    if not os.path.exists(p):
        return None
    img = pygame.image.load(p).convert_alpha()
    if size is not None:
        # chấp nhận tuple (w, h) hoặc (int,int); nếu size None → bỏ qua
        w, h = int(size[0]), int(size[1])
        if w > 0 and h > 0:
            # scale nearest để giữ nét
            img = pygame.transform.scale(img, (w, h))
    return img

def load_all(size=None):
    """
    Trả về dict các asset. Nếu size None -> không scale tại đây.
    main.py sẽ tự scale bằng transform.scale (nearest) theo view_side.
    """
    # Có thể đổi tên file theo ảnh của bạn
    return {
        "floor": load_img("floor.png",  size),
        "wall":  load_img("wall.png",   size),
        "start": load_img("start.png",  size),
        "goal":  load_img("goal.png",   size),
    }
