Fanorona over Sockets (prototype)

Protótipo em Python para jogar Fanorona via sockets (servidor + 2 clientes gráficos).
Durante uma partida, o servidor aceita exatamente dois jogadores. Conexões
adicionais recebem um erro JSON (`game_full`) e são encerradas.

Requisitos

- Python 3.8+

Como executar

1) Abra um terminal e rode o servidor:

```bash
python server.py
```

2) Use a interface gráfica (`gui_client.py`) em duas máquinas (ou na mesma máquina em janelas diferentes):

```bash
python gui_client.py
```

As peças usam as letras `R` (vermelha) e `P` (rosa) no protocolo e no tabuleiro.

Protocolo de rede

O servidor e clientes usam NDJSON (uma mensagem JSON por linha) com mensagens como:

- Cliente -> Servidor:
	- `{"type":"join","name":"Raul"}`
	- `{"type":"chat","text":"boa sorte"}`
	- `{"type":"move","from":[x1,y1],"to":[x2,y2]}`
	- `{"type":"resign"}`
	- `{"type":"get_board"}`

- Servidor -> Cliente:
	- `{"type":"error","reason":"game_full"}`
	- `{"type":"assign","color":"R"}`
	- `{"type":"board","rows":["PPPPPPPPP",... ]}`
	- `{"type":"turn","color":"R"}`
	- `{"type":"move_ok","color":"R","from":[x1,y1],"to":[x2,y2],"captured":[[cx,cy],...]}`
	- `{"type":"chat","from":"Cidcley","text":"oi"}`
	- `{"type":"game_over","winner":"P"}`

	Todas as mensagens do protocolo são objetos JSON delimitados por uma quebra de
	linha. Não há mensagem inicial em texto puro; o primeiro evento útil recebido
	pelo cliente é uma mensagem JSON do servidor.

Observações

- O tabuleiro usa as conexões horizontais, verticais e diagonais do Fanorona; capturas são aplicadas quando o movimento escolhido as produz.
- Durante uma sequência de capturas, o servidor mantém o histórico das posições
	visitadas pela peça e impede que ela passe duas vezes pelo mesmo ponto. Esse
	histórico é limpo ao finalizar o turno e não bloqueia movimentos de turnos
	posteriores.
- A partida também detecta vitória por bloqueio e empate após 50 turnos consecutivos sem captura.

Build / Executáveis

Você pode criar executáveis Windows usando `PyInstaller`. Um helper `build_exe.bat` foi incluído no repositório.

Exemplo (PowerShell):

```powershell
python -m pip install --upgrade pip
python -m pip install --upgrade pyinstaller
.\build_exe.bat
```

Os binários gerados (`fanorona_server.exe`, `fanorona_gui.exe`) ficarão na pasta `dist`.

Se preferir rodar manualmente o PyInstaller:

```powershell
pyinstaller --onefile --name fanorona_server server.py
pyinstaller --noconsole --onefile --name fanorona_gui gui_client.py
```

Observações:
- O projeto usa apenas módulos da stdlib (`socket`, `threading`, `json`, `tkinter`), então não há dependências de runtime além do Python e do `pyinstaller` para build.