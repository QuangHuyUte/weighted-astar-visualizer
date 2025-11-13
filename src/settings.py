# =========================
# settings.py (3-tier layout)
# =========================

# --- Window & FPS ---
WIDTH, HEIGHT = 1120, 820   
TOP_PANEL_H = 72
BOTTOM_PANEL_H = 128
FPS = 60

# --- UI fonts ---
UI_FONT_NAME    = "Segoe UI"
UI_FONT_SIZE    = 18
HELP_FONT_SIZE  = 16
TITLE_FONT_SIZE = 22

# --- Grid defaults (khởi tạo) ---
# Lưu ý: main.py có combobox Size (S/M/L/XL) để đổi map runtime,
# nhưng vẫn nên giữ mặc định ở đây cho các module khác có thể dùng.
ROWS, COLS = 16, 16

# --- Algorithm defaults ---
EIGHT_DIR  = False
# "manhattan" | "euclidean" | "octile" | "chebyshev"
HEURISTIC  = "manhattan"
MODE       = "astar"
WEIGHT     = 1.0           # W=1.0 => A* chuẩn; >1.0 => Weighted A*
AUTO_STEP_EVERY_MS = 110   # thời gian auto step (ms)

# --- Colors ---
WHITE = (249, 250, 252)
BLACK = (28, 28, 30)
GRIDC = (205, 208, 215)

GREEN = (52, 199, 89)   # start
RED   = (255, 69, 58)   # goal

OPEN   = (255, 179, 64)   # ô trong open set (cam)
CLOSED = (88, 148, 255)   # ô trong closed set (xanh)
PATHC  = (255, 214, 10)   # đường đi (vàng)
TEXT   = (33, 37, 41)

TOP_BG    = (242, 244, 247)   # nền top bar
BOTTOM_BG = (245, 247, 250)   # nền bottom bar

BTN_BG     = (255, 255, 255)
BTN_BR     = (210, 214, 220)
BTN_HL     = (235, 238, 242)
BTN_ACTIVE = (220, 242, 220)

# --- Overlay alpha ---
OPEN_ALPHA   = 120
CLOSED_ALPHA = 120
PATH_ALPHA   = 150
CURR_ALPHA   = 165

# =========================
# SPRITESHEETS (IDLE + WALK)
# =========================
# Đặt file sprite vào thư mục assets/:
#   assets/runner_idle.png
#   assets/runner_walk.png
IDLE_FILE = "runner_idle.png"
WALK_FILE = "runner_walk.png"

# Kích thước 1 frame trong sheet
FRAME_W = 48
FRAME_H = 96

# mapping hàng theo hướng (tuỳ sheet của bạn)
ROW_DOWN  = 0
ROW_LEFT  = 1
ROW_RIGHT = 2
ROW_UP    = 3

# Số cột (frame) trong mỗi sheet
# Nếu sheet của bạn khác, chỉnh lại cho đúng:
IDLE_COLS = 12    # ví dụ: 4 frame idle
WALK_COLS = 12    # ví dụ: 6 frame walk

# FPS cho animation
IDLE_FPS  = 12
WALK_FPS  = 12

# Cách scale sprite theo ô:
# - "fit_cell": ép vừa cả ô (vuông)
# - "fit_height": cao bằng ô, rộng theo tỉ lệ (khuyên dùng cho nhân vật 64x128)
# - "fit_width": rộng bằng ô, cao theo tỉ lệ
SCALE_MODE = "fit_height"
SCALE_MULT = 1.1  # nhân thêm một chút cho nổi bật (1.0 nếu muốn vừa khít)

# Vẽ nhân vật tại node nào
DRAW_FOR_CURRENT = True   # chạy theo node current khi đang visualize
DRAW_FOR_CURSOR  = False  # không vẽ theo vị trí chuột

BLOCK_CORNER_CUTTING = True



# =========================
# MONSTERS (idle/flight)
# =========================
# Đặt file dưới thư mục assets/ (đổi tên theo file bạn có).
# Mỗi phần tử: (filename, num_cols)
MONSTER_SPECS = [
    ("monster_mushroom_idle.png", 4),
    ("monster_goblin_idle.png",   4),
    ("monster_bat_flight.png",    8),  # con bay có 8 frame
    ("monster_skeleton_idle.png", 4),
]

# Tốc độ animation mặc định (FPS)
MONSTER_FPS = 8

# Quy tắc scale riêng cho quái (để luôn gọn trong 1 ô)
MONSTER_SCALE_MODE = "fit_cell"   # "fit_cell" khuyên dùng cho quái
MONSTER_SCALE_MULT = 3         # <1.0 để không tràn ô


# Extra cost when stepping into a monster cell
MONSTER_COST = 5.0