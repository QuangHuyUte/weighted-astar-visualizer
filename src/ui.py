# ui.py
import pygame

class Button:
    def __init__(self, rect, label, font, toggle=False):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.font = font
        self.toggle = toggle
        self.active = False
        self._pressed = False

    def clicked(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self._pressed = True
                return False
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._pressed and self.rect.collidepoint(event.pos):
                self._pressed = False
                if self.toggle:
                    self.active = not self.active
                return True
            self._pressed = False
        return False

    def draw(self, screen, active_override=None):
        active = self.active if active_override is None else active_override
        bg = (230, 233, 240) if not active else (205, 215, 235)
        br = (170, 176, 190)
        txtc = (30, 33, 40)
        pygame.draw.rect(screen, bg, self.rect, border_radius=8)
        pygame.draw.rect(screen, br, self.rect, 1, border_radius=8)
        surf = self.font.render(self.label, True, txtc)
        screen.blit(surf, (self.rect.centerx - surf.get_width()//2,
                           self.rect.centery - surf.get_height()//2))

class Segmented:
    def __init__(self, rect, items, font, selected_index=0):
        self.rect = pygame.Rect(rect)
        self.items = list(items)
        self.font = font
        self.selected = int(selected_index)

    def handle(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                n = len(self.items)
                w = self.rect.w // n
                idx = (event.pos[0] - self.rect.x) // w
                idx = max(0, min(n-1, idx))
                changed = (idx != self.selected)
                self.selected = idx
                return changed
        return False

    def draw(self, screen):
        bg = (235, 237, 244)
        br = (170, 176, 190)
        txt = (30, 33, 40)
        sel = (205, 215, 235)
        pygame.draw.rect(screen, bg, self.rect, border_radius=8)
        pygame.draw.rect(screen, br, self.rect, 1, border_radius=8)
        n = len(self.items)
        w = self.rect.w // n
        for i, it in enumerate(self.items):
            r = pygame.Rect(self.rect.x + i*w, self.rect.y,
                            w if i < n-1 else self.rect.w - (n-1)*w, self.rect.h)
            if i == self.selected:
                pygame.draw.rect(screen, sel, r, border_radius=8)
            surf = self.font.render(str(it), True, txt)
            screen.blit(surf, (r.centerx - surf.get_width()//2,
                               r.centery - surf.get_height()//2))

class Dropdown:
    """Combobox: click mở/đóng, tự bung LÊN nếu thiếu chỗ bên dưới.
       draw_head(): vẽ hộp đóng
       draw_menu(): vẽ danh sách (gọi sau cùng để nổi lên trên)"""
    def __init__(self, rect, items, font, selected_index=0, placeholder=None):
        self.rect = pygame.Rect(rect)
        self.items = list(items)
        self.font = font
        self.selected = int(selected_index)
        self.opened = False
        self.placeholder = placeholder
        self.item_h = self.rect.h
        self.max_visible = min(8, len(self.items))
        self._open_up = False  # quyết định bung lên/xuống lúc mở
        self.scroll_offset = 0

    def handle(self, event):
        changed = False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.opened:
                lr = self._list_rect()
                if lr.collidepoint(event.pos):
                    # click chọn item trong cửa sổ đang hiển thị (có offset)
                    idx_in_view = (event.pos[1] - lr.y) // self.item_h
                    start = self.scroll_offset
                    end   = min(start + self.max_visible, len(self.items))
                    idx   = start + idx_in_view
                    if start <= idx < end:
                        if idx != self.selected:
                            self.selected = idx
                            changed = True
                        self.opened = False
                else:
                    # click ra ngoài -> đóng
                    self.opened = False
            else:
                if self.rect.collidepoint(event.pos):
                    # quyết định mở lên/xuống như cũ
                    surf = pygame.display.get_surface()
                    H = surf.get_height() if surf else (self.rect.bottom + 200)
                    list_h = self.item_h * min(self.max_visible, len(self.items))
                    space_below = H - (self.rect.bottom + 4)
                    self._open_up = (space_below < list_h + 6)
                    self.opened = True
                    # căn offset sao cho mục đang chọn nằm trong khung
                    if len(self.items) > self.max_visible:
                        self.scroll_offset = max(0, min(self.selected - (self.max_visible//2),
                                                        len(self.items) - self.max_visible))
                    else:
                        self.scroll_offset = 0

        # 👉 thêm xử lý lăn chuột
        elif event.type == pygame.MOUSEWHEEL and self.opened:
            lr = self._list_rect()
            # chỉ cuộn khi con trỏ đang ở trong khu vực menu
            mx, my = pygame.mouse.get_pos()
            if lr.collidepoint((mx, my)):
                if len(self.items) > self.max_visible:
                    self.scroll_offset -= event.y  # event.y: +1 lăn lên, -1 lăn xuống
                    self.scroll_offset = max(0, min(self.scroll_offset,
                                                    len(self.items) - self.max_visible))

        elif event.type == pygame.KEYDOWN and self.opened:
            if event.key in (pygame.K_ESCAPE, pygame.K_RETURN):
                self.opened = False
        return changed


    def _list_rect(self):
        h = self.item_h * min(self.max_visible, len(self.items))
        if self._open_up:
            return pygame.Rect(self.rect.x, self.rect.y - 4 - h, self.rect.w, h)
        return pygame.Rect(self.rect.x, self.rect.bottom + 4, self.rect.w, h)

    # --- vẽ ---
    def draw_head(self, screen):
        bg = (235, 237, 244)
        br = (170, 176, 190)
        txt = (30, 33, 40)
        pygame.draw.rect(screen, bg, self.rect, border_radius=8)
        pygame.draw.rect(screen, br, self.rect, 1, border_radius=8)
        label = self.items[self.selected] if 0 <= self.selected < len(self.items) else (self.placeholder or "")
        surf = self.font.render(str(label), True, txt)
        screen.blit(surf, (self.rect.x + 10, self.rect.centery - surf.get_height()//2))
        # caret ▼
        pygame.draw.polygon(screen, br, [
            (self.rect.right - 16, self.rect.centery - 3),
            (self.rect.right - 8,  self.rect.centery - 3),
            (self.rect.right - 12, self.rect.centery + 3),
        ])

    def draw_menu(self, screen):
        if not self.opened:
            return
        lr = self._list_rect()
        # bóng + hộp
        shadow = pygame.Surface((lr.w, lr.h), pygame.SRCALPHA); shadow.fill((0,0,0,30))
        screen.blit(shadow, (lr.x+2, lr.y+2))
        pygame.draw.rect(screen, (250, 250, 252), lr, border_radius=6)
        pygame.draw.rect(screen, (170,176,190), lr, 1, border_radius=6)

        sel = (205, 215, 235)
        txt = (30, 33, 40)

        # dải hiển thị theo offset
        start = self.scroll_offset
        end   = min(start + self.max_visible, len(self.items))
        for i, it in enumerate(self.items[start:end]):
            r = pygame.Rect(lr.x, lr.y + i*self.item_h, lr.w, self.item_h)
            real_idx = start + i
            if real_idx == self.selected:
                pygame.draw.rect(screen, sel, r, border_radius=4)
            s = self.font.render(str(it), True, txt)
            screen.blit(s, (r.x + 10, r.centery - s.get_height()//2))

        # (tuỳ chọn) vẽ thanh scroll mảnh ở cạnh phải khi có thể cuộn
        if len(self.items) > self.max_visible:
            bar_area_h = lr.h
            # tỉ lệ: bao nhiêu mục hiển thị / tổng mục
            ratio = self.max_visible / float(len(self.items))
            bar_h = max(12, int(bar_area_h * ratio))
            # vị trí: offset hiện tại / (tổng cuộn được)
            travel = bar_area_h - bar_h
            if len(self.items) - self.max_visible > 0:
                bar_y = lr.y + int(travel * (self.scroll_offset / (len(self.items) - self.max_visible)))
            else:
                bar_y = lr.y
            bar_x = lr.right - 6  # mỏng 4px
            pygame.draw.rect(screen, (210, 214, 220), (bar_x-1, lr.y+2, 4, lr.h-4), border_radius=2)
            pygame.draw.rect(screen, (170, 176, 190), (bar_x-1, bar_y, 4, bar_h), border_radius=2)


    # giữ tương thích cũ nếu code gọi .draw()
    def draw(self, screen):
        self.draw_head(screen)
        self.draw_menu(screen)


class PanelBox:
    """Khung nhóm nút/tab có tiêu đề nhỏ phía trên."""
    def __init__(self, rect, title, font):
        self.rect = pygame.Rect(rect)
        self.title = title
        self.font = font

    def draw(self, screen):
        bg = (242, 244, 250)
        br = (186, 192, 206)
        txt = (68, 70, 80)
        pygame.draw.rect(screen, bg, self.rect, border_radius=10)
        pygame.draw.rect(screen, br, self.rect, 1, border_radius=10)
        cap = self.font.render(self.title, True, txt)
        screen.blit(cap, (self.rect.x + 10, self.rect.y - cap.get_height()))
