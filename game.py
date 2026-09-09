import copy


class Board:
    WIDTH = 9
    HEIGHT = 5

    def __init__(self):
        # 'P' = Pink, 'R' = Red, '.' = empty
        self.grid = [[None for _ in range(self.WIDTH)] for _ in range(self.HEIGHT)]
        self.setup()

    def setup(self):
        for y in range(self.HEIGHT):
            for x in range(self.WIDTH):
                self.grid[y][x] = '.'
        # top two rows P (pink)
        for y in (0, 1):
            for x in range(self.WIDTH):
                self.grid[y][x] = 'P'
        # bottom two rows R (red)
        for y in (3, 4):
            for x in range(self.WIDTH):
                self.grid[y][x] = 'R'
        # middle row: alternate R and P across the row, center empty
        mid = self.WIDTH // 2
        for x in range(self.WIDTH):
            if x == mid:
                self.grid[2][x] = '.'
            else:
                self.grid[2][x] = 'R' if (x % 2 == 0) else 'P'

    def in_bounds(self, x, y):
        return 0 <= x < self.WIDTH and 0 <= y < self.HEIGHT

    def get(self, x, y):
        if not self.in_bounds(x, y):
            return None
        return self.grid[y][x]

    def set(self, x, y, v):
        if not self.in_bounds(x, y):
            return
        self.grid[y][x] = v

    def clone(self):
        b = Board()
        b.grid = copy.deepcopy(self.grid)
        return b

    def serialize(self):
        return '\n'.join(''.join(row) for row in self.grid)

    def __str__(self):
        rows = []
        for y in range(self.HEIGHT):
            rows.append(''.join(self.grid[y]))
        return "\n".join(rows)


DIRS = [
    (-1, -1), (0, -1), (1, -1),
    (-1, 0),          (1, 0),
    (-1, 1),  (0, 1),  (1, 1)
]


class Game:
    def __init__(self):
        self.board = Board()
        self.turn = 'R'  # Red starts (was White in previous convention)
        self.winner = None
        self.no_capture_turns = 0
        self.turn_had_capture = False
        self.neighbors = self.build_neighbors(pattern='both_even')

    def set_neighbor_pattern(self, pattern: str):
        """Rebuild the fixed traditional Fanorona graph.

        The argument is retained for compatibility with older callers.
        """
        self.neighbors = self.build_neighbors()

    def switch_turn(self):
        if self.turn_had_capture:
            self.no_capture_turns = 0
        else:
            self.no_capture_turns += 1
        self.turn_had_capture = False
        self.turn = 'P' if self.turn == 'R' else 'R'

    def record_move(self, captured):
        if captured:
            self.turn_had_capture = True

    def is_adjacent(self, x1, y1, x2, y2):
        # adjacency according to neighbor graph
        return (x2, y2) in self.neighbors.get((x1, y1), [])

    def _ensure_piece_path(self, x, y):
        return set()

    def can_piece_visit(self, x1, y1, x2, y2):
        # The server tracks visited positions for the current capture sequence.
        return True

    def move_piece(self, x1, y1, x2, y2):
        piece = self.board.get(x1, y1)
        self.board.set(x1, y1, '.')
        self.board.set(x2, y2, piece)

    def remove_piece(self, x, y):
        self.board.set(x, y, '.')

    def build_neighbors(self, pattern='both_even'):
        """Build the Fanorona connectivity for a 9x5 board.

        The traditional board has horizontal and vertical lines everywhere.
        Diagonals connect each even/even point to its diagonal odd/odd points.
        The test is applied to both endpoints so the graph is undirected.
        """
        neigh = {}
        for y in range(Board.HEIGHT):
            for x in range(Board.WIDTH):
                nbrs = []
                # orthogonals
                for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
                    nx, ny = x+dx, y+dy
                    if 0 <= nx < Board.WIDTH and 0 <= ny < Board.HEIGHT:
                        nbrs.append((nx, ny))
                for dx, dy in [(-1,-1),(1,-1),(-1,1),(1,1)]:
                    nx, ny = x+dx, y+dy
                    if not (0 <= nx < Board.WIDTH and 0 <= ny < Board.HEIGHT):
                        continue
                    starts_at_even_intersection = x % 2 == 0 and y % 2 == 0
                    ends_at_even_intersection = nx % 2 == 0 and ny % 2 == 0
                    if starts_at_even_intersection or ends_at_even_intersection:
                        nbrs.append((nx, ny))
                neigh[(x,y)] = nbrs
        return neigh

    def normalize(self, dx, dy):
        if dx == 0 and dy == 0:
            return (0, 0)
        if dx != 0:
            dx = dx // abs(dx)
        if dy != 0:
            dy = dy // abs(dy)
        return (dx, dy)

    def captures_for_move(self, x1, y1, x2, y2):
        """Return (approach_list, withdrawal_list) of positions that would be captured if
        the piece moves from (x1,y1) to (x2,y2). Lists are in order away from the moved piece.
        Does not modify the board."""
        if not self.board.in_bounds(x1, y1) or not self.board.in_bounds(x2, y2):
            return ([], [])
        piece = self.board.get(x1, y1)
        if piece not in ('R', 'P'):
            return ([], [])
        if (x2, y2) not in self.neighbors.get((x1, y1), []):
            return ([], [])
        dx = x2 - x1
        dy = y2 - y1
        ndx, ndy = self.normalize(dx, dy)
        # approach: from destination forward
        approach = self.contiguous_in_direction(x2, y2, ndx, ndy, piece)
        # withdrawal: from source backward
        wdx, wdy = -ndx, -ndy
        withdrawal = self.contiguous_in_direction(x1, y1, wdx, wdy, piece)
        return (approach, withdrawal)

    def contiguous_in_direction(self, x, y, dx, dy, player):
        # returns list of opponent positions contiguous from (x,y) following
        # the neighbor graph in direction (dx,dy). We step by validating
        # that each successive cell is a neighbor of the previous one and
        # that the step direction matches (dx,dy) normalized.
        res = []
        ndx, ndy = self.normalize(dx, dy)
        cx, cy = x, y
        while True:
            nx, ny = cx + ndx, cy + ndy
            if not self.board.in_bounds(nx, ny):
                break
            # ensure (nx,ny) is reachable from (cx,cy)
            if (nx, ny) not in self.neighbors.get((cx, cy), []):
                break
            val = self.board.get(nx, ny)
            if val == '.':
                break
            if val == player:
                break
            res.append((nx, ny))
            cx, cy = nx, ny
        return res

    def apply_move(self, x1, y1, x2, y2, visited_seq=None):
        # returns (ok, message, captured_positions, continue_capture_possible, requires_choice)
        if visited_seq is None:
            visited_seq = set()
        if not self.board.in_bounds(x1, y1) or not self.board.in_bounds(x2, y2):
            return (False, 'Fora dos limites', [], False, False)
        piece = self.board.get(x1, y1)
        if piece not in ('R', 'P'):
            return (False, 'Não há peça na origem', [], False, False)
        if piece != self.turn:
            return (False, 'Não é o seu turno', [], False, False)
        if self.board.get(x2, y2) != '.':
            return (False, 'O destino não está vazio', [], False, False)
        if not self.is_adjacent(x1, y1, x2, y2):
            return (False, 'Só é possível mover para um ponto vizinho', [], False, False)
        if not self.can_piece_visit(x1, y1, x2, y2):
            return (False, 'A peça não pode retornar a um ponto já visitado', [], False, False)
        if (x2, y2) in visited_seq:
            return (False, 'Não é possível revisitar um ponto durante uma sequência de capturas', [], False, False)

        if not visited_seq:
            visited_seq.add((x1, y1))

        # compute captures but don't apply both automatically
        approach, withdrawal = self.captures_for_move(x1, y1, x2, y2)

        # If no captures produced, this is a simple move
        if not approach and not withdrawal:
            # simple move: apply and switch turn
            self.move_piece(x1, y1, x2, y2)
            self.update_winner()
            # turn passing handled by server (manual end-turn)
            return (True, 'Ok', [], False, False)

        # if both present, require choice by player (approach vs withdrawal)
        if approach and withdrawal:
            # do not change board yet; caller must resolve choice
            return (True, 'ChoiceRequired', [], False, True)

        # exactly one capture type present: apply it
        captured = approach if approach else withdrawal
        # apply move
        self.move_piece(x1, y1, x2, y2)
        for (cx, cy) in captured:
            self.remove_piece(cx, cy)
        visited_seq.add((x2, y2))

        # After move, check if further captures possible for the same piece at (x2,y2)
        cont = False
        # only consider further captures along neighbor edges
        for (nx, ny) in self.neighbors.get((x2, y2), []):
            if self.board.get(nx, ny) != '.':
                continue
            if not self.can_piece_visit(x2, y2, nx, ny):
                continue
            ap, wd = self.captures_for_move(x2, y2, nx, ny)
            if (ap or wd) and (nx, ny) not in visited_seq:
                cont = True
                break

        self.update_winner()

        # If no further capture, do NOT switch turn automatically; server will require manual end-turn
        # (game.turn remains the current player until server calls switch_turn())

        return (True, 'Ok', captured, cont, False)

    def update_winner(self):
        counts = {'R': 0, 'P': 0}
        for y in range(self.board.HEIGHT):
            for x in range(self.board.WIDTH):
                v = self.board.get(x, y)
                if v in counts:
                    counts[v] += 1
        if counts['R'] == 0:
            self.winner = 'P'
        elif counts['P'] == 0:
            self.winner = 'R'
        elif self.is_blockade_win(self.turn):
            self.winner = self.turn

    def player_has_legal_move(self, player):
        """Return whether the player has any legal adjacent move."""
        for y in range(self.board.HEIGHT):
            for x in range(self.board.WIDTH):
                if self.board.get(x, y) != player:
                    continue
                for nx, ny in self.neighbors.get((x, y), []):
                    if self.board.get(nx, ny) != '.':
                        continue
                    if not self.can_piece_visit(x, y, nx, ny):
                        continue
                    return True
        return False

    def is_blockade_win(self, player):
        opponent = 'P' if player == 'R' else 'R'
        return not self.player_has_legal_move(opponent)

    def is_draw_by_no_capture(self):
        return self.no_capture_turns >= 50

    def player_has_any_capture(self, player):
        # iterate all pieces of player and check if any move yields captures
        for y in range(self.board.HEIGHT):
            for x in range(self.board.WIDTH):
                if self.board.get(x, y) != player:
                    continue
                for (nx, ny) in self.neighbors.get((x, y), []):
                    # destination must be empty to be a legal move
                    if self.board.get(nx, ny) != '.':
                        continue
                    ap, wd = self.captures_for_move(x, y, nx, ny)
                    if ap or wd:
                        return True
        return False


if __name__ == '__main__':
    g = Game()
    print(g.board)
