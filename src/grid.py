# grid.py
import csv, json, os

def blank(rows, cols):
    return [[0 for _ in range(cols)] for _ in range(rows)]

def save_map_csv_json(grid, start, goal, dir_path):
    os.makedirs(dir_path, exist_ok=True)
    csv_path = os.path.join(dir_path, "map.csv")
    json_path = os.path.join(dir_path, "map.json")
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerows(grid)
    meta = {"rows": len(grid), "cols": len(grid[0]), "start": list(start), "goal": list(goal)}
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return csv_path, json_path

def load_map_csv_json(dir_path, fallback_rows, fallback_cols):
    csv_path = os.path.join(dir_path, "map.csv")
    json_path = os.path.join(dir_path, "map.json")
    if not os.path.exists(csv_path):
        return blank(fallback_rows, fallback_cols), (0,0), (fallback_rows-1, fallback_cols-1)
    with open(csv_path, newline="") as f:
        rows = list(csv.reader(f))
    rows = [list(map(int, r)) for r in rows]
    nr, nc = len(rows), len(rows[0]) if rows else (0)
    out = [[0]*fallback_cols for _ in range(fallback_rows)]
    for r in range(min(fallback_rows, nr)):
        for c in range(min(fallback_cols, nc)):
            out[r][c] = 1 if rows[r][c] else 0
    start = (0,0); goal = (fallback_rows-1, fallback_cols-1)
    if os.path.exists(json_path):
        try:
            with open(json_path, encoding="utf-8") as f:
                meta = json.load(f)
            s = tuple(meta.get("start", start))
            g = tuple(meta.get("goal", goal))
            if 0 <= s[0] < fallback_rows and 0 <= s[1] < fallback_cols: start = s
            if 0 <= g[0] < fallback_rows and 0 <= g[1] < fallback_cols: goal = g
        except Exception:
            pass
    return out, start, goal
