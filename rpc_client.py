import socket
import threading

import Pyro5.api
import Pyro5.core


def _client_ip_for_server(uri):
    """Return the local address reachable from the server described by ``uri``."""
    server_uri = Pyro5.core.URI(str(uri))
    server_host = server_uri.host

    address_info = socket.getaddrinfo(
        server_host,
        server_uri.port,
        type=socket.SOCK_DGRAM,
    )
    if not address_info:
        raise RuntimeError(f'Não foi possível resolver o servidor RPC: {server_host}')

    family, socktype, protocol, _, address = address_info[0]
    try:
        with socket.socket(family, socktype, protocol) as probe:
            probe.connect(address)
            return probe.getsockname()[0]
    except OSError as error:
        raise RuntimeError(
            f'Não foi possível descobrir o IP local para o servidor RPC '
            f'{server_host}: {error}'
        ) from error


@Pyro5.api.expose
class UpdateCallback:
    def __init__(self, on_update):
        self.on_update = on_update

    def state_updated(self, payload):
        self.on_update(payload)


class FanoronaRPCClient:
    def __init__(self, uri, on_update):
        self.proxy = Pyro5.api.Proxy(uri)
        client_ip = _client_ip_for_server(uri)
        self.callback_daemon = Pyro5.api.Daemon(host=client_ip)
        self.callback = UpdateCallback(on_update)
        self.callback_uri = self.callback_daemon.register(self.callback)
        self.callback_thread = threading.Thread(
            target=self.callback_daemon.requestLoop,
            daemon=True,
        )
        self.callback_thread.start()
        self.token = None

    def register(self, name):
        result = self.proxy.register_player(name, str(self.callback_uri))
        if not result['ok']:
            raise RuntimeError(result['reason'])
        self.token = result['token']
        return result

    def _call(self, method, *args):
        if not self.token:
            raise RuntimeError('Cliente não registrado no servidor')
        return getattr(self.proxy, method)(self.token, *args)

    def move(self, x1, y1, x2, y2):
        return self._call('move', x1, y1, x2, y2)

    def choose_capture(self, choice_id, choice):
        return self._call('choose_capture', choice_id, choice)

    def end_turn(self):
        return self._call('end_turn')

    def chat(self, text):
        return self._call('chat', text)

    def resign(self):
        return self._call('resign')

    def close(self):
        self.callback_daemon.shutdown()
        self.proxy._pyroRelease()
