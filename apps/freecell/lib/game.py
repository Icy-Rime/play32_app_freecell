from freecell import random_seed, FreeCell, split_card, CARD_EMPTY
from utime import sleep_ms
from play32hw.cpu import cpu_speed_context, FAST, VERY_SLOW
from machine import lightsleep
import hal_screen, hal_keypad
import tiles

TILES_BOTTOM = b"\x04\x05"
TILES_CURSOR_TOP = b"\x14\x14"
TILES_CURSOR_BOTTOM = b"\x15\x15"
TILES_EMPTY_SPACE = b"\x13\x13"

fc = FreeCell()
table_data = bytearray(800) # 16 * ? tile_id
last_screen = bytearray() # last screen content, onle 16 * ? tile_id
current_screen = bytearray()
screen_lines = 0
scene_lines = 0
view_offset = 0
selected = -1
cursor = 0

def init(app_path):
    global last_screen, current_screen, screen_lines
    tiles.init(app_path, hal_screen.get_format())
    screen_lines = hal_screen.get_size()[1] // 8
    last_screen = bytearray(16 * screen_lines)
    current_screen = bytearray(16 * screen_lines)
    for i in range(len(last_screen)):
        last_screen[i] = 0xFF

def get_card_tiles(card):
    if card == CARD_EMPTY:
        return bytes([22, 23])
    else:
        typ, val = split_card(card)
        return bytes([typ, val + 6])

def update_table():
    # render the full table
    global scene_lines, view_offset
    # render top cursors
    lines = 0
    base_off = 0
    for i in range(8):
        off = base_off + i * 2
        table_data[off : off + 2] = TILES_EMPTY_SPACE
    if cursor >= 8:
        off = base_off + (cursor - 8) * 2
        table_data[off : off + 2] = TILES_CURSOR_TOP
    if selected >= 8:
        off = base_off + (selected - 8) * 2
        table_data[off : off + 2] = TILES_CURSOR_BOTTOM
    # render freecell and recvcell
    lines = 1
    base_off = lines * 16
    for i in range(4):
        off = base_off + i * 2
        card = fc.get_free_cell_card(i)
        table_data[off : off + 2] = get_card_tiles(card)
        off += 8
        card = fc.get_recv_cell_card(i)
        table_data[off : off + 2] = get_card_tiles(card)
    lines = 2
    base_off = lines * 16
    for i in range(8):
        off = base_off + i * 2
        table_data[off : off + 2] = TILES_BOTTOM
    lines = 3
    base_off = lines * 16
    for i in range(4):
        off = base_off + i * 2
        table_data[off : off + 2] = TILES_EMPTY_SPACE
        off += 8
        table_data[off : off + 2] = TILES_CURSOR_BOTTOM
    # render table
    cols_size = [ fc.get_col_info(col)[2] for col in range(8) ]
    for l in range(max(cols_size) + 1):
        lines += 1
        base_off = lines * 16
        for col in range(8):
            off = base_off + col * 2
            if l < cols_size[col]:
                card = fc.get_card_at(col, l)
                table_data[off : off + 2] = get_card_tiles(card)
            elif l == cols_size[col]:
                table_data[off : off + 2] = TILES_BOTTOM
            else:
                table_data[off : off + 2] = TILES_EMPTY_SPACE
    # render bottom cursors
    lines += 1
    base_off = lines * 16
    for i in range(8):
        off = base_off + i * 2
        table_data[off : off + 2] = TILES_EMPTY_SPACE
    if cursor >= 0 and cursor < 8:
        off = base_off + cursor * 2
        table_data[off : off + 2] = TILES_CURSOR_BOTTOM
    if selected >= 0 and selected < 8:
        off = base_off + selected * 2
        table_data[off : off + 2] = TILES_CURSOR_TOP
    # update scene and screen
    scene_lines = lines + 1
    while scene_lines < screen_lines:
        lines += 1
        base_off = lines * 16
        for i in range(8):
            off = base_off + i * 2
            table_data[off : off + 2] = TILES_EMPTY_SPACE
        scene_lines += 1
    if view_offset + screen_lines > scene_lines:
        view_offset = scene_lines - screen_lines

def update_screen():
    base_off = view_offset * 16
    current_screen[0 : 16 * screen_lines] = table_data[base_off : 16 * screen_lines + base_off]

def focus_on_cursor():
    global view_offset
    if cursor < 8:
        view_offset = scene_lines - screen_lines
    else:
        view_offset = 0

def render(force=False):
    frame = hal_screen.get_framebuffer()
    scr_w, scr_h = hal_screen.get_size()
    base_x = (scr_w - (16 * 8)) // 2
    base_y = (scr_h % 8) // 2
    changed = False
    for row in range(screen_lines):
        for col in range(16):
            offset = (row * 16) + col
            old_tid = last_screen[offset]
            tid = current_screen[offset]
            if old_tid != tid or force:
                t = tiles.get_tile(tid)
                frame.blit(t, base_x + col * 8, base_y + row * 8)
                changed = True
    if changed:
        last_screen[:] = current_screen[:]
        hal_screen.refresh()

def new_game(seed=None):
    global view_offset, selected, cursor
    if seed == None:
        seed = random_seed()
    fc.init(seed)
    view_offset = 0
    selected = -1
    cursor = 0
    update_table()
    focus_on_cursor()
    update_screen()

def is_win():
    card_count = sum(( fc.get_col_info(col)[2] for col in range(8) ))
    if card_count <= 0:
        return True
    return False

def game_loop():
    global cursor, selected, view_offset
    update_table()
    focus_on_cursor()
    update_screen()
    render(True)
    with cpu_speed_context(VERY_SLOW):
        while True:
            if is_win():
                return True
            need_update_table = False
            need_focus_cursor = False
            need_check_possible_move = False
            for event in hal_keypad.get_key_event():
                event_type, key = hal_keypad.parse_key_event(event)
                if event_type == hal_keypad.EVENT_KEY_PRESS:
                    if key == hal_keypad.KEY_B:
                        if selected >= 0:
                            selected = -1
                            need_update_table = True
                            need_focus_cursor = True
                        else:
                            return False # go back
                    elif key == hal_keypad.KEY_A:
                        if selected < 0:
                            # select another target
                            selected = cursor
                            if cursor == 7 or cursor == 15:
                                cursor -= 1
                            else:
                                cursor += 1
                        else:
                            fc.move(selected, cursor)
                            selected = -1
                            need_check_possible_move = True
                        need_update_table = True
                        need_focus_cursor = True
                    elif key == hal_keypad.KEY_LEFT or key == hal_keypad.KEY_RIGHT:
                        ofs = 1 if key == hal_keypad.KEY_RIGHT else -1
                        old_cursor = cursor
                        cursor += ofs
                        cursor = cursor % 8 if old_cursor < 8 else ((cursor - 8) % 8) + 8
                        if selected == cursor:
                            cursor += ofs
                            cursor = cursor % 8 if old_cursor < 8 else ((cursor - 8) % 8) + 8
                        need_update_table = True
                        need_focus_cursor = True
                    elif key == hal_keypad.KEY_UP or key == hal_keypad.KEY_DOWN:
                        ofs = screen_lines if key == hal_keypad.KEY_DOWN else -screen_lines
                        view_offset += ofs
                        if view_offset <= 0:
                            view_offset = 0
                            if key == hal_keypad.KEY_UP and cursor < 8:
                                cursor += 8
                                need_update_table = True
                        if view_offset + screen_lines > scene_lines:
                            view_offset = scene_lines - screen_lines
                            if key == hal_keypad.KEY_DOWN and cursor >= 8:
                                cursor -= 8
                                need_update_table = True
                        if need_update_table:
                            if selected == cursor:
                                if cursor == 7 or cursor == 15:
                                    cursor -= 1
                                else:
                                    cursor += 1
                    with cpu_speed_context(FAST):
                        if need_update_table:
                            update_table()
                        if need_focus_cursor:
                            focus_on_cursor()
                        update_screen()
                        render()
                        if need_check_possible_move:
                            possible = fc.possible_move()
                            while possible:
                                sleep_ms(500)
                                frm, to = possible
                                fc.move(frm, to)
                                update_table()
                                update_screen()
                                render()
                                possible = fc.possible_move()
            lightsleep(10)
