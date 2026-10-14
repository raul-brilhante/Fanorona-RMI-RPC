# Fanorona over Pyro5 RMI/RPC

Jogo de Fanorona em Python com um servico autoritativo Pyro5 e dois clientes
graficos. A logica do jogo permanece em `game.py`; somente a camada de
comunicacao foi substituida por chamadas remotas de metodos.

## Requisitos

- Python 3.8+
- Pyro5 (`python -m pip install -r requirements.txt`)

## Como executar

Na maquina que hospedara a partida:

```bash
python server.py --host 0.0.0.0 --port 5000
```

Em cada uma das duas maquinas:

```bash
python gui_client.py
```

Na GUI, informe o IP da maquina do servidor e a porta `5000`. O servidor aceita
exatamente dois jogadores. O cliente registra um callback Pyro5 proprio;
depois de cada movimento, o servidor invoca esse callback em ambos os clientes,
enviando o novo estado do tabuleiro e o evento correspondente.

Pyro5 foi escolhido por oferecer RMI orientado a objetos (metodos e callbacks
remotos) sem criar um protocolo textual artesanal. O servidor mantem o unico
estado de `Game`, enquanto `rpc_client.py` e `rpc_server.py` isolam o
transporte.

## Regras preservadas

- O tabuleiro usa as conexoes horizontais, verticais e diagonais do Fanorona.
- Capturas por aproximacao e afastamento, sequencias, bloqueio, vitoria e
  empate continuam implementados em `game.py`.
- O servidor apenas coordena chamadas e sincroniza o estado existente.

## Build / Executaveis

Voce pode criar executaveis Windows usando `PyInstaller`:

```powershell
python -m pip install --upgrade pyinstaller
.\build_exe.bat
```

Os binarios gerados (`fanorona_server.exe`, `fanorona_gui.exe`) ficarao em
`dist`.

O projeto usa `tkinter` e Pyro5 em runtime. O Pyro5 usa sua propria camada de
transporte internamente; a aplicacao nao importa nem manipula `socket`,
`select`, buffers ou mensagens JSON.
