import socket
import threading
import queue
import traceback
import json
from game import Game

HOST = '0.0.0.0'
PORT = 5000

class Player:
    def __init__(self, conn, addr):
        self.conn = conn
        self.addr = addr
        self.name = None
        self.color = None

    def send(self, msg):
        try:
            if isinstance(msg, dict):
                s = json.dumps(msg)
            else:
                s = str(msg)
            self.conn.sendall((s + '\n').encode('utf-8'))
        except Exception:
            pass


class FanoronaServer:
    def __init__(self, host=HOST, port=PORT):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.clients = []
        self.q = queue.Queue()
        self.game = Game()
        self.lock = threading.Lock()
        self.choice_counter = 0
        self.pending_choices = {}
        self.turn_pending = False

    def start(self):
        self.sock.bind((self.host, self.port))
        self.sock.listen(5)
        print(f"Server listening on {self.host}:{self.port}")
        threading.Thread(target=self.accept_loop, daemon=True).start()
        while True:
            if len(self.clients) >= 2:
                self.run_game()
                break

    def accept_loop(self):
        while True:
            conn, addr = self.sock.accept()
            if len(self.clients) >= 2:
                try:
                    conn.sendall((json.dumps({'type': 'error', 'reason': 'game_full'}) + '\n').encode('utf-8'))
                finally:
                    conn.close()
                print('Rejected client (game full)', addr)
                continue
            p = Player(conn, addr)
            self.clients.append(p)
            threading.Thread(target=self.client_reader, args=(p,), daemon=True).start()
            print('Client connected', addr)

    def client_reader(self, player):
        conn = player.conn
        f = conn.makefile('r', encoding='utf-8')
        try:
            for line in f:
                line = line.rstrip('\n')
                if not line:
                    continue
                self.q.put((player, line))
        except Exception:
            traceback.print_exc()
        finally:
            conn.close()

    def broadcast(self, msg):
        for p in self.clients:
            p.send(msg)

    def find_player_by_color(self, color):
        for p in self.clients:
            if p.color == color:
                return p
        return None

    def run_game(self):
        p1, p2 = self.clients[0], self.clients[1]
        p1.color = 'R'
        p2.color = 'P'
        p1.send({'type': 'assign', 'color': 'R'})
        p2.send({'type': 'assign', 'color': 'P'})
        self.broadcast({'type': 'start'})
        self.send_board()
        self.broadcast({'type': 'turn', 'color': self.game.turn, 'status': 'active'})

        visited_seq = set()
        while True:
            player, line = self.q.get()
            try:
                try:
                    msg = json.loads(line)
                except Exception:
                    player.send({'type': 'error', 'reason': 'invalid_json'})
                    continue

                t = msg.get('type')
                if t == 'join':
                    name = msg.get('name') or 'Jogador'
                    player.name = name
                    print(f"[SERVER] JOIN from {player.addr}: {name}")
                    self.broadcast({'type': 'chat', 'from': 'Sistema', 'text': f'{name} entrou na partida'})
                    continue
                if t == 'chat':
                    text = msg.get('text', '')
                    print(f"[SERVER] CHAT from {player.addr} ({player.name}): {text}")
                    self.broadcast({'type': 'chat', 'from': player.name or 'Jogador', 'text': text})
                    continue
                if t == 'resign':
                    other = [p for p in self.clients if p != player][0]
                    self.broadcast({'type': 'game_over', 'winner': other.color, 'reason': 'resign'})
                    break
                if t == 'move':
                    frm = msg.get('from')
                    to = msg.get('to')
                    if not frm or not to or len(frm) != 2 or len(to) != 2:
                        player.send({'type': 'invalid', 'reason': 'bad_move_format'})
                        continue
                    x1, y1 = int(frm[0]), int(frm[1])
                    x2, y2 = int(to[0]), int(to[1])
                    if player.color != self.game.turn:
                        player.send({'type': 'invalid', 'reason': 'not_your_turn'})
                        continue
                    if self.turn_pending:
                        player.send({'type': 'invalid', 'reason': 'must_end_turn'})
                        continue
                    if any(ctx['player'] == player for ctx in self.pending_choices.values()):
                        player.send({'type': 'invalid', 'reason': 'capture_choice_pending'})
                        continue

                    ok, msgtxt, captured, cont, requires_choice = self.game.apply_move(x1, y1, x2, y2, visited_seq)
                    if not ok:
                        player.send({'type': 'invalid', 'reason': msgtxt})
                        continue

                    if requires_choice:
                        self.choice_counter += 1
                        cid = str(self.choice_counter)
                        approach, withdrawal = self.game.captures_for_move(x1, y1, x2, y2)
                        self.pending_choices[cid] = {
                            'player': player,
                            'from': [x1, y1],
                            'to': [x2, y2],
                            'approach': approach,
                            'withdrawal': withdrawal,
                            'visited_seq': visited_seq
                        }
                        player.send({'type': 'choose', 'choice_id': cid, 'options': ['approach', 'withdrawal'], 'approach_count': len(approach), 'withdrawal_count': len(withdrawal)})
                        continue

                    self.game.record_move(captured)
                    self.broadcast({'type': 'move_ok', 'color': player.color, 'from': [x1, y1], 'to': [x2, y2], 'captured': captured})
                    self.send_board()
                    if self.game.winner:
                        self.broadcast({'type': 'game_over', 'winner': self.game.winner})
                        break
                    if cont:
                        visited_seq.add((x2, y2))
                        player.send({'type': 'continue', 'msg': 'Você pode capturar novamente'})
                        self.broadcast({'type': 'turn', 'color': self.game.turn, 'status': 'capture'})
                        continue
                    else:
                        visited_seq.clear()
                        self.turn_pending = True
                        self.broadcast({'type': 'turn_pending', 'color': self.game.turn})
                        continue
                if t == 'get_board':
                    player.send({'type': 'board', 'rows': self.game.board.serialize().split('\n')})
                    continue
                if t == 'capture_choice':
                    cid = msg.get('choice_id')
                    choice = msg.get('choice')
                    ctx = self.pending_choices.pop(cid, None)
                    if not ctx:
                        player.send({'type': 'invalid', 'reason': 'bad_choice_id'})
                        continue
                    if ctx['player'] != player:
                        player.send({'type': 'invalid', 'reason': 'not_your_choice'})
                        continue
                    x1, y1 = ctx['from']
                    x2, y2 = ctx['to']
                    if (x2, y2) in ctx['visited_seq']:
                        player.send({'type': 'invalid', 'reason': 'Não é possível revisitar um ponto durante uma sequência de capturas'})
                        continue
                    if choice == 'approach':
                        captured = ctx['approach']
                    else:
                        captured = ctx['withdrawal']
                    self.game.move_piece(x1, y1, x2, y2)
                    for (cx, cy) in captured:
                        self.game.remove_piece(cx, cy)
                    ctx['visited_seq'].add((x2, y2))
                    visited_seq.clear()
                    visited_seq.update(ctx['visited_seq'])
                    self.game.record_move(captured)
                    self.game.update_winner()
                    cont = False
                    for (nx, ny) in self.game.neighbors.get((x2, y2), []):
                        if self.game.board.get(nx, ny) != '.':
                            continue
                        if not self.game.can_piece_visit(x2, y2, nx, ny):
                            continue
                        ap, wd = self.game.captures_for_move(x2, y2, nx, ny)
                        if (ap or wd) and (nx, ny) not in ctx['visited_seq']:
                            cont = True
                            break
                    self.broadcast({'type': 'move_ok', 'color': player.color, 'from': [x1, y1], 'to': [x2, y2], 'captured': captured})
                    self.send_board()
                    if self.game.winner:
                        self.broadcast({'type': 'game_over', 'winner': self.game.winner})
                        break
                    if cont:
                        ctx['visited_seq'].add((x2, y2))
                        player.send({'type': 'continue', 'msg': 'Você pode capturar novamente'})
                        self.broadcast({'type': 'turn', 'color': self.game.turn, 'status': 'capture'})
                        continue
                    else:
                        visited_seq.clear()
                        self.turn_pending = True
                        self.broadcast({'type': 'turn_pending', 'color': self.game.turn})
                        continue
                if t == 'end_turn':
                    if player.color != self.game.turn:
                        player.send({'type': 'invalid', 'reason': 'not_your_turn'})
                        continue
                    if not self.turn_pending:
                        player.send({'type': 'invalid', 'reason': 'no_turn_pending'})
                        continue
                    visited_seq.clear()
                    self.turn_pending = False
                    self.game.switch_turn()
                    if self.game.is_draw_by_no_capture():
                        self.broadcast({'type': 'game_over', 'winner': None, 'reason': '50_no_capture_turns'})
                        break
                    self.broadcast({'type': 'turn', 'color': self.game.turn, 'status': 'active'})
                    continue
                player.send({'type': 'invalid', 'reason': 'unknown_command'})
            except Exception as e:
                traceback.print_exc()
                player.send({'type': 'error', 'reason': 'server_error'})

        for p in self.clients:
            try:
                p.conn.close()
            except Exception:
                pass

    def send_board(self):
        b = self.game.board.serialize()
        rows = b.split('\n')
        self.broadcast({'type': 'board', 'rows': rows})


if __name__ == '__main__':
    s = FanoronaServer()
    s.start()
