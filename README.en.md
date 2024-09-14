# NLP-Wolf

[ [**日本語**](./README.md) | English ]


## Reference

This project is based on <https://github.com/aiwolfdial/AIWolfNLAgentPython>.


## Before you run
```bash
python3 -m venv venv

. venv/bin/activate

pip3 install -r requirements.txt
```

## Init direnv
If you have already installed direnv, you can skip the below command.
```bash
# Homebrew
brew install direnv

# apt package
sudo apt install -y direnv
```

Copy the sample file to origin file.
```bash
cp .envrc.sample .envrc
```

Paste the API key in the `.envrc` file.

After that, you need direnv to load that file.

```bash
direnv allow
```

If your api key is printed in your terminal, it means successful.


## Activate the Agent

Execute command in the same directory level with `README.en.md`.

Before you start, you need to activate self-match server.
```bash
python3 src/agent/multiprocess.py
```

## Activate the Server

Servers should use <https://github.com/aiwolfdial/AIWolfNLGameServer>.

Run in self-play method, connecting from the server to the client.

## Version

`Native Linux (especially Ubuntu) or WSL`.

It does not support operation under Windows or MacOS.

`python3.11.7`

Execute our implemented agent.

`Java JDK17`

Activate the server.
