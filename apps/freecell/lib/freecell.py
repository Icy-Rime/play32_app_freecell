try:
    from uio import BytesIO
except ImportError:
    from io import BytesIO
try:
    from uos import urandom
except ImportError:
    from os import urandom

def make_card(typ, val):
    return ((val << 2) | (typ & 0b11)) & 0b11111111

def split_card(byt):
    return byt & 0b11, (byt >> 2) & 0b111111

def make_history(frm, to, size):
    b0 = ((size & 0b1111) << 4) | (frm & 0b1111)
    b1 = ((size & 0b1111) << 4) | (to & 0b1111)
    return bytes([b0, b1])

def split_history(byts):
    size = (byts[0] >> 4) & 0b1111
    frm = byts[0] & 0b1111
    to = byts[1] & 0b1111
    return frm, to, size

CARD_EMPTY = 0b11111111
# CARD: 6bit val, 2bit type
#     ->  typ: 0b00, 0b10 is the same color, 0b01, 0b11 is the same color
# history 8bit from, 8bit to
#     ->  address: 4bit size, 4bit col or cell
#         -> 0~7: cols 8~11: free_cell 12-15: recv_cell

def random_int(xn):
    # return [0, 2**31)
    return (1103515245 * xn + 12345) % 0x80000000

def random_seed():
    return int.from_bytes(urandom(4), "big")

class FreeCell:
    def __init__(self):
        self.__seed = 0
        self.__table = bytearray(52) # card table, contains all cards
        self.__col_tails = bytearray(8) # tail position of every col
        self.__free_cells = bytearray(4)
        self.__recv_cells = bytearray(4)
        self.__history = BytesIO(b"") # 前2bit记录history大小
    
    @property
    def seed(self):
        return self.__seed
    
    def init(self, seed):
        assert 0 <= seed and 0xFFFFFFFF >= seed
        self.__seed = seed
        for i in range(4):
            self.__free_cells[i] = CARD_EMPTY
            self.__recv_cells[i] = CARD_EMPTY
        self.__history = BytesIO(b"")
        self.__history.write(b"\x00\x00")
        for typ in range(4):
            for val in range(13):
                card = make_card(typ, val)
                self.__table[typ * 13 + val] = card
        for i in range(52):
            curr = self.__table[i]
            seed = random_int(seed)
            rand_i = int((seed / 0x80000000) * 52)
            self.__table[i] = self.__table[rand_i]
            self.__table[rand_i] = curr
        self.__col_tails = bytearray([7, 14, 21, 28, 34, 40, 46, 52])

    def get_col_info(self, col):
        assert 0 <= col and 8 > col
        start = self.__col_tails[col - 1] if col > 0 else 0
        end = self.__col_tails[col]
        return start, end, end - start
    
    def get_card_at(self, col, pos):
        start, end, size = self.get_col_info(col)
        index = start + pos
        assert index < end
        return self.__table[index]
    
    def get_free_cell_card(self, fcid):
        assert fcid < 4 and fcid >= 0
        return self.__free_cells[fcid]
    
    def get_recv_cell_card(self, rcid):
        assert rcid < 4 and rcid >= 0
        return self.__recv_cells[rcid]

    def _max_cards_can_move_to(self, to):
        if to < 0:
            return 0
        elif to < 8:
            free_cells = sum(( 1 if card == CARD_EMPTY else 0 for card in self.__free_cells ))
            free_cols = sum(( 1 if (col != to) and (self.get_col_info(col)[2] == 0) else 0 for col in range(8) ))
            return (free_cells + 1) * (2 ** free_cols)
        elif to < 12:
            fcid = to - 8
            if self.__free_cells[fcid] == CARD_EMPTY:
                return 1
            else:
                return 0
        elif to < 16:
            return 1
        else:
            return 0

    def _max_card_can_move_from(self, frm):
        if frm < 0:
            return 0
        elif frm < 8:
            start, end, size = self.get_col_info(frm)
            last_card = CARD_EMPTY
            i = end - 1
            while i >= start:
                card = self.__table[i]
                if last_card == CARD_EMPTY:
                    last_card = card
                else:
                    l_typ, l_val = split_card(last_card)
                    typ, val = split_card(card)
                    if ((typ ^ l_typ) & 0b1) == 0b1 and l_val == val - 1:
                        last_card = card
                    else:
                        return end - i - 1
                i -= 1
            return size
        elif frm < 12:
            fcid = frm - 8
            if self.__free_cells[fcid] == CARD_EMPTY:
                return 0
            else:
                return 1
        elif frm < 16:
            return 0
        else:
            return 0
    
    def _do_move(self, frm, to, size):
        if frm < 8 and to < 8:
            f_ed = self.get_col_info(frm)[1]
            t_ed = self.get_col_info(to)[1]
            # move in the table
            #   |    t     s f 
            #   ||---|---|---|---|
            #   |  s f       t
            if frm < to:
                p0 = f_ed - size
                p1 = t_ed - size
                tmp = self.__table[p0 : f_ed]
                for p in range(p0, p1):
                    self.__table[p] = self.__table[p + size]
                for i in range(size):
                    self.__table[p1 + i] = tmp[i]
                for i in range(frm, to):
                    self.__col_tails[i] -= size
            else:
                p0 = t_ed + size
                p1 = f_ed
                tmp = self.__table[f_ed - size : f_ed]
                p = p1 - 1
                while p >= p0:
                    self.__table[p] = self.__table[p - size]
                    p -= 1
                for i in range(size):
                    self.__table[t_ed + i] = tmp[i]
                for i in range(to, frm):
                    self.__col_tails[i] += size
        elif frm < 8 and to >= 8:
            # table to cell
            f_ed = self.get_col_info(frm)[1]
            if to < 12:
                fcid = to - 8
                self.__free_cells[fcid] = self.__table[f_ed - 1]
            elif to < 16:
                offs = to - 12
                self.__recv_cells[offs] = self.__table[f_ed - 1]
            ed = self.get_col_info(7)[1]
            for i in range(f_ed - 1, ed - 1):
                self.__table[i] = self.__table[i + 1]
            self.__table[ed - 1] = CARD_EMPTY
            for i in range(frm, 8):
                self.__col_tails[i] -= 1
        elif frm >= 8 and to < 8:
            # cell to table
            if frm < 12:
                fcid = frm - 8
                f_card = self.__free_cells[fcid]
                self.__free_cells[fcid] = CARD_EMPTY
            elif frm < 16:
                offs = frm - 12
                f_card = self.__recv_cells[offs]
                typ, val = split_card(f_card)
                if val > 0:
                    self.__recv_cells[offs] = make_card(typ, val - 1)
                else:
                    self.__recv_cells[offs] = CARD_EMPTY
            t_ed = self.get_col_info(to)[1]
            ed = self.get_col_info(7)[1]
            i = ed
            while i >= t_ed + 1:
                self.__table[i] = self.__table[i - 1]
                i -= 1
            self.__table[t_ed] = f_card
            for i in range(to, 8):
                self.__col_tails[i] += 1
        else:
            # cell to cell
            if frm < 12:
                fcid = frm - 8
                f_card = self.__free_cells[fcid]
                self.__free_cells[fcid] = CARD_EMPTY
            elif frm < 16:
                offs = frm - 12
                f_card = self.__recv_cells[offs]
                typ, val = split_card(f_card)
                if val > 0:
                    self.__recv_cells[offs] = make_card(typ, val - 1)
                else:
                    self.__recv_cells[offs] = CARD_EMPTY
            if to < 12:
                fcid = to - 8
                self.__free_cells[fcid] = f_card
            elif to < 16:
                offs = to - 12
                self.__recv_cells[offs] = f_card
    
    def _record_history(self, frm, to, size):
        record = make_history(frm, to, size)
        self.__history.seek(0)
        lng = int.from_bytes(self.__history.read(2), "big")
        self.__history.seek(2 + lng * 2)
        self.__history.write(record)
        self.__history.seek(0)
        self.__history.write(int.to_bytes(lng + 1, 2, "big"))

    def undo(self):
        self.__history.seek(0)
        lng = int.from_bytes(self.__history.read(2), "big")
        if lng <= 0:
            return
        self.__history.seek(lng * 2)
        record = self.__history.read(2)
        frm, to, size = split_history(record)
        self._do_move(to, frm, size)
        self.__history.seek(0)
        self.__history.write(int.to_bytes(lng - 1, 2, "big"))

    def save(self, stream):
        stream.write(int.to_bytes(self.__seed, 4, "big")) # 4
        stream.write(self.__table) # 52
        stream.write(self.__col_tails) # 8
        stream.write(self.__free_cells) # 4
        stream.write(self.__recv_cells) # 4
        self.__history.seek(0)
        lng_bytes = self.__history.read(2)
        stream.write(lng_bytes) # 2
        lng = int.from_bytes(lng_bytes, "big")
        stream.write(self.__history.read(lng * 2)) # lng * 2
    
    def load(self, stream):
        self.__seed = int.from_bytes(stream.read(4), "big")
        self.__table = bytearray(stream.read(52))
        self.__col_tails = bytearray(stream.read(8))
        self.__free_cells = bytearray(stream.read(4))
        self.__recv_cells = bytearray(stream.read(4))
        lng_bytes = stream.read(2)
        lng = int.from_bytes(lng_bytes, "big")
        self.__history = BytesIO(b"")
        self.__history.write(lng_bytes)
        self.__history.write(stream.read(lng * 2))
    
    def possible_move(self):
        top_cards = bytearray(12)
        for i in range(8):
            size = self.get_col_info(i)[2]
            if size > 0:
                top_cards[i] = self.get_card_at(i, size - 1)
            else:
                top_cards[i] = CARD_EMPTY
        for i in range(4):
            top_cards[8 + i] = self.__free_cells[i]
        tmp = bytearray(b"\xff\xff\xff\xff") # store [typ -> val + 1]
        for t_card in self.__recv_cells:
            if t_card != CARD_EMPTY:
                t_typ, t_val = split_card(t_card)
                tmp[t_typ] = min(t_val + 1, tmp[t_typ]) # plus 1
        for i in range(4):
            if tmp[i] == 0xFF:
                tmp[i] = 0
        # max can be auto collect if: min other color +1
        min_red_p1 = min(tmp[0], tmp[2])
        min_black_p1 = min(tmp[1], tmp[3])
        for i, f_card in enumerate(top_cards):
            if f_card == CARD_EMPTY:
                continue
            f_typ, f_val = split_card(f_card)
            if f_typ & 0b1 == 0b0 and f_val > min_black_p1: # red
                continue
            elif f_typ & 0b1 == 0b1 and f_val > min_red_p1: # black
                continue
            if f_val == tmp[f_typ]: # match the value, and can be auto collect
                if f_val == 0: #use first empty recv cell
                    for to, t_card in enumerate(self.__recv_cells):
                        if t_card == CARD_EMPTY:
                            return i, to + 12
                else: # find the cell
                    find_card = make_card(f_typ, f_val - 1)
                    for to, t_card in enumerate(self.__recv_cells):
                        if t_card == find_card:
                            return i, to + 12
        return None

    def move(self, frm, to):
        assert frm >= 0 and frm < 16
        assert to >= 0 and to < 16
        if frm == to:
            return False
        if frm >= 12: # from recv_cells, not allowed
            return False
        max_can_move_from = self._max_card_can_move_from(frm)
        max_can_move_to = self._max_cards_can_move_to(to)
        max_can_move = min(max_can_move_from, max_can_move_to)
        if max_can_move <= 0: # can't move
            return False
        # get target card
        t_card = CARD_EMPTY
        if to < 8:
            size = self.get_col_info(to)[2]
            if size <= 0:
                t_card = CARD_EMPTY
            else:
                t_card = self.get_card_at(to, size - 1)
        elif to < 12:
            t_card = CARD_EMPTY
        elif to < 16:
            offs = to - 12
            t_card = self.__recv_cells[offs]
        # get source card
        move_size = 0
        # target is empty
        if t_card == CARD_EMPTY and to < 12:
            # free cell and col accept any card
            move_size = max_can_move
        elif t_card == CARD_EMPTY and to < 16:
            # recv cell accept A when empty
            if frm < 8: # from table
                size = self.get_col_info(frm)[2]
                f_card = self.get_card_at(frm, size - 1)
            else: # from free cell
                fcid = frm - 8
                f_card = self.__free_cells[fcid]
            typ, val = split_card(f_card)
            if val != 0:
                return False
            move_size = 1
        # target is not empty, target can't be free cell
        elif frm < 8:
            # from table
            l_typ, l_val = split_card(t_card)
            f_start, f_end, _ = self.get_col_info(frm)
            move_size = 0
            i = f_end - 1
            start_limit = max(f_start, f_end - max_can_move)
            if to < 8: # to table, find suitable card
                while i >= start_limit:
                    f_card = self.__table[i]
                    typ, val = split_card(f_card)
                    if ((typ ^ l_typ) & 0b1) == 0b1 and l_val == val + 1:
                        move_size = f_end - i
                        break
                    i -= 1
            elif to < 16: # to recv cell, only check 1 bottom card
                f_card = self.__table[i]
                typ, val = split_card(f_card)
                if typ == l_typ and l_val == val - 1:
                    move_size = 1 
        else:
            # from free cell
            fcid = frm - 8
            f_card = self.__free_cells[fcid]
            typ, val = split_card(f_card)
            l_typ, l_val = split_card(t_card)
            if to < 8:
                if ((typ ^ l_typ) & 0b1) != 0b1 or l_val != val + 1:
                    return False
            elif to < 16:
                if typ != l_typ or l_val != val - 1:
                    return False
            move_size = 1
        if move_size <= 0:
            return False
        # do the move
        # print("move info:", frm, to, move_size)
        self._do_move(frm, to, move_size)
        self._record_history(frm, to, move_size)
        return True
