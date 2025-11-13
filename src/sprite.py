import os, pygame

def load_sheet(path, frame_w, frame_h, row=0, cols=None):
    """
    Cắt spritesheet theo kích thước frame_w x frame_h.
    - row: lấy hàng thứ row (0-based)
    - cols: số cột; nếu None, tự suy ra theo chiều rộng ảnh
    Trả về: list[Surface]
    """
    try:
        sheet = pygame.image.load(path).convert_alpha()
    except Exception:
        return []

    sw, sh = sheet.get_size()
    if cols is None or cols <= 0:
        cols = sw // frame_w
    frames = []
    y = row * frame_h
    for i in range(cols):
        x = i * frame_w
        frame = sheet.subsurface(pygame.Rect(x, y, frame_w, frame_h)).copy()
        frames.append(frame)
    return frames

def scale_frames(frames, target_w, target_h, keep_aspect=True):
    out = []
    for f in frames:
        if keep_aspect:
            fw, fh = f.get_size()
            scale = min(target_w / fw, target_h / fh)
            w, h = max(1, int(fw*scale)), max(1, int(fh*scale))
        else:
            w, h = target_w, target_h
        out.append(pygame.transform.smoothscale(f, (w, h)))
    return out

class Animator:
    def __init__(self, frames, fps=8):
        self.frames = frames
        self.fps = fps
        self.t = 0.0
        self.idx = 0

    def update(self, dt_ms):
        if not self.frames: return
        self.t += dt_ms
        period = 1000.0 / max(1.0, self.fps)
        while self.t >= period:
            self.t -= period
            self.idx = (self.idx + 1) % len(self.frames)

    def get(self):
        if not self.frames: return None
        return self.frames[self.idx]
