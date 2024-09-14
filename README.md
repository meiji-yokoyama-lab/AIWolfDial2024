# NLP-Wolf

[ 日本語 | [**English**](./README.en.md) ]


## 参考

本プロジェクトは<https://github.com/aiwolfdial/AIWolfNLAgentPython>をベースに作成されています。


## セットアップ
```bash
python3 -m venv venv

. venv/bin/activate

pip3 install -r requirements.txt
```


## APIの管理
すでにdirenvをインストールをしている場合は、スキップしていただいて構いません。
```bash
# Homebrew
brew install direnv

# apt package
sudo apt install -y direnv
```

サンプルファイルを複製する。
```bash
cp .envrc.sample .envrc
```

.envrcにAPIキーをペーストし、その後direnvをロードする。

```bash
direnv allow
```

APIキーがexportされたらok。


## Agentの起動

`README.md`があるディレクトリから実行する。

```bash
python3 src/agent/multiprocess.py
```


## 対戦サーバの起動

サーバは<https://github.com/aiwolfdial/AIWolfNLGameServer>を利用してください。

サーバからクライアントに接続する自己対戦モードで実行してください。


## バージョン管理

`Native Linux (特にUbuntu) or WSL`

WindowsやMacOSでの動作には対応していません。

`python3.11.7`

作成したモデルを動かすためのバージョン。

`Java JDK17`

対戦用のサーバを動かすためのバージョン。
