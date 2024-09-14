import configparser
import errno
import os
import random


def read_text(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return f.read().splitlines()


def random_select(data: list):
    return random.choice(data)


def is_json_complate(responces: bytes) -> bool:
    try:
        responces = responces.decode("utf-8")
    except:
        return False

    if responces == "":
        return False

    cnt = 0

    for word in responces:
        if word == "{":
            cnt += 1
        elif word == "}":
            cnt -= 1

    return cnt == 0


def check_config(config_path: str) -> configparser.ConfigParser:
    if not os.path.exists(config_path):
        raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), config_path)

    return configparser.ConfigParser()
