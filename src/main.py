# main.py
import sys, os, pygame, time
from . import settings as S
from .ui import Button, Segmented, Dropdown, PanelBox
from .astar import generate_states
from .assets import load_all, asset_path
from .sprite import load_sheet, Animator
import math
import random

from enum import Enum

# ---------- helpers ----------
def game_area_height():
    return S.HEIGHT - (S.TOP_PANEL_H + S.BOTTOM_PANEL_H)

def compute_square_cell_and_margins(rows, cols, right_panel_w):
    """Game area = phần còn lại (trừ top, bottom, sidebar phải). Cell luôn VUÔNG."""
    game_h = game_area_height()
    usable_w = S.WIDTH - right_panel_w
    cell = max(4, min(usable_w // cols, game_h // rows))
    mx = (usable_w - cols * cell) // 2
    my = S.TOP_PANEL_H + (game_h - rows * cell) // 2
    return cell, mx, my

# ---- TWO-LEG BUILDER: Start -> Key -> Goal ----
def build_two_leg_states(grid, start, key_pos, goal, monsters,
                         heuristic_kind, eight_dir, weight, monster_cost):
    """
    Tạo list states bằng cách ghép 2 lần generate_states:
      1) start -> key_pos
      2) key_pos -> goal
    Nếu không có key_pos, chạy thẳng start -> goal.
    """
    from .astar import generate_states  # tránh import vòng

    if key_pos:
        seg1 = list(generate_states(
            grid, start, key_pos,
            heuristic_kind=heuristic_kind,
            eight_dir=eight_dir,
            weight=weight,
            monsters=monsters,
            monster_extra_cost=monster_cost
        ))
        # không tới được Key -> trả về kết quả chặng 1
        if not seg1 or not seg1[-1].get("found"):
            return seg1

        seg2 = list(generate_states(
            grid, key_pos, goal,
            heuristic_kind=heuristic_kind,
            eight_dir=eight_dir,
            weight=weight,
            monsters=monsters,
            monster_extra_cost=monster_cost
        ))
        states = seg1 + seg2

        # vá path cuối = path1 + path2[1:] để không lặp node Key
        if seg2 and seg2[-1].get("found"):
            full_path = list(seg1[-1].get("path", [])) + list(seg2[-1].get("path", [])[1:])
            states[-1] = dict(states[-1])
            states[-1]["path"] = full_path
        return states

    # Không có key -> chạy thẳng
    return list(generate_states(
        grid, start, goal,
        heuristic_kind=heuristic_kind,
        eight_dir=eight_dir,
        weight=weight,
        monsters=monsters,
        monster_extra_cost=monster_cost
    ))

def to_rect(rc, CELL, MX, MY, camx, camy):
    r, c = rc
    return pygame.Rect(MX + c*CELL - camx, MY + r*CELL - camy, CELL, CELL)

def mouse_rc(mx, my, rows, cols, CELL, MX, MY, camx, camy, right_panel_x):
    # không nhận click trong sidebar
    if mx >= right_panel_x:
        return None
    gx = mx - MX + camx
    gy = my - MY + camy
    c = int(gx // CELL)
    r = int(gy // CELL)
    if 0 <= r < rows and 0 <= c < cols:
        return (r, c)
    return None

# Lấy rect modal History/Compare (to, co giãn theo màn hình)
def get_history_rect():
    pad_w = 120
    pad_h = 40
    panel_w = max(720, min(S.WIDTH - pad_w, 1200))
    panel_h = max(520, min(game_area_height() - pad_h, 760))
    panel_x = (S.WIDTH - panel_w) // 2
    panel_y = S.TOP_PANEL_H + (game_area_height() - panel_h) // 2
    return pygame.Rect(panel_x, panel_y, panel_w, panel_h)

# ---------- drawing ----------
def blit_scaled(screen, img, rect):
    if img:
        if img.get_size() == (rect.w, rect.h):
            screen.blit(img, rect.topleft)
        else:
            screen.blit(pygame.transform.scale(img, (rect.w, rect.h)), rect.topleft)

def draw_cell_base(screen, grid, rc, CELL, MX, MY, camx, camy, assets):
    rect = to_rect(rc, CELL, MX, MY, camx, camy)
    if grid[rc[0]][rc[1]] == 1:
        img = assets.get("wall")
        if img: blit_scaled(screen, img, rect)
        else:   pygame.draw.rect(screen, (65,70,80), rect)
    else:
        img = assets.get("floor")
        if img: blit_scaled(screen, img, rect)
        else:   pygame.draw.rect(screen, S.WHITE, rect)

def draw_overlay(screen, rc, kind, CELL, MX, MY, camx, camy, assets):
    rect = to_rect(rc, CELL, MX, MY, camx, camy)
    if kind == "start":
        img = assets.get("start")
        if img: blit_scaled(screen, img, rect)
        else:   pygame.draw.rect(screen, S.GREEN, rect); return
    if kind == "goal":
        img = assets.get("goal")
        if img: blit_scaled(screen, img, rect)
        else:   pygame.draw.rect(screen, S.RED, rect); return
    color, alpha = None, 128
    if kind == "open":    color, alpha = S.OPEN,   S.OPEN_ALPHA
    if kind == "closed":  color, alpha = S.CLOSED, S.CLOSED_ALPHA
    if kind == "path":    color, alpha = S.PATHC,  S.PATH_ALPHA
    if kind == "current": color, alpha = (255,120,120), S.CURR_ALPHA
    if color:
        ov = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        ov.fill((*color, alpha))
        screen.blit(ov, rect.topleft)

def draw_grid_lines(screen, rows, cols, CELL, MX, MY, camx, camy):
    for r in range(rows+1):
        y = MY + r*CELL - camy
        pygame.draw.line(screen, S.GRIDC, (MX, y), (MX + cols*CELL, y), 1)
    for c in range(cols+1):
        x = MX + c*CELL - camx
        pygame.draw.line(screen, S.GRIDC, (x, MY), (x, MY + rows*CELL), 1)

# ---------- sprites ----------
def scale_frames_to_cell(frames, CELL):
    out = []
    for f in frames:
        fw, fh = f.get_size()
        if S.SCALE_MODE == "fit_height":
            sc = (CELL * S.SCALE_MULT) / fh
        elif S.SCALE_MODE == "fit_width":
            sc = (CELL * S.SCALE_MULT) / fw
        else:  # fit_cell
            sc = min((CELL * S.SCALE_MULT)/fw, (CELL * S.SCALE_MULT)/fh)
        out.append(pygame.transform.scale(f, (max(1,int(fw*sc)), max(1,int(fh*sc)))))
    return out

def scale_frames_to_cell_monster(frames, CELL):
    out = []
    for f in frames:
        fw, fh = f.get_size()
        mode = getattr(S, "MONSTER_SCALE_MODE", "fit_cell")
        mult = float(getattr(S, "MONSTER_SCALE_MULT", 0.95))
        if mode == "fit_height":
            sc = (CELL * mult) / max(1, fh)
        elif mode == "fit_width":
            sc = (CELL * mult) / max(1, fw)
        else:  # fit_cell
            sc = min((CELL * mult)/max(1, fw), (CELL * mult)/max(1, fh))
        out.append(pygame.transform.scale(f, (max(1,int(fw*sc)), max(1,int(fh*sc)))))
    return out

def _load_strip_by_cols(path, cols):
    """Load 1 hàng sprite, tự suy frame_w từ sw//cols."""
    try:
        sheet = pygame.image.load(path).convert_alpha()
    except Exception:
        return []
    sw, sh = sheet.get_size()
    cols = max(1, int(cols))
    fw = sw // cols
    fh = sh
    frames = []
    for i in range(cols):
        rect = pygame.Rect(i*fw, 0, fw, fh)
        frames.append(sheet.subsurface(rect).copy())
    return frames

def load_monster_variants(CELL):
    """Trả về list variants: {"name", "right":[...], "left":[...]}"""
    variants = []
    for fname, cols in getattr(S, "MONSTER_SPECS", []):
        path = asset_path(fname)
        frames_r = _load_strip_by_cols(path, cols)
        frames_r = scale_frames_to_cell_monster(frames_r, CELL)
        frames_l = [pygame.transform.flip(f, True, False) for f in frames_r]
        variants.append({"name": fname, "right": frames_r, "left": frames_l})
    return variants

def load_key_frames(CELL):
    """Load từng frame của key (4 ảnh rời), scale vừa ô."""
    frames = []
    for i in range(4):
        path = asset_path(f"key_{i}.png")
        try:
            img = pygame.image.load(path).convert_alpha()
        except Exception:
            continue
        fw, fh = img.get_size()
        sc = min((CELL * 0.9) / fw, (CELL * 0.9) / fh)
        frames.append(pygame.transform.scale(img, (int(fw * sc), int(fh * sc))))
    return frames

def load_chest_frames(CELL):
    """Load 2 bộ frame của rương: idle_0..3 và open_0..3, scale vừa ô."""
    idle, opened = [], []
    for i in range(4):
        for prefix, bucket in (("chest_idle", idle), ("chest_open", opened)):
            path = asset_path(f"{prefix}_{i}.png")
            try:
                img = pygame.image.load(path).convert_alpha()
            except Exception:
                continue
            fw, fh = img.get_size()
            sc = min((CELL * 0.95) / fw, (CELL * 0.95) / fh)
            bucket.append(pygame.transform.scale(img, (int(fw * sc), int(fh * sc))))
    return idle, opened

def load_flag_frames(CELL):
    """Load 4 frame cờ start: flag_0..3, scale vừa 1 ô."""
    frames = []
    for i in range(4):
        path = asset_path(f"flag_{i}.png")
        try:
            img = pygame.image.load(path).convert_alpha()
        except Exception:
            continue
        fw, fh = img.get_size()
        sc = min((CELL * 0.95) / fw, (CELL * 0.95) / fh)
        frames.append(pygame.transform.scale(img, (int(fw * sc), int(fh * sc))))
    return frames

def load_sheet_rows(file, cols, CELL):
    path = asset_path(file)
    rows = {}
    cols_arg = None if (cols is None or cols <= 0) else cols
    for row in (S.ROW_DOWN, S.ROW_LEFT, S.ROW_RIGHT, S.ROW_UP):
        base = load_sheet(path, S.FRAME_W, S.FRAME_H, row=row, cols=cols_arg)
        base = scale_frames_to_cell(base, CELL)
        rows[row] = base
    return rows

def pick_row(dr, dc):
    if abs(dr) >= abs(dc):
        return S.ROW_DOWN if dr>0 else (S.ROW_UP if dr<0 else S.ROW_DOWN)
    return S.ROW_RIGHT if dc>0 else S.ROW_LEFT

def _step_cost(r0, c0, r1, c1):
    dr, dc = abs(r1 - r0), abs(c1 - c0)
    if dr == 1 and dc == 1:
        return 1.0 if getattr(S, "HEURISTIC", "manhattan") == "chebyshev" else math.sqrt(2.0)
    return 1.0

def compute_metrics(states, monsters=None, monster_extra_cost=0.0):
    """Tính (explored_count, total_cost) — total_cost gồm bước đi + phụ phí khi bước vào ô Monster."""
    if not states:
        return 0, 0.0
    last = states[-1]
    explored = len(last.get("closed", []))
    path = last.get("path", [])
    cost = 0.0
    for i in range(1, len(path)):
        r0, c0 = path[i-1]
        r1, c1 = path[i]
        cost += _step_cost(r0, c0, r1, c1)
        if monsters and (r1, c1) in monsters:
            cost += float(monster_extra_cost)
    return explored, cost


# ---------- NEW: Tools / Inventory ----------
class Tool(Enum):
    START = "start"
    GOAL = "goal"
    KEY = "key"
    WALL = "wall"
    MONSTER = "monster"

INVENTORY_MAX = {
    Tool.START: 1,
    Tool.GOAL: 1,
    Tool.KEY: 1,
    Tool.WALL: float("inf"),
    Tool.MONSTER: float("inf"),
}

# ===== Monster picker =====
MONSTER_OPTIONS = [
    {"fname": "monster_bat_flight.png",    "label": "Bat",      "cost": 5},
    {"fname": "monster_goblin_idle.png",   "label": "Goblin",   "cost": 8},
    {"fname": "monster_mushroom_idle.png", "label": "Mushroom", "cost": 10},
    {"fname": "monster_skeleton_idle.png", "label": "Skeleton", "cost": 12},
]

def get_monster_picker_rect():
    """Cửa sổ chọn loại Monster (nhỏ hơn History)."""
    # make the picker noticeably smaller than History dialog
    pad_w = 220
    pad_h = 80
    panel_w = max(360, min(S.WIDTH - pad_w, 520))
    panel_h = max(220, min(game_area_height() - pad_h, 320))
    panel_x = (S.WIDTH - panel_w) // 2
    panel_y = S.TOP_PANEL_H + (game_area_height() - panel_h) // 2
    return pygame.Rect(panel_x, panel_y, panel_w, panel_h)

# Màu vẽ fallback
COLOR_KEY = (240, 200, 0)
COLOR_MONSTER = (200, 40, 40)
COLOR_TOOL_HILITE = (70, 90, 140)

# ---------- main ----------
def run():
    pygame.init()
    print(pygame.version.ver)
    screen = pygame.display.set_mode((S.WIDTH, S.HEIGHT))
    pygame.display.set_caption("A* Pathfinding Visualizer")
    clock = pygame.time.Clock()

    # fonts
    title_font = pygame.font.SysFont(S.UI_FONT_NAME, S.TITLE_FONT_SIZE, bold=True)
    ui_font    = pygame.font.SysFont(S.UI_FONT_NAME, S.UI_FONT_SIZE)
    help_font  = pygame.font.SysFont(S.UI_FONT_NAME, S.HELP_FONT_SIZE, bold=True)
    tiny_font  = pygame.font.SysFont(S.UI_FONT_NAME, max(12, S.UI_FONT_SIZE-2))

    # Sidebar dimensions
    RIGHT_W = 260
    RIGHT_X = S.WIDTH - RIGHT_W
    RIGHT_RECT = pygame.Rect(RIGHT_X, S.TOP_PANEL_H, RIGHT_W, S.HEIGHT - (S.TOP_PANEL_H + S.BOTTOM_PANEL_H))
    SIDEPAD = 8

    # Map presets
    MAP_PRESETS = [(10,15), (15,20), (20,30), (30,40)]
    preset_names= ["S","M","L","XL"]
    preset_idx  = 2
    ROWS, COLS = MAP_PRESETS[preset_idx]

    # layout cell/margins
    CELL, MX, MY = compute_square_cell_and_margins(ROWS, COLS, RIGHT_W)
    camx = camy = 0

    # data
    grid  = [[0 for _ in range(COLS)] for _ in range(ROWS)]
    start = None; goal = None
    key_pos = None
    monsters = set()
    monsters_info = {}

    # Inventory
    inventory_left = {t: (INVENTORY_MAX[t] if INVENTORY_MAX[t] != float("inf") else float("inf")) for t in Tool}
    current_tool = Tool.WALL

    assets = load_all(None)
    idle_rows = load_sheet_rows(S.IDLE_FILE, S.IDLE_COLS, CELL)
    walk_rows = load_sheet_rows(S.WALK_FILE, S.WALK_COLS, CELL)
    idle_anim = Animator(idle_rows[S.ROW_DOWN], fps=S.IDLE_FPS)
    walk_anim = Animator(walk_rows[S.ROW_DOWN], fps=S.WALK_FPS)
    monster_variants = load_monster_variants(CELL)
    key_frames = load_key_frames(CELL)
    key_anim = Animator(key_frames, fps=6)
    chest_idle_frames, chest_open_frames = load_chest_frames(CELL)
    chest_idle_anim = Animator(chest_idle_frames, fps=6) if chest_idle_frames else None
    chest_open_anim = Animator(chest_open_frames, fps=10) if chest_open_frames else None
    flag_frames = load_flag_frames(CELL)
    flag_anim = Animator(flag_frames, fps=8) if flag_frames else None

    # --- Tool icons (text + small image) ---
    ICON_SIZE = 18
    def _make_icon(img, fallback_draw=None):
        surf = pygame.Surface((ICON_SIZE, ICON_SIZE), pygame.SRCALPHA)
        if img:
            iw, ih = img.get_size()
            sc = min(ICON_SIZE / max(1, iw), ICON_SIZE / max(1, ih))
            img2 = pygame.transform.smoothscale(img, (max(1, int(iw*sc)), max(1, int(ih*sc))))
            surf.blit(img2, ((ICON_SIZE - img2.get_width())//2, (ICON_SIZE - img2.get_height())//2))
        elif fallback_draw:
            fallback_draw(surf)
        return surf

    def build_tool_icons():
        _start_img = (flag_frames[0] if flag_frames else assets.get("start"))
        _goal_img  = (chest_idle_frames[0] if chest_idle_frames else assets.get("goal"))
        _key_img   = (key_frames[0] if key_frames else None)
        _wall_img  = assets.get("wall")
        start_icon = _make_icon(_start_img, lambda s: pygame.draw.rect(s,(0,160,90),s.get_rect(),border_radius=3))
        goal_icon  = _make_icon(_goal_img,  lambda s: pygame.draw.rect(s,(210,40,40),s.get_rect(),border_radius=3))
        key_icon   = _make_icon(_key_img,   lambda s: pygame.draw.circle(s,(240,200,0),(ICON_SIZE//2,ICON_SIZE//2), ICON_SIZE//2-2))
        wall_icon  = _make_icon(_wall_img,  lambda s: pygame.draw.rect(s,(90,95,105),s.get_rect()))
        return {Tool.START:start_icon, Tool.GOAL:goal_icon, Tool.KEY:key_icon, Tool.WALL:wall_icon}

    tool_icons = build_tool_icons()

    # --- Monster picker state (init mapping + default) ---
    monster_picker_open = False
    monster_choice_index = 0
    variant_name_to_index = {v.get("name"): i for i, v in enumerate(monster_variants)}
    if MONSTER_OPTIONS:
        default_fname = MONSTER_OPTIONS[0]["fname"]
        if default_fname in variant_name_to_index:
            monster_choice_index = variant_name_to_index[default_fname]
        S.MONSTER_COST = MONSTER_OPTIONS[0]["cost"]

    # layout cache for monster modal (to handle clicks event-based)
    mp_layout = None  # dict with MP_RECT, close_rect, cells

    cur_kind, cur_row = "idle", S.ROW_DOWN

    def set_anim(kind, row):
        nonlocal idle_anim, walk_anim, cur_kind, cur_row
        if kind not in ("idle","walk"): kind="idle"
        if row not in idle_rows: row=S.ROW_DOWN
        cur_kind, cur_row = kind, row
        idle_anim = Animator(idle_rows[row], fps=S.IDLE_FPS)
        walk_anim = Animator(walk_rows[row], fps=S.WALK_FPS)

    def get_frame(dt):
        if cur_kind=="walk":
            walk_anim.update(dt); return walk_anim.get()
        idle_anim.update(dt); return idle_anim.get()

    # ------------- BOTTOM BAR -------------
    BTN_W, BTN_H = 84, 30
    col_w = (S.WIDTH - RIGHT_W) // 3
    row_y1 = S.HEIGHT - S.BOTTOM_PANEL_H + 14

    control_box = PanelBox(pygame.Rect(20, row_y1-8, col_w-40, BTN_H+16), "Control", tiny_font)
    cx = control_box.rect.centerx
    btn_prev = Button((cx - (BTN_W*3//2 + 8), row_y1, BTN_W, BTN_H), "Step -", ui_font)
    btn_play = Button((cx - (BTN_W//2),       row_y1, BTN_W, BTN_H), "Play",   ui_font)
    btn_next = Button((cx + (BTN_W//2 + 8),   row_y1, BTN_W, BTN_H), "Step +", ui_font)

    dir_box = PanelBox(pygame.Rect(col_w+20, row_y1-8, col_w-40, BTN_H+16), "Direction", tiny_font)
    cx = dir_box.rect.centerx
    btn_4dir = Button((cx - BTN_W - 8, row_y1, BTN_W, BTN_H), "4-dir", ui_font, toggle=True)
    btn_8dir = Button((cx + 8,         row_y1, BTN_W, BTN_H), "8-dir", ui_font, toggle=True)
    btn_4dir.active = not S.EIGHT_DIR; btn_8dir.active = S.EIGHT_DIR

    heur_labels = ["Manhattan","Euclid","Octile","Chebyshev"]
    _sel_h = {"manhattan":0,"euclidean":1,"octile":2,"chebyshev":3}.get(getattr(S,"HEURISTIC","manhattan"),0)
    drp_heur = Dropdown((2*col_w + 20 + (col_w-40)//2 - 160, row_y1, 320, BTN_H),
                        heur_labels, ui_font, selected_index=_sel_h)

    # ------------- SIDEBAR -------------
    sidebar_title = title_font.render("Menu", True, S.TEXT)
    drp_size = Dropdown((RIGHT_X + SIDEPAD, 0, RIGHT_W - 2*SIDEPAD, 30),
                        preset_names, ui_font, selected_index=preset_idx)

    # Weight (bao gồm <1)
    weight_options = ["0.50", "0.75", "0.90", "1.00", "1.25", "1.50", "2.00"]
    def _w_index(w):
        try:
            s = f"{float(w):.2f}"
            return weight_options.index(s)
        except Exception:
            return weight_options.index("1.00")
    drp_w = Dropdown((RIGHT_X + 8, 0, RIGHT_W - 16, 30),
                     weight_options, ui_font,
                     selected_index=_w_index(getattr(S, "WEIGHT", 1.0)))

    btn_hist = Button((RIGHT_X + SIDEPAD, 0, 110, 26), "History", ui_font, toggle=True)
    btn_hist.active = False

    # NEW: TOOLBAR (các nút chọn tool)
    tool_buttons = []
    def set_current_tool(t):
        nonlocal current_tool
        current_tool = t
        for b in tool_buttons:
            b.active = (b._tool == t)
    def make_tool_button(label, tool_enum, rect):
        b = Button(rect, label, ui_font, toggle=True)
        b._tool = tool_enum
        tool_buttons.append(b)
        return b

    # pathfinding state
    states, idx = [], -1
    playing, dirty = False, True
    last_ms = 0
    history = []
    hist_open = False
    hist_selected = set()
    hist_show_compare = False

    last_build_runtime_ms = 0.0

    # ----- Helpers: place/remove -----
    def cell_is_free_for_entity(r, c):
        if grid[r][c] == 1: return False
        if start is not None and (r, c) == start: return False
        if goal is not None and (r, c) == goal: return False
        if key_pos is not None and (r, c) == key_pos: return False
        if (r, c) in monsters: return False
        return True

    def place_entity(tool, r, c):
        nonlocal start, goal, key_pos
        left = inventory_left[tool]
        if left == 0:
            return
        if tool == Tool.WALL:
            if grid[r][c] != 1 and ((r,c) != start and (r,c) != goal and (r,c) != key_pos and (r,c) not in monsters):
                grid[r][c] = 1
            return
        if not cell_is_free_for_entity(r, c):
            return
        if tool == Tool.START:
            if start is None:
                start = (r, c)
                if INVENTORY_MAX[Tool.START] != float("inf"):
                    inventory_left[Tool.START] -= 1
        elif tool == Tool.GOAL:
            if goal is None:
                goal = (r, c)
                if INVENTORY_MAX[Tool.GOAL] != float("inf"):
                    inventory_left[Tool.GOAL] -= 1
        elif tool == Tool.KEY:
            if key_pos is None:
                key_pos = (r, c)
                if INVENTORY_MAX[Tool.KEY] != float("inf"):
                    inventory_left[Tool.KEY] -= 1
        elif tool == Tool.MONSTER:
            if (r, c) not in monsters:
                monsters.add((r, c))
                vidx = monster_choice_index if monster_variants else 0
                v = monster_variants[vidx] if monster_variants else {"right": [], "left": []}
                anim_r = Animator(v["right"], fps=int(getattr(S, "MONSTER_FPS", 8)))
                anim_l = Animator(v["left"],  fps=int(getattr(S, "MONSTER_FPS", 8)))
                monsters_info[(r, c)] = {
                    "variant": vidx,
                    "anim_right": anim_r,
                    "anim_left":  anim_l,
                    "facing": "right",
                }

    def remove_entity_at(r, c):
        nonlocal start, goal, key_pos
        if grid[r][c] == 1:
            grid[r][c] = 0
            return True
        if start is not None and (r, c) == start:
            start = None
            if INVENTORY_MAX[Tool.START] != float("inf"):
                inventory_left[Tool.START] += 1
            return True
        if goal is not None and (r, c) == goal:
            goal = None
            if INVENTORY_MAX[Tool.GOAL] != float("inf"):
                inventory_left[Tool.GOAL] += 1
            return True
        if key_pos is not None and (r, c) == key_pos:
            key_pos = None
            if INVENTORY_MAX[Tool.KEY] != float("inf"):
                inventory_left[Tool.KEY] += 1
            return True
        if (r, c) in monsters:
            monsters.remove((r, c))
            if (r, c) in monsters_info:
                monsters_info.pop((r, c), None)
            return True
        return False

    # ----- History helpers -----
    def record_history():
        nonlocal history
        if not states or not states[-1].get("found"): return
        explored, shortest = compute_metrics(
            states,
            monsters=monsters,
            monster_extra_cost=float(getattr(S, "MONSTER_COST", 0.0))
        )
        item = {
            "heuristic": getattr(S,'HEURISTIC','manhattan'),
            "eight_dir": bool(S.EIGHT_DIR),
            "weight": float(getattr(S,'WEIGHT',1.0)),
            "explored": int(explored),
            "cost": float(shortest),
            "runtime_ms": float(last_build_runtime_ms),
            "timestamp": pygame.time.get_ticks(),
        }
        dir_lbl = "8-dir" if item["eight_dir"] else "4-dir"
        item["label"] = f"{dir_lbl} | H:{item['heuristic']} | W:{item['weight']:.2f} → explored:{item['explored']}, path:{item['cost']:.2f}, time:{item['runtime_ms']:.1f}ms"
        if not history or history[-1]["label"] != item["label"]:
            history.append(item)
            history[:] = history[-40:]

    def rebuild():
        nonlocal states, idx, dirty, last_build_runtime_ms
        if start is None or goal is None:
            states, idx = [], -1
            last_build_runtime_ms = 0.0
        else:
            t0 = time.perf_counter()
            states = build_two_leg_states(
                grid=grid,
                start=start,
                key_pos=key_pos,
                goal=goal,
                monsters=monsters,
                heuristic_kind=getattr(S, "HEURISTIC", "manhattan"),
                eight_dir=S.EIGHT_DIR,
                weight=float(getattr(S, "WEIGHT", 1.0)),
                monster_cost=float(getattr(S, "MONSTER_COST", 0.0))
            )
            t1 = time.perf_counter()
            last_build_runtime_ms = (t1 - t0) * 1000.0
            idx = 0 if states else -1
        dirty=False

    def step_to(new_idx):
        nonlocal idx
        if not (0<=new_idx<len(states)): return
        a = states[new_idx-1]["current"] if new_idx-1>=0 else start
        b = states[new_idx]["current"]
        if a and b: set_anim("walk", pick_row(b[0]-a[0], b[1]-a[1]))
        idx = new_idx
        if idx == len(states)-1:
            record_history()

    def reset_map_to(rows, cols):
        nonlocal ROWS, COLS, CELL, MX, MY, grid, start, goal, key_pos, monsters
        nonlocal idle_rows, walk_rows, idle_anim, walk_anim, idx, states, playing, dirty
        nonlocal monster_variants
        nonlocal key_frames, key_anim
        nonlocal chest_idle_frames, chest_open_frames, chest_idle_anim, chest_open_anim
        nonlocal flag_frames, flag_anim
        nonlocal variant_name_to_index, monster_choice_index  # <-- cần nonlocal
        nonlocal tool_icons

        ROWS, COLS = rows, cols
        CELL, MX, MY = compute_square_cell_and_margins(ROWS, COLS, RIGHT_W)
        grid  = [[0 for _ in range(COLS)] for _ in range(ROWS)]
        start = None; goal = None
        key_pos = None; monsters = set()
        monsters_info.clear()
        for t in (Tool.START, Tool.GOAL, Tool.KEY):
            inventory_left[t] = 1
        idle_rows = load_sheet_rows(S.IDLE_FILE, S.IDLE_COLS, CELL)
        walk_rows = load_sheet_rows(S.WALK_FILE, S.WALK_COLS, CELL)
        idle_anim = Animator(idle_rows[S.ROW_DOWN], fps=S.IDLE_FPS)
        walk_anim = Animator(walk_rows[S.ROW_DOWN], fps=S.WALK_FPS)

        monster_variants = load_monster_variants(CELL)
        variant_name_to_index = {v.get("name"): i for i, v in enumerate(monster_variants)}
        if MONSTER_OPTIONS:
            default_fname = MONSTER_OPTIONS[0]["fname"]
            if default_fname in variant_name_to_index:
                monster_choice_index = variant_name_to_index[default_fname]
            S.MONSTER_COST = MONSTER_OPTIONS[0]["cost"]

        key_frames = load_key_frames(CELL)
        key_anim = Animator(key_frames, fps=6)
        chest_idle_frames, chest_open_frames = load_chest_frames(CELL)
        chest_idle_anim = Animator(chest_idle_frames, fps=6) if chest_idle_frames else None
        chest_open_anim = Animator(chest_open_frames, fps=10) if chest_open_frames else None
        flag_frames = load_flag_frames(CELL)
        flag_anim = Animator(flag_frames, fps=8) if flag_frames else None

        tool_icons = build_tool_icons()

        idx=-1; states=[]; playing=False; dirty=True

    # ---------- loop ----------
    running=True
    while running:
        dt = clock.tick(S.FPS)

        # precompute monster picker layout for this frame so we can use in event handling
        mp_layout = None
        if 'monster_picker_open' in locals() and monster_picker_open:
            MP_RECT = get_monster_picker_rect()
            close_rect = pygame.Rect(MP_RECT.right - 86, MP_RECT.y + 10, 70, 28)
            pad = 22
            cell_w = (MP_RECT.w - pad*3)//2
            cell_h = (MP_RECT.h - 80 - pad*3)//2
            cells = []
            for i, opt in enumerate(MONSTER_OPTIONS):
                r = i // 2
                c = i % 2
                x = MP_RECT.x + pad + c*(cell_w + pad)
                y = MP_RECT.y + 56 + pad + r*(cell_h + pad)
                rect = pygame.Rect(x, y, cell_w, cell_h)
                cells.append((rect, opt))
            mp_layout = {"MP_RECT": MP_RECT, "close_rect": close_rect, "cells": cells}

        # === AUTO-LAYOUT SIDEBAR ===
        y = S.TOP_PANEL_H + 10 + 28
        lbl_size_h = ui_font.size("Size")[1]
        drp_size.rect.topleft = (RIGHT_X + SIDEPAD, y + lbl_size_h + 6)
        drp_size.rect.w = RIGHT_W - 2*SIDEPAD
        size_label_pos = (RIGHT_X + SIDEPAD, y)
        y = drp_size.rect.bottom + 14
        lbl_w_h = ui_font.size("W (weight)")[1]
        drp_w.rect.topleft = (RIGHT_X + SIDEPAD, y + lbl_w_h + 6)
        drp_w.rect.w = RIGHT_W - 2*SIDEPAD
        weight_label_pos = (RIGHT_X + SIDEPAD, y)
        y = drp_w.rect.bottom + 16

        # History title + button
        hist_sep_y = y
        hist_label_pos = (RIGHT_X + SIDEPAD, y + 8)
        btn_hist.rect.topleft = (RIGHT_X + SIDEPAD, y + 30)
        btn_hist.rect.size = (110, 26)
        y = btn_hist.rect.bottom + 16

        # --- TOOLBAR SECTION ---
        pygame.draw.line(screen, S.BTN_BR, (RIGHT_X+SIDEPAD, y), (RIGHT_X+RIGHT_W-SIDEPAD, y), 1)
        tools_label_pos = (RIGHT_X + SIDEPAD, y + 8)
        btn_h = 32
        btn_w = (RIGHT_W - 3*SIDEPAD) // 2
        rect_start  = pygame.Rect(RIGHT_X + SIDEPAD,           y + 34, btn_w, btn_h)
        rect_goal   = pygame.Rect(rect_start.right + SIDEPAD,  y + 34, btn_w, btn_h)
        rect_key    = pygame.Rect(RIGHT_X + SIDEPAD,           rect_start.bottom + 8, btn_w, btn_h)
        rect_wall   = pygame.Rect(RIGHT_X + SIDEPAD,           rect_key.bottom + 8, btn_w, btn_h)
        rect_mon    = pygame.Rect(rect_wall.right + SIDEPAD,   rect_key.bottom + 8, btn_w, btn_h)

        if not tool_buttons:
            make_tool_button("Start",   Tool.START,   rect_start)
            make_tool_button("Goal",    Tool.GOAL,    rect_goal)
            make_tool_button("Key",     Tool.KEY,     rect_key)
            make_tool_button("Wall",    Tool.WALL,    rect_wall)
            make_tool_button("Monster", Tool.MONSTER, rect_mon)
            set_current_tool(current_tool)
        else:
            tool_buttons[0].rect = rect_start
            tool_buttons[1].rect = rect_goal
            tool_buttons[2].rect = rect_key
            tool_buttons[3].rect = rect_wall
            tool_buttons[4].rect = rect_mon

        # --------- EVENTS ---------
        for e in pygame.event.get():
            # quit
            if e.type == pygame.QUIT:
                running=False
                continue

            # keyboard
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_SPACE:
                    if dirty: rebuild()
                    if states:
                        playing = not playing
                        last_ms = 0
                elif e.key == pygame.K_LEFT:
                    if dirty: rebuild()
                    if states:
                        step_to(max(0, idx-1)); playing = False
                elif e.key == pygame.K_RIGHT:
                    if dirty: rebuild()
                    if states:
                        step_to(min(len(states)-1, idx+1)); playing = False
                elif e.key == pygame.K_ESCAPE and hist_open:
                    hist_open = False
                    hist_selected.clear(); hist_show_compare = False
                elif e.key == pygame.K_b and hist_open and hist_show_compare:
                    hist_show_compare = False

            # Click outside modal to close (History)
            if hist_open and e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                mx, my = e.pos
                HIST_RECT = get_history_rect()
                if not HIST_RECT.collidepoint(mx, my):
                    hist_open = False
                    hist_selected.clear(); hist_show_compare = False

            # Controls
            if btn_prev.clicked(e):
                if dirty: rebuild()
                if states: step_to(max(0, idx-1)); playing=False
            if btn_play.clicked(e):
                if dirty: rebuild()
                if states: playing = not playing; last_ms=0
            if btn_next.clicked(e):
                if dirty: rebuild()
                if states: step_to(min(len(states)-1, idx+1)); playing=False

            # Direction
            if btn_4dir.clicked(e):
                S.EIGHT_DIR=False
                btn_4dir.active=True; btn_8dir.active=False
                S.HEURISTIC = "manhattan"; drp_heur.selected = 0
                dirty=True; playing=False
            if btn_8dir.clicked(e):
                S.EIGHT_DIR=True
                btn_4dir.active=False; btn_8dir.active=True
                if getattr(S, "HEURISTIC", "manhattan") == "manhattan":
                    S.HEURISTIC = "octile"; drp_heur.selected = 2
                dirty=True; playing=False

            # Heuristic select
            if drp_heur.handle(e):
                choices = ["manhattan","euclidean","octile","chebyshev"]
                choice = choices[drp_heur.selected]
                if not S.EIGHT_DIR:
                    S.HEURISTIC = "manhattan"; drp_heur.selected = 0
                else:
                    if choice == "manhattan":
                        S.HEURISTIC = "octile"; drp_heur.selected = 2
                    else:
                        S.HEURISTIC = choice
                dirty = True; playing = False

            # Sidebar: Size & Weight
            if drp_size.handle(e):
                r,c = MAP_PRESETS[drp_size.selected]; reset_map_to(r,c)
            if drp_w.handle(e):
                try: S.WEIGHT = float(weight_options[drp_w.selected])
                except Exception: S.WEIGHT = 1.0
                dirty = True; playing = False

            # Open History modal
            if btn_hist.clicked(e):
                playing = False
                hist_open = True
                hist_show_compare = False

            # === TOOLBAR: chọn tool ===
            if e.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP) and e.button == 1:
                for b in tool_buttons:
                    if b.rect.collidepoint(e.pos):
                        # Nếu là Monster -> bật picker
                        if b._tool == Tool.MONSTER:
                            playing = False
                            monster_picker_open = True
                        else:
                            set_current_tool(b._tool)

            # === Map edit bằng tool ===
            if e.type == pygame.MOUSEBUTTONDOWN:
                if e.button==1:
                    rc = mouse_rc(*e.pos, ROWS,COLS,CELL,MX,MY,camx,camy, RIGHT_X)
                    if rc:
                        place_entity(current_tool, rc[0], rc[1])
                        dirty=True; playing=False
                elif e.button==3:
                    rc = mouse_rc(*e.pos, ROWS,COLS,CELL,MX,MY,camx,camy, RIGHT_X)
                    if rc:
                        if remove_entity_at(rc[0], rc[1]):
                            dirty=True; playing=False

            # kéo chuột phải: vẽ tường (Wall only)
            if e.type==pygame.MOUSEMOTION and pygame.mouse.get_pressed()[2] and current_tool == Tool.WALL:
                rc = mouse_rc(*e.pos, ROWS,COLS,CELL,MX,MY,camx,camy, RIGHT_X)
                if rc:
                    if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                        if grid[rc[0]][rc[1]] == 1:
                            grid[rc[0]][rc[1]] = 0
                            dirty=True; playing=False
                    else:
                        if grid[rc[0]][rc[1]] != 1 and (rc != start and rc != goal and rc != key_pos and rc not in monsters):
                            grid[rc[0]][rc[1]] = 1
                            dirty=True; playing=False

            # ====== History modal interactions ======
            if hist_open:
                HIST_RECT = get_history_rect()
                list_pad = 16
                content = pygame.Rect(HIST_RECT.x + list_pad,
                                      HIST_RECT.y + 56,
                                      HIST_RECT.w - 2*list_pad,
                                      HIST_RECT.h - 56 - list_pad - 48)
                if hist_show_compare and e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    btn_y3 = content.bottom + 10
                    btn_w3, btn_h3 = 140, 32
                    btn_back_cmp = pygame.Rect(HIST_RECT.x + list_pad, btn_y3, btn_w3, btn_h3)
                    if btn_back_cmp.collidepoint(e.pos):
                        hist_show_compare = False
                        continue

                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    if content.collidepoint(e.pos) and not hist_show_compare:
                        line_h = ui_font.get_height() + 8
                        idx_in_view = (e.pos[1] - (content.y + 10)) // line_h
                        lines = history[-200:]; total = len(lines)
                        if 0 <= idx_in_view < total:
                            real_idx = len(history) - 1 - idx_in_view
                            if 0 <= real_idx < len(history):
                                if real_idx in hist_selected:
                                    hist_selected.remove(real_idx)
                                else:
                                    hist_selected.add(real_idx)

                btn_y2 = content.bottom + 10
                btn_w2, btn_h2 = 140, 32
                gap2 = 14
                btn_compare = pygame.Rect(HIST_RECT.x + list_pad, btn_y2, btn_w2, btn_h2)
                btn_reset   = pygame.Rect(btn_compare.right + gap2, btn_y2, btn_w2, btn_h2)
                btn_back    = pygame.Rect(btn_reset.right + gap2, btn_y2, btn_w2, btn_h2)

                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    if btn_compare.collidepoint(e.pos):
                        if len(hist_selected) >= 2:
                            hist_show_compare = True
                    elif btn_reset.collidepoint(e.pos):
                        hist_selected.clear(); hist_show_compare = False

            # ===== Monster picker interactions (event-based to avoid multi-trigger) =====
            if monster_picker_open and mp_layout and e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                mx, my = e.pos
                if mp_layout["close_rect"].collidepoint(mx, my):
                    monster_picker_open = False
                else:
                    for rect, opt in mp_layout["cells"]:
                        if rect.collidepoint(mx, my):
                            if opt["fname"] in variant_name_to_index:
                                monster_choice_index = variant_name_to_index[opt["fname"]]
                            S.MONSTER_COST = opt["cost"]
                            set_current_tool(Tool.MONSTER)
                            monster_picker_open = False
                            break

        # autoplay
        if playing and states:
            last_ms += dt
            if last_ms >= S.AUTO_STEP_EVERY_MS:
                last_ms = 0
                if idx < len(states)-1: step_to(idx+1)
                else: playing=False

        if dirty and not playing:
            rebuild()

        # runner pos
        draw_rc=None
        if 0<=idx<len(states):
            st=states[idx]
            if st.get("found") and goal is not None:
                draw_rc=goal; set_anim("idle", S.ROW_DOWN)
            else:
                cur=st["current"]; draw_rc=cur if cur else (start if start else None)
        else:
            if start: draw_rc=start; set_anim("idle", S.ROW_DOWN)

        # Xác định cột của player để quái quay mặt
        player_c = None
        if 0 <= idx < len(states):
            st = states[idx]
            prc = st["current"] if st["current"] else (start if start else None)
            if prc: player_c = prc[1]
        elif start:
            player_c = start[1]

        # Cập nhật facing + animator
        for (mr, mc), info in list(monsters_info.items()):
            if player_c is not None:
                info["facing"] = "left" if player_c < mc else "right"
            if info["facing"] == "left":
                info["anim_left"].update(dt)
            else:
                info["anim_right"].update(dt)

        # --------- render ---------
        screen.fill(S.WHITE)

        # TOP BAR
        pygame.draw.rect(screen, S.TOP_BG, (0,0,S.WIDTH,S.TOP_PANEL_H))
        h1 = "LMB: place by tool • RMB drag (Wall only) • RMB: remove • Shift+RMB: erase wall • Space: Play/Pause"
        t1 = help_font.render(h1, True, S.TEXT)
        screen.blit(t1, (12, 10))

        # GAME AREA
        game_rect = pygame.Rect(0, S.TOP_PANEL_H, S.WIDTH - RIGHT_W, game_area_height())
        screen.set_clip(game_rect)

        for r in range(ROWS):
            for c in range(COLS):
                draw_cell_base(screen, grid, (r,c), CELL, MX, MY, camx, camy, assets)

        if 0<=idx<len(states):
            st=states[idx]
            for rc in st["closed"]: draw_overlay(screen, rc, 'closed', CELL, MX, MY, camx, camy, assets)
            for rc in st["open"]:   draw_overlay(screen, rc, 'open',   CELL, MX, MY, camx, camy, assets)
            for rc in st["path"]:   draw_overlay(screen, rc, 'path',   CELL, MX, MY, camx, camy, assets)
            if st["current"]:       draw_overlay(screen, st["current"], 'current', CELL, MX, MY, camx, camy, assets)

        # Start = cờ động
        if start:
            sr, sc = start
            rect = to_rect((sr, sc), CELL, MX, MY, camx, camy)
            if flag_anim:
                flag_anim.update(dt)
                fr = flag_anim.get()
                if fr:
                    fw, fh = fr.get_size()
                    screen.blit(fr, (rect.x + (rect.w - fw)//2, rect.y + (rect.h - fh)//2))
            else:
                draw_overlay(screen, start, 'start', CELL, MX, MY, camx, camy, assets)

        # Goal = Chest (idle -> open khi chạm đích)
        if goal:
            gr, gc = goal
            rect = to_rect((gr, gc), CELL, MX, MY, camx, camy)
            opened = False
            if 0 <= idx < len(states):
                st_curr = states[idx]
                if (st_curr.get("current") == goal) or (st_curr.get("found") and idx == len(states) - 1):
                    opened = True
            anim = (chest_open_anim if opened and chest_open_anim else chest_idle_anim)
            if anim:
                anim.update(dt)
                fr = anim.get()
                if fr:
                    fw, fh = fr.get_size()
                    screen.blit(fr, (rect.x + (rect.w - fw)//2, rect.y + (rect.h - fh)//2))
            else:
                draw_overlay(screen, goal, 'goal', CELL, MX, MY, camx, camy, assets)

        # KEY
        if key_pos is not None and key_frames:
            kr, kc = key_pos
            rect = to_rect((kr, kc), CELL, MX, MY, camx, camy)
            key_anim.update(dt)
            fr = key_anim.get()
            if fr:
                fw, fh = fr.get_size()
                screen.blit(fr, (rect.x + (rect.w - fw)//2, rect.y + (rect.h - fh)//2))
        elif key_pos is not None:
            kr, kc = key_pos
            rect = to_rect((kr, kc), CELL, MX, MY, camx, camy)
            pygame.draw.circle(screen, COLOR_KEY, rect.center, max(4, rect.w // 3))

        # MONSTERS
        for (mr, mc) in monsters:
            rect = to_rect((mr, mc), CELL, MX, MY, camx, camy)
            info = monsters_info.get((mr, mc))
            if info:
                fr = info["anim_left"].get() if info["facing"] == "left" else info["anim_right"].get()
                if fr:
                    fw, fh = fr.get_size()
                    screen.blit(fr, (rect.x + (rect.w - fw)//2, rect.y + (rect.h - fh)//2))
            else:
                pygame.draw.circle(screen, COLOR_MONSTER, rect.center, max(4, rect.w // 3))

        # runner
        if draw_rc:
            rect = to_rect(draw_rc, CELL, MX, MY, camx, camy)
            fr = get_frame(dt)
            if fr:
                fw, fh = fr.get_width(), fr.get_height()
                screen.blit(fr, (rect.x + (rect.w - fw)//2, rect.y + (rect.h - fh)//2))

        draw_grid_lines(screen, ROWS, COLS, CELL, MX, MY, camx, camy)
        screen.set_clip(None)

        # SIDEBAR
        pygame.draw.rect(screen, S.BOTTOM_BG, RIGHT_RECT)
        pygame.draw.line(screen, S.BTN_BR, (RIGHT_X, S.TOP_PANEL_H), (RIGHT_X, S.HEIGHT - S.BOTTOM_PANEL_H), 1)
        screen.blit(sidebar_title, (RIGHT_X + SIDEPAD, S.TOP_PANEL_H + 10))
        screen.blit(ui_font.render("Size", True, S.TEXT), size_label_pos); drp_size.draw_head(screen)
        screen.blit(ui_font.render("W (weight)", True, S.TEXT), weight_label_pos); drp_w.draw_head(screen)

        # History title + button
        pygame.draw.line(screen, S.BTN_BR, (RIGHT_X+SIDEPAD, hist_sep_y), (RIGHT_X+RIGHT_W-SIDEPAD, hist_sep_y), 1)
        screen.blit(ui_font.render("History", True, S.TEXT), hist_label_pos)
        btn_hist.draw(screen)

        # TOOLBOX
        screen.blit(ui_font.render("Toolbox", True, S.TEXT), tools_label_pos)
        for b in tool_buttons:
            if b._tool == current_tool:
                b.bg = (200, 200, 200)
                b.border = (100, 100, 100)
            else:
                b.bg = (245, 247, 250)
                b.border = (170, 176, 190)
            b.draw(screen)
            # draw icons for Start/Goal/Key/Wall (skip Monster)
            if b._tool != Tool.MONSTER:
                ic = tool_icons.get(b._tool)
                if ic:
                    ix = b.rect.x + 10
                    iy = b.rect.y + (b.rect.height - 18) // 2
                    screen.blit(ic, (ix, iy))

        # Info lines
        def qty_str(t):
            v = inventory_left[t]
            return "∞" if v == float("inf") else f"{int(v)}/1"
        info_y = tool_buttons[-1].rect.bottom + 10
        info_x = RIGHT_X + SIDEPAD
        lines = [
            f"Start:   {qty_str(Tool.START)}",
            f"Goal:    {qty_str(Tool.GOAL)}",
            f"Key:     {qty_str(Tool.KEY)}",
            f"Wall:    {qty_str(Tool.WALL)}",
            f"Monster: {qty_str(Tool.MONSTER)}",
            f"Monster cost: +{int(getattr(S,'MONSTER_COST',0))}",
            "",
            "LMB: place by tool",
            "RMB: remove • RMB drag (Wall only)",
            "Shift+RMB: erase wall",
        ]
        for line in lines:
            surf = tiny_font.render(line, True, (90,95,105))
            screen.blit(surf, (info_x, info_y))
            info_y += tiny_font.get_height() + 4

        # BOTTOM BAR
        pygame.draw.rect(screen, S.BOTTOM_BG, (0, S.HEIGHT - S.BOTTOM_PANEL_H, S.WIDTH, S.BOTTOM_PANEL_H))
        control_box.draw(screen); dir_box.draw(screen)
        btn_prev.draw(screen); btn_play.draw(screen, active_override=playing); btn_next.draw(screen)
        btn_4dir.draw(screen); btn_8dir.draw(screen)
        drp_heur.draw_head(screen)

        explored, path_steps = (0,0)
        if states and states[-1].get("found"):
            explored, path_steps = compute_metrics(
                states,
                monsters=monsters,
                monster_extra_cost=float(getattr(S, "MONSTER_COST", 0.0))
            )

        status = f"Map {ROWS}×{COLS} | Steps {max(idx,0)}/{max(len(states)-1,0)} | Dir {'8-dir' if S.EIGHT_DIR else '4-dir'} | H {getattr(S,'HEURISTIC','manhattan')} | W {getattr(S,'WEIGHT',1.0):.2f} | Path {path_steps:.2f} | Explored {explored} | t {last_build_runtime_ms:.1f}ms"
        stsurf = ui_font.render(status, True, S.TEXT)
        screen.blit(stsurf, (20, S.HEIGHT - S.BOTTOM_PANEL_H + BTN_H + 20))

        # ---- modal dropdown ----
        opened = None
        for dd in (drp_size, drp_w, drp_heur):
            if dd.opened: opened = dd; break
        if opened:
            overlay = pygame.Surface((S.WIDTH, S.HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 60))
            screen.blit(overlay, (0, 0))
            opened.draw_head(screen); opened.draw_menu(screen)

        # ===== MONSTER PICKER MODAL =====
        if monster_picker_open and mp_layout:
            dim = pygame.Surface((S.WIDTH, S.HEIGHT), pygame.SRCALPHA)
            dim.fill((0, 0, 0, 120))
            screen.blit(dim, (0, 0))

            MP_RECT = mp_layout["MP_RECT"]
            close_rect = mp_layout["close_rect"]
            cells = mp_layout["cells"]

            pygame.draw.rect(screen, (250, 251, 253), MP_RECT, border_radius=12)
            pygame.draw.rect(screen, (170, 176, 190), MP_RECT, 1, border_radius=12)

            title = title_font.render("Choose Monster Type", True, S.TEXT)
            screen.blit(title, (MP_RECT.x + 16, MP_RECT.y + 12))

            # Close button
            pygame.draw.rect(screen, (235, 238, 242), close_rect, border_radius=8)
            pygame.draw.rect(screen, (170, 176, 190), close_rect, 1, border_radius=8)
            close_txt = ui_font.render("Close", True, (30,33,40))
            screen.blit(close_txt, (close_rect.centerx - close_txt.get_width()//2,
                                    close_rect.centery - close_txt.get_height()//2))

            # grid 2x2
            for rect, opt in cells:
                is_selected = False
                if opt["fname"] in variant_name_to_index:
                    is_selected = (monster_choice_index == variant_name_to_index[opt["fname"]])
                pygame.draw.rect(screen, (235, 238, 242), rect, border_radius=10)
                pygame.draw.rect(screen, (120, 160, 255) if is_selected else (170,176,190),
                                 rect, 2, border_radius=10)

                thumb_rect = pygame.Rect(rect.x+12, rect.y+12, rect.w-24, rect.h-60)
                try:
                    img = pygame.image.load(asset_path(opt["fname"])).convert_alpha()
                    iw, ih = img.get_size()
                    sc = min(thumb_rect.w/max(1, iw), thumb_rect.h/max(1, ih))
                    img2 = pygame.transform.scale(img, (max(1,int(iw*sc)), max(1,int(ih*sc))))
                    screen.blit(img2, (thumb_rect.centerx - img2.get_width()//2,
                                       thumb_rect.centery - img2.get_height()//2))
                except Exception:
                    pass

                lbl = f"{opt['label']} (+{opt['cost']})"
                surf = ui_font.render(lbl, True, (50,54,62))
                screen.blit(surf, (rect.centerx - surf.get_width()//2, rect.bottom - 36))

        # ===== HISTORY MODAL =====
        if hist_open:
            dim = pygame.Surface((S.WIDTH, S.HEIGHT), pygame.SRCALPHA)
            dim.fill((0, 0, 0, 120)); screen.blit(dim, (0, 0))

            HIST_RECT = get_history_rect()

            pygame.draw.rect(screen, (250, 251, 253), HIST_RECT, border_radius=12)
            pygame.draw.rect(screen, (170, 176, 190), HIST_RECT, 1, border_radius=12)

            title = title_font.render("Run History", True, S.TEXT)
            screen.blit(title, (HIST_RECT.x + 16, HIST_RECT.y + 12))

            close_rect = pygame.Rect(HIST_RECT.right - 86, HIST_RECT.y + 10, 70, 28)
            pygame.draw.rect(screen, (235, 238, 242), close_rect, border_radius=8)
            pygame.draw.rect(screen, (170, 176, 190), close_rect, 1, border_radius=8)
            close_txt = ui_font.render("Close", True, (30,33,40))
            screen.blit(close_txt, (close_rect.centerx - close_txt.get_width()//2,
                                    close_rect.centery - close_txt.get_height()//2))
            if pygame.mouse.get_pressed()[0] and close_rect.collidepoint(pygame.mouse.get_pos()):
                hist_open = False
                hist_selected.clear(); hist_show_compare = False

            list_pad = 16
            content = pygame.Rect(HIST_RECT.x + list_pad,
                                  HIST_RECT.y + 56,
                                  HIST_RECT.w - 2*list_pad,
                                  HIST_RECT.h - 56 - list_pad - 48)

            pygame.draw.rect(screen, (245, 247, 250), content, border_radius=8)
            pygame.draw.rect(screen, (210, 214, 220), content, 1, border_radius=8)

            if not hist_show_compare:
                screen.set_clip(content)
                yy = content.y + 10
                lines = history[-200:]
                line_h = ui_font.get_height() + 8
                for i, item in enumerate(reversed(lines)):
                    label = item.get("label","(Empty)")
                    real_idx = len(history) - 1 - i
                    selected = (real_idx in hist_selected)
                    row_rect = pygame.Rect(content.x + 10, yy - 2, content.w - 20, line_h)
                    if selected:
                        hl = pygame.Surface((row_rect.w, row_rect.h), pygame.SRCALPHA)
                        hl.fill((80,120,255,60)); screen.blit(hl, (row_rect.x, row_rect.y))
                    surf = ui_font.render(label, True, (70,74,82))
                    screen.blit(surf, (content.x + 14, yy))
                    yy += line_h
                    if yy > content.bottom: break
                screen.set_clip(None)

                btn_y = content.bottom + 10
                btn_w, btn_h = 140, 32
                gap = 14
                btn_compare = pygame.Rect(HIST_RECT.x + list_pad, btn_y, btn_w, btn_h)
                btn_reset   = pygame.Rect(btn_compare.right + gap, btn_y, btn_w, btn_h)

                ok_to_compare = (len(hist_selected) >= 2)

                pygame.draw.rect(screen, (235, 238, 242), btn_compare, border_radius=8)
                pygame.draw.rect(screen, (170, 176, 190), btn_compare, 1, border_radius=8)
                txt = "Compare" if ok_to_compare else "Compare (disabled)"
                col = (30,33,40) if ok_to_compare else (150,150,150)
                screen.blit(ui_font.render(txt, True, col),
                            (btn_compare.centerx - ui_font.size(txt)[0]//2,
                             btn_compare.centery - ui_font.get_height()//2))

                pygame.draw.rect(screen, (235, 238, 242), btn_reset, border_radius=8)
                pygame.draw.rect(screen, (170, 176, 190), btn_reset, 1, border_radius=8)
                t2 = "Reset Sel."
                screen.blit(ui_font.render(t2, True, (30,33,40)),
                            (btn_reset.centerx - ui_font.size(t2)[0]//2,
                             btn_reset.centery - ui_font.get_height()//2))

                hint = f"Selected: {len(hist_selected)}"
                screen.blit(tiny_font.render(hint, True, (90,95,105)),
                            (btn_reset.right + 16, btn_y + 6))

            else:
                pygame.draw.rect(screen, (245, 247, 250), content, border_radius=8)
                pygame.draw.rect(screen, (210, 214, 220), content, 1, border_radius=8)

                entries = [history[i] for i in sorted(hist_selected)]

                def score(ent):
                    return (
                        round(float(ent.get("cost", float("inf"))), 4),
                        int(ent.get("explored", 10**9)),
                        float(ent.get("runtime_ms", float("inf")))
                    )

                best_idx = None
                if entries:
                    best_idx = min(range(len(entries)), key=lambda i: score(entries[i]))

                headers = ["#", "HEURISTIC", "WEIGHT", "DIR", "EXPLORED", "COST", "RUNTIME"]

                def _col_pos(perc):
                    return int(content.x + 16 + (content.w - 32) * perc)

                col_x = [_col_pos(p) for p in (0.02, 0.10, 0.32, 0.46, 0.62, 0.76, 0.90)]
                row_h = ui_font.get_height() + 18

                head_y = content.y + 10
               
                header_rect = pygame.Rect(content.x + 8, head_y - 6, content.w - 16, row_h)
                pygame.draw.rect(screen, (110, 120, 132), header_rect, border_radius=8)
                pygame.draw.rect(screen, (170, 176, 190), header_rect, 1, border_radius=8)
                for cx, name in zip(col_x, headers):
                    screen.blit(ui_font.render(name, True, (240, 244, 248)), (cx, head_y))

                y2 = head_y + row_h + 4
                rows_to_draw = max(3, len(entries))
                for i in range(rows_to_draw):
                    row_rect = pygame.Rect(content.x + 8, y2 - 6, content.w - 16, row_h)

                    if i == best_idx:
                        pygame.draw.rect(screen, (205, 235, 210), row_rect, border_radius=8)
                        pygame.draw.rect(screen, (160, 200, 170), row_rect, 1, border_radius=8)
                    else:
                        pygame.draw.rect(screen, (255, 255, 255), row_rect, border_radius=8)
                        pygame.draw.rect(screen, (210, 214, 220), row_rect, 1, border_radius=8)

                    if i < len(entries):
                        ent = entries[i]
                        vals = [
                            str(i+1),
                            str(ent.get("heuristic","")),
                            f"{ent.get('weight',0):.2f}",
                            "8-dir" if ent.get("eight_dir") else "4-dir",
                            str(ent.get("explored",0)),
                            f"{ent.get('cost',0.0):.2f}",
                            f"{ent.get('runtime_ms',0.0):.1f} ms",
                        ]
                        for cx, v in zip(col_x, vals):
                            screen.blit(ui_font.render(v, True, (60,64,72)), (cx, y2))
                        if i == best_idx:
                            badge = tiny_font.render("★ BEST", True, (30, 90, 50))
                            screen.blit(badge, (col_x[-1] + 80, y2 + 2))
                    y2 += row_h + 4

                btn_y3 = content.bottom + 10
                btn_w3, btn_h3 = 140, 32
                btn_back = pygame.Rect(HIST_RECT.x + list_pad, btn_y3, btn_w3, btn_h3)
                pygame.draw.rect(screen, (235, 238, 242), btn_back, border_radius=8)
                pygame.draw.rect(screen, (170, 176, 190), btn_back, 1, border_radius=8)
                tback = "Back"
                screen.blit(ui_font.render(tback, True, (30,33,40)),
                            (btn_back.centerx - ui_font.size(tback)[0]//2,
                             btn_back.centery - ui_font.get_height()//2))

        pygame.display.flip()

    pygame.quit(); sys.exit()

if __name__ == "__main__":
    run()
