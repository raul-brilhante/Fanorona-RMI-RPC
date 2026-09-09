import threading
import time
import socket

from server import FanoronaServer

HOST = '127.0.0.1'
PORT = 6000
import json


def run_server():
    s = FanoronaServer(host=HOST, port=PORT)
    s.start()


def read_lines(sock, tag, timeout=2.0):
    sock.settimeout(0.5)
    end = time.time() + timeout
    buf = ''
    try:
        f = sock.makefile('r', encoding='utf-8')
        while time.time() < end:
            line = f.readline()
            if not line:
                break
            print(f'[{tag}] {line.rstrip()}')
    except Exception as e:
        pass


def simulate_clients():
    s1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s1.connect((HOST, PORT))
    s1.sendall((json.dumps({'type':'join','name':'Raul'}) + '\n').encode('utf-8'))
    time.sleep(0.2)
    s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s2.connect((HOST, PORT))
    s2.sendall((json.dumps({'type':'join','name':'Cidcley'}) + '\n').encode('utf-8'))
    time.sleep(0.5)

    s1.sendall((json.dumps({'type':'get_board'}) + '\n').encode('utf-8'))
    time.sleep(0.2)
    print('\n-- after GET_BOARD:')
    read_lines(s1, 'C1')
    read_lines(s2, 'C2')

    s1.sendall((json.dumps({'type':'move','from':[4,3],'to':[4,2]}) + '\n').encode('utf-8'))
    time.sleep(0.5)
    print('\n-- after MOVE by Raul:')
    read_lines(s1, 'C1')
    read_lines(s2, 'C2')

    s1.close()
    s2.close()


if __name__ == '__main__':
    t = threading.Thread(target=run_server, daemon=True)
    t.start()
    time.sleep(0.4)
    simulate_clients()
    time.sleep(1.0)
    print('\nTest finished')
