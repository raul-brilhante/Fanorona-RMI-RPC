import argparse
import threading
import uuid

import Pyro5.api
import Pyro5.errors

from game import Game


@Pyro5.api.expose
class FanoronaRPC:
    """Serviço autoritativo do jogo, exposto como objeto remoto Pyro5."""

    def __init__(self):
        self.game = Game()
        self.players = {}
        self.pending_choices = {}
        self.visited_seq = set()
        self.turn_pending = False
        self.choice_counter = 0
        self.lock = threading.RLock()

    def _state(self):
        return {
            'rows': self.game.board.serialize().splitlines(),
            'turn': self.game.turn,
            'winner': self.game.winner,
            'status': 'turn_pending' if self.turn_pending else 'active',
        }

    def _result(self, ok=True, **values):
        return {'ok': ok, **values}

    def _player(self, token):
        return self.players.get(token)

    def _notify(self, event=None):
        payload = {'state': self._state(), 'event': event}
        disconnected = []
        for token, player in self.players.items():
            callback = player['callback']
            if callback is None:
                continue
            try:
                callback._pyroClaimOwnership()
                callback.state_updated(payload)
            except (Pyro5.errors.CommunicationError, Pyro5.errors.ConnectionClosedError):
                disconnected.append(token)
        for token in disconnected:
            self.players.pop(token, None)

    @Pyro5.api.expose
    def register_player(self, name, callback_uri=None):
        with self.lock:
            if len(self.players) >= 2:
                return self._result(False, reason='game_full')
            token = uuid.uuid4().hex
            color = 'R' if not self.players else 'P'
            callback = Pyro5.api.Proxy(callback_uri) if callback_uri else None
            self.players[token] = {
                'name': name or 'Jogador',
                'color': color,
                'callback': callback,
            }
            self._notify({'type': 'chat', 'from': 'Sistema',
                          'text': f"{name or 'Jogador'} entrou na partida"})
            return self._result(True, token=token, color=color, state=self._state())

    @Pyro5.api.expose
    def get_state(self, token):
        with self.lock:
            if not self._player(token):
                return self._result(False, reason='invalid_player')
            return self._result(True, state=self._state())

    @Pyro5.api.expose
    def move(self, token, x1, y1, x2, y2):
        with self.lock:
            player = self._player(token)
            if not player:
                return self._result(False, reason='invalid_player')
            if player['color'] != self.game.turn:
                return self._result(False, reason='not_your_turn')
            if self.turn_pending:
                return self._result(False, reason='must_end_turn')
            if any(choice['token'] == token for choice in self.pending_choices.values()):
                return self._result(False, reason='capture_choice_pending')

            ok, reason, captured, cont, requires_choice = self.game.apply_move(
                int(x1), int(y1), int(x2), int(y2), self.visited_seq
            )
            if not ok:
                return self._result(False, reason=reason)
            if requires_choice:
                self.choice_counter += 1
                choice_id = str(self.choice_counter)
                approach, withdrawal = self.game.captures_for_move(x1, y1, x2, y2)
                self.pending_choices[choice_id] = {
                    'token': token,
                    'from': (x1, y1),
                    'to': (x2, y2),
                    'approach': approach,
                    'withdrawal': withdrawal,
                    'visited_seq': set(self.visited_seq),
                }
                self._notify({'type': 'choose', 'choice_id': choice_id,
                              'approach_count': len(approach),
                              'withdrawal_count': len(withdrawal)})
                return self._result(True, requires_choice=True)

            self._finish_move(player, x1, y1, x2, y2, captured, cont)
            return self._result(True, state=self._state())

    def _finish_move(self, player, x1, y1, x2, y2, captured, cont):
        self.game.record_move(captured)
        self._notify({'type': 'move_ok', 'color': player['color'],
                      'from': [x1, y1], 'to': [x2, y2],
                      'captured': [list(position) for position in captured]})
        if self.game.winner:
            self._notify({'type': 'game_over', 'winner': self.game.winner})
        elif cont:
            self.visited_seq.add((x2, y2))
            self._notify({'type': 'continue'})
        else:
            self.visited_seq.clear()
            self.turn_pending = True
            self._notify({'type': 'turn_pending', 'color': self.game.turn})

    @Pyro5.api.expose
    def choose_capture(self, token, choice_id, choice):
        with self.lock:
            context = self.pending_choices.pop(str(choice_id), None)
            if not context:
                return self._result(False, reason='bad_choice_id')
            if context['token'] != token:
                self.pending_choices[str(choice_id)] = context
                return self._result(False, reason='not_your_choice')
            if choice not in ('approach', 'withdrawal'):
                return self._result(False, reason='bad_capture_choice')

            x1, y1 = context['from']
            x2, y2 = context['to']
            captured = context[choice]
            self.game.move_piece(x1, y1, x2, y2)
            for cx, cy in captured:
                self.game.remove_piece(cx, cy)
            self.visited_seq.clear()
            self.visited_seq.update(context['visited_seq'])
            self.visited_seq.add((x2, y2))
            self.game.record_move(captured)
            self.game.update_winner()

            cont = any(
                self.game.board.get(nx, ny) == '.'
                and (nx, ny) not in self.visited_seq
                and (self.game.captures_for_move(x2, y2, nx, ny)[0]
                     or self.game.captures_for_move(x2, y2, nx, ny)[1])
                for nx, ny in self.game.neighbors.get((x2, y2), [])
            )
            player = self.players[token]
            self._finish_move(player, x1, y1, x2, y2, captured, cont)
            return self._result(True, state=self._state())

    @Pyro5.api.expose
    def end_turn(self, token):
        with self.lock:
            player = self._player(token)
            if not player:
                return self._result(False, reason='invalid_player')
            if player['color'] != self.game.turn:
                return self._result(False, reason='not_your_turn')
            if not self.turn_pending:
                return self._result(False, reason='no_turn_pending')
            self.visited_seq.clear()
            self.turn_pending = False
            self.game.switch_turn()
            if self.game.is_draw_by_no_capture():
                self._notify({'type': 'game_over', 'winner': None,
                              'reason': '50_no_capture_turns'})
            else:
                self._notify({'type': 'turn', 'color': self.game.turn})
            return self._result(True, state=self._state())

    @Pyro5.api.expose
    def chat(self, token, text):
        with self.lock:
            player = self._player(token)
            if not player:
                return self._result(False, reason='invalid_player')
            self._notify({'type': 'chat', 'from': player['name'], 'text': str(text)})
            return self._result(True)

    @Pyro5.api.expose
    def resign(self, token):
        with self.lock:
            player = self._player(token)
            if not player:
                return self._result(False, reason='invalid_player')
            winner = next(
                (other['color'] for key, other in self.players.items() if key != token),
                None,
            )
            self.game.winner = winner
            self._notify({'type': 'game_over', 'winner': winner, 'reason': 'resign'})
            return self._result(True)


def main():
    parser = argparse.ArgumentParser(description='Servidor RMI/RPC do Fanorona')
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=5000)
    args = parser.parse_args()

    daemon = Pyro5.api.Daemon(host=args.host, port=args.port)
    uri = daemon.register(FanoronaRPC(), objectId='fanorona')
    print(f'Serviço RPC disponível em {uri}')
    daemon.requestLoop()


if __name__ == '__main__':
    main()
