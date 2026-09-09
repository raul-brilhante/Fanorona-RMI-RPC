import socket
import threading
import json
import tkinter as tk
from tkinter import scrolledtext, messagebox
from game import Game

CELL_SIZE = 64
COLS = 9
ROWS = 5

COLOR_BG = '#e0cfa6'
COLOR_LINE = '#3b2f1f'
COLOR_PIECE_R = '#D32F2F'
COLOR_PIECE_R_INNER = '#FF6F61'
COLOR_PIECE_P = '#FF69B4'
COLOR_PIECE_P_INNER = '#FFC0CB'


class GUIClient(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Cliente Fanorona')
        self.geometry(f'{CELL_SIZE * COLS + 300}x{CELL_SIZE * ROWS + 80}')

        self.sock = None
        self.reader_thread = None
        self.my_color = None
        self.turn = None
        self.board = [['.' for _ in range(COLS)] for _ in range(ROWS)]
        self.selection = None
        try:
            self._graph = Game()
        except Exception:
            self._graph = None

        self._build_ui()

    def _build_ui(self):
        top = tk.Frame(self)
        top.pack(side='top', fill='x')

        tk.Label(top, text='Servidor:').pack(side='left')
        self.host_var = tk.StringVar(value='127.0.0.1')
        tk.Entry(top, textvariable=self.host_var, width=12).pack(side='left')
        tk.Label(top, text='Porta:').pack(side='left')
        self.port_var = tk.StringVar(value='5000')
        tk.Entry(top, textvariable=self.port_var, width=6).pack(side='left')
        tk.Label(top, text='Nome:').pack(side='left')
        self.name_var = tk.StringVar(value='Jogador')
        tk.Entry(top, textvariable=self.name_var, width=12).pack(side='left')
        tk.Button(top, text='Conectar', command=self.connect).pack(side='left', padx=4)
        tk.Button(top, text='Desistir', command=self.resign).pack(side='left', padx=4)
        self.end_turn_button = tk.Button(top, text='Encerrar turno', command=self.end_turn)
        self.end_turn_button.pack(side='left', padx=4)

        status = tk.Frame(self)
        status.pack(side='top', fill='x')
        self.lbl_color = tk.Label(status, text='Cor: -')
        self.lbl_color.pack(side='left', padx=4)
        self.lbl_turn = tk.Label(status, text='Turno: -')
        self.lbl_turn.pack(side='left', padx=8)

        main = tk.Frame(self)
        main.pack(side='top', fill='both', expand=True)

        self.canvas = tk.Canvas(main, width=CELL_SIZE * COLS, height=CELL_SIZE * ROWS, bg='grey')
        self.canvas.pack(side='left', padx=4, pady=4)
        self.canvas.bind('<Button-1>', self.on_canvas_click)

        right = tk.Frame(main)
        right.pack(side='left', fill='both', expand=True)

        tk.Label(right, text='Chat / Registro').pack(anchor='w')
        self.chat = scrolledtext.ScrolledText(right, width=40, height=20, state='disabled')
        self.chat.pack(fill='both', expand=True)

        chat_entry = tk.Frame(right)
        chat_entry.pack(fill='x')
        self.chat_var = tk.StringVar()
        self.chat_input = tk.Entry(chat_entry, textvariable=self.chat_var)
        self.chat_input.pack(side='left', fill='x', expand=True)
        self.chat_input.bind('<Return>', lambda e: self.send_chat())
        tk.Button(chat_entry, text='Enviar', command=self.send_chat).pack(side='left')

        self.end_turn_enabled = False
        self.end_turn_button.config(state='disabled')
        self.redraw_board()

    def end_turn(self):
        if not self.sock:
            return
        self.send_json({'type': 'end_turn'})
        self.end_turn_enabled = False
        self.update_end_button_state()

    def update_end_button_state(self):
        self.end_turn_button.config(state='normal' if self.end_turn_enabled else 'disabled')

    def connect(self):
        if self.sock:
            messagebox.showinfo('Informação', 'Já conectado')
            return
        host = self.host_var.get()
        try:
            port = int(self.port_var.get())
        except ValueError:
            messagebox.showerror('Erro', 'Porta inválida')
            return
        name = self.name_var.get() or 'Jogador'
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((host, port))
            self.sock = sock
            self.send_json({'type': 'join', 'name': name})
            self.reader_thread = threading.Thread(target=self.reader_loop, daemon=True)
            self.reader_thread.start()
            self.log('Conectado ao servidor')
        except Exception as e:
            messagebox.showerror('Erro', f'Não foi possível conectar: {e}')

    def resign(self):
        if self.sock:
            self.send_json({'type': 'resign'})

    def send_chat(self):
        txt = self.chat_var.get().strip()
        if not txt or not self.sock:
            return
        self.chat_var.set('')
        self.send_json({'type': 'chat', 'text': txt})
        self.chat_input.focus_set()

    def send_json(self, obj):
        try:
            self.sock.sendall((json.dumps(obj) + '\n').encode('utf-8'))
        except Exception as e:
            self.log(f'Erro ao enviar: {e}')

    def reader_loop(self):
        f = self.sock.makefile('r', encoding='utf-8', newline='\n')
        try:
            for raw in f:
                line = raw.rstrip('\n')
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                self.after(0, self.process_server_msg, obj)
        except Exception as e:
            self.after(0, self.log, f'Leitura interrompida: {e}')

    def process_server_msg(self, msg):
        message_type = msg.get('type')
        if message_type == 'board':
            rows = msg.get('rows', [])
            if len(rows) >= ROWS:
                for y in range(ROWS):
                    for x in range(COLS):
                        self.board[y][x] = rows[y][x] if x < len(rows[y]) else '.'
                self.redraw_board()
            return
        if message_type == 'assign':
            self.my_color = msg.get('color')
            self.lbl_color.config(text=f'Cor: {self.my_color}')
            self.log(f'Cor atribuída: {self.my_color}')
            return
        if message_type == 'turn':
            self.turn = msg.get('color')
            self.lbl_turn.config(text=f'Turno: {self.turn}')
            self.end_turn_enabled = self.my_color == self.turn and msg.get('status') in (None, 'active')
            self.update_end_button_state()
            return
        if message_type == 'turn_pending':
            self.turn = msg.get('color')
            self.lbl_turn.config(text=f'Turno (aguardando encerramento): {self.turn}')
            self.end_turn_enabled = self.my_color == self.turn
            self.update_end_button_state()
            return
        if message_type == 'chat':
            self.log(f"{msg.get('from')}: {msg.get('text')}")
            return
        if message_type == 'move_ok':
            from_position = [value + 1 for value in msg.get('from', [])]
            to_position = [value + 1 for value in msg.get('to', [])]
            self.log(f"Movimento: {msg.get('color')} {from_position} -> {to_position}")
            return
        if message_type == 'choose':
            choice_id = msg.get('choice_id')
            approach_count = msg.get('approach_count')
            withdrawal_count = msg.get('withdrawal_count')
            question = (
                f'As capturas por aproximação ({approach_count}) e afastamento '
                f'({withdrawal_count}) estão disponíveis. Escolher aproximação? '
                '(Não escolhe afastamento)'
            )
            choice = 'approach' if messagebox.askyesno('Escolha da captura', question) else 'withdrawal'
            self.send_json({'type': 'capture_choice', 'choice_id': choice_id, 'choice': choice})
            return
        if message_type == 'game_over':
            self.log(f"Fim de jogo: vencedor {msg.get('winner')}")
            messagebox.showinfo('Fim de jogo', f"Vencedor: {msg.get('winner')}")
            return
        if message_type == 'invalid':
            self.log('Inválido: ' + str(msg.get('reason')))
            return
        if message_type == 'continue':
            self.log('Você pode capturar novamente')
            return
        if message_type == 'error':
            self.log('Erro: ' + str(msg.get('reason')))
            return
        self.log(str(msg))

    def redraw_board(self):
        self.canvas.delete('all')
        self.canvas.create_rectangle(0, 0, CELL_SIZE * COLS, CELL_SIZE * ROWS, fill=COLOR_BG, outline='')

        if self._graph:
            drawn = set()
            for (x, y), neighbors in self._graph.neighbors.items():
                center_x = x * CELL_SIZE + CELL_SIZE / 2
                center_y = y * CELL_SIZE + CELL_SIZE / 2
                for neighbor_x, neighbor_y in neighbors:
                    key = tuple(sorted(((x, y), (neighbor_x, neighbor_y))))
                    if key in drawn:
                        continue
                    drawn.add(key)
                    self.canvas.create_line(
                        center_x,
                        center_y,
                        neighbor_x * CELL_SIZE + CELL_SIZE / 2,
                        neighbor_y * CELL_SIZE + CELL_SIZE / 2,
                        fill=COLOR_LINE,
                        width=2,
                    )

        for y in range(ROWS):
            for x in range(COLS):
                center_x = x * CELL_SIZE + CELL_SIZE / 2
                center_y = y * CELL_SIZE + CELL_SIZE / 2
                node_radius = max(3, CELL_SIZE * 0.06)
                self.canvas.create_oval(
                    center_x - node_radius,
                    center_y - node_radius,
                    center_x + node_radius,
                    center_y + node_radius,
                    fill=COLOR_LINE,
                    outline='',
                )
                value = self.board[y][x]
                if value == 'R':
                    outer_color, inner_color = COLOR_PIECE_R, COLOR_PIECE_R_INNER
                elif value == 'P':
                    outer_color, inner_color = COLOR_PIECE_P, COLOR_PIECE_P_INNER
                else:
                    continue
                outer_radius = CELL_SIZE * 0.30
                inner_radius = CELL_SIZE * 0.20
                self.canvas.create_oval(
                    center_x - outer_radius,
                    center_y - outer_radius,
                    center_x + outer_radius,
                    center_y + outer_radius,
                    fill=outer_color,
                    outline=COLOR_LINE,
                    width=2,
                )
                self.canvas.create_oval(
                    center_x - inner_radius,
                    center_y - inner_radius,
                    center_x + inner_radius,
                    center_y + inner_radius,
                    fill=inner_color,
                    outline='',
                )

        if self.selection:
            x, y = self.selection
            self.canvas.create_rectangle(
                x * CELL_SIZE + 2,
                y * CELL_SIZE + 2,
                (x + 1) * CELL_SIZE - 2,
                (y + 1) * CELL_SIZE - 2,
                outline='yellow',
                width=3,
            )

    def on_canvas_click(self, event):
        x = int(event.x // CELL_SIZE)
        y = int(event.y // CELL_SIZE)
        if x < 0 or x >= COLS or y < 0 or y >= ROWS or not self.sock or not self.my_color:
            return
        current = self.board[y][x]
        if self.selection is None:
            if current == self.my_color:
                self.selection = (x, y)
                self.redraw_board()
            else:
                self.log('Selecione uma peça sua para mover')
            return
        source_x, source_y = self.selection
        if (source_x, source_y) == (x, y):
            self.selection = None
            self.redraw_board()
            return
        self.send_json({'type': 'move', 'from': [source_x, source_y], 'to': [x, y]})
        self.selection = None
        self.redraw_board()

    def log(self, message):
        self.chat.config(state='normal')
        self.chat.insert('end', message + '\n')
        self.chat.see('end')
        self.chat.config(state='disabled')

    def on_close(self):
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass
        self.destroy()


if __name__ == '__main__':
    app = GUIClient()
    app.protocol('WM_DELETE_WINDOW', app.on_close)
    app.mainloop()
