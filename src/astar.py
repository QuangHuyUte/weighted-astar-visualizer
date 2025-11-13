# astar.py
import math
import heapq
from . import settings as S


def _heuristic(a, b, kind: str):
    ax, ay = a
    bx, by = b
    dx = abs(ax - bx)
    dy = abs(ay - by)
    if kind == "manhattan":
        # chuẩn cho 4-dir (chỉ ngang/dọc)
        return dx + dy
    elif kind == "euclidean":
        # chuẩn cho 8-dir với cost chéo = sqrt(2)
        return math.hypot(dx, dy)
    elif kind == "octile":
        # chuẩn cho 8-dir khi chéo cost = sqrt(2)
        # công thức tương đương: dx + dy + (sqrt(2) - 2) * min(dx, dy)
        return max(dx, dy) + (math.sqrt(2.0) - 1.0) * min(dx, dy)
    elif kind == "chebyshev":
        # chuẩn cho 8-dir khi mọi bước (kể cả chéo) cost = 1
        return max(dx, dy)
    else:
        return 0.0


def _neighbors(r, c, rows, cols, grid, eight_dir: bool, diag_cost_is_one: bool,
               monsters=None, monster_extra_cost=0.0):
    """
    Sinh láng giềng (nr, nc, step_cost).
    - Tường (grid==1) bị chặn.
    - Nếu eight_dir=True: có thêm bước chéo; chặn cắt góc.
    - Nếu (nr,nc) là ô quái vật -> cộng thêm monster_extra_cost vào step_cost.
    """
    # 4 hướng cơ bản
    base = [(-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0)]
    if eight_dir:
        diag = 1.0 if diag_cost_is_one else math.sqrt(2.0)
        base += [(-1, -1, diag), (-1, 1, diag), (1, -1, diag), (1, 1, diag)]

    for dr, dc, cost in base:
        nr, nc = r + dr, c + dc
        if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] != 1:
            # chặn đi chéo xuyên góc
            if eight_dir and dr != 0 and dc != 0:
                if grid[r][c + dc] == 1 or grid[r + dr][c] == 1:
                    continue
            step_cost = cost
            if monsters and (nr, nc) in monsters:
                step_cost += float(monster_extra_cost)
            yield (nr, nc, step_cost)


def _reconstruct_path(came_from, start, cur):
    path = []
    n = cur
    while n in came_from:
        path.append(n)
        n = came_from[n]
    path.append(start)
    path.reverse()
    return path


def generate_states(grid, start, goal,
                    heuristic_kind="manhattan",
                    eight_dir=False,
                    mode="astar",
                    weight=1.0,
                    monsters=None,
                    monster_extra_cost=0.0):
    """
    Trả về các trạng thái (generator) để visualize.
    Mỗi lần yield một dict:
      {
        "open":   list[(r,c)],
        "closed": list[(r,c)],
        "path":   list[(r,c)],  # path tốt nhất tới 'current'
        "current":(r,c) | None,
        "found":  bool
      }
    f = g + W * h  (W = weight; W=1 là A* thường).

    Thêm:
    - monsters: set[(r,c)] các ô có quái vật
    - monster_extra_cost: float, phụ phí khi BƯỚC VÀO ô quái vật
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0

    start = tuple(start)
    goal  = tuple(goal)

    # Heuristic function
    h = lambda a, b: _heuristic(a, b, heuristic_kind)

    # Chi phí chéo tự động theo heuristic:
    # - Chebyshev  => chéo = 1.0
    # - Ngược lại  => chéo = sqrt(2) (nếu eight_dir=True)
    diag_cost_is_one = (eight_dir and heuristic_kind == "chebyshev")

    open_heap = []
    came_from = {}
    g_score   = {start: 0.0}
    f_start   = g_score[start] + weight * h(start, goal)
    heapq.heappush(open_heap, (f_start, 0, start))
    open_set = {start}
    closed   = set()

    step_id = 0

    while open_heap:
        _, _, current = heapq.heappop(open_heap)
        if current not in open_set:
            continue
        open_set.remove(current)
        closed.add(current)

        # path tốt nhất tới current
        path = _reconstruct_path(came_from, start, current) if current != start else [start]
        found = (current == goal)

        yield {
            "open":    list(open_set),
            "closed":  list(closed),
            "path":    path,
            "current": current,
            "found":   found
        }
        if found:
            return

        cr, cc = current
        for nr, nc, step_cost in _neighbors(cr, cc, rows, cols, grid,
                                            eight_dir, diag_cost_is_one,
                                            monsters, monster_extra_cost):
            neighbor = (nr, nc)
            if neighbor in closed:
                continue
            tentative_g = g_score[current] + step_cost
            if tentative_g < g_score.get(neighbor, float("inf")):
                came_from[neighbor] = current
                g_score[neighbor]   = tentative_g
                f_score = tentative_g + weight * h(neighbor, goal)
                heapq.heappush(open_heap, (f_score, step_id, neighbor))
                open_set.add(neighbor)
        step_id += 1

    # không tìm thấy
    yield {
        "open":    list(open_set),
        "closed":  list(closed),
        "path":    [],
        "current": None,
        "found":   False
    }
    return
