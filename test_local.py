from game import Game
from rpc_server import FanoronaRPC


def test_rules_are_unchanged():
    game = Game()
    ok, _, captured, continuation, choice = game.apply_move(4, 3, 4, 2, set())
    assert ok
    assert captured == [(4, 1), (4, 0)]
    assert not continuation
    assert not choice


def test_rpc_updates_shared_state_without_text_protocol():
    service = FanoronaRPC()
    first = service.register_player('Raul')
    second = service.register_player('Cidcley')

    assert first['ok'] and second['ok']
    result = service.move(first['token'], 4, 3, 4, 2)
    assert result['ok']

    first_state = service.get_state(first['token'])['state']
    second_state = service.get_state(second['token'])['state']
    assert first_state['rows'] == second_state['rows']
    assert first_state['rows'][2][4] == 'R'


if __name__ == '__main__':
    test_rules_are_unchanged()
    test_rpc_updates_shared_state_without_text_protocol()
    print('RPC smoke tests passed')
