import json
import os
import re

import requests
from openai import OpenAI
from retry import retry

from src.models.lib.generate_message import make_messages
from src.models.lib.prompt import *
from src.models.lib.utils import (get_chat_history,
                                  make_unified_prompt_from_list,
                                  normalize_text)


class GptClass:
    def __init__(self) -> None:
        self.client = OpenAI()
        self.max_tokens: int = 200
        self.n: int = 1  # 原則使わない
        self.stop_words = None
        self.temperature: float = 1.0
        self.presence_penalty: float = 0.0
        self.frequency_penalty: float = 0.0
        self.timeout_seconds: float = 4.5
        self.url = "https://api.openai.com/v1/chat/completions"

    def make_gpt_format_message(
        self,
        system_call: dict[str, str],
        chat_history: list[dict[str, str | int]],
        towards_me: list[dict[str, str]] = [],
    ) -> str:
        system_prompt, user_prompt = make_messages(
            system_call, chat_history, towards_me
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    @retry(tries=3, backoff=0, jitter=0, max_delay=None, delay=0.3)
    def multi_turn_chat_completion(
        self,
        system_call: dict[str, str],
        chat_history: list[dict[str, str | int]],
        towards_me: list[dict[str, str]] = [],
        model: str = "gpt-3.5-turbo",
        is_multi_process: bool = False,
        n_samples: int = 1,
    ) -> str:
        messages: list[dict[str, str]] = self.make_gpt_format_message(
            system_call, chat_history, towards_me
        )

        if is_multi_process and n_samples > 1:
            try:
                responses_json = requests.post(
                    url=self.url,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": "Bearer " + os.getenv("OPENAI_API_KEY"),
                    },
                    json={
                        "model": model,
                        "messages": messages,
                        "temperature": self.temperature,
                        "max_tokens": self.max_tokens,
                        "stop": self.stop_words,
                        "presence_penalty": self.presence_penalty,
                        "frequency_penalty": self.frequency_penalty,
                        "n": n_samples,
                    },
                    timeout=self.timeout_seconds,
                ).json()
                responses: list[str] = [
                    responses_json["choices"][i]["message"]["content"]
                    for i in range(n_samples)
                ]
                response = self.chat_completion(
                    "", make_unified_prompt_from_list("", responses)
                )
            except:
                # サーバーエラーもこっちに飛ぶ
                response = "Timeout"
        else:
            try:
                response_json = requests.post(
                    url=self.url,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": "Bearer " + os.getenv("OPENAI_API_KEY"),
                        "OpenAI-Organization": os.getenv("OPENAI_ORG_ID"),
                    },
                    json={
                        "model": model,
                        "messages": messages,
                        "temperature": self.temperature,
                        "max_tokens": self.max_tokens,
                        "stop": self.stop_words,
                        "presence_penalty": self.presence_penalty,
                        "frequency_penalty": self.frequency_penalty,
                    },
                    timeout=self.timeout_seconds,
                ).json()
                response: str = response_json["choices"][0]["message"]["content"]
            except:
                # サーバーエラーもこっちに飛ぶ
                response = "Timeout"
        result = response.replace("\n", "")
        if system_call["request"] == "vote" or system_call["request"] == "divine" or system_call["request"] == "attack":
            result = int(re.sub(r"\D", "", result))
        else:
            result = re.sub(r"Agent\[0\d\]: ", "", result)
            result = normalize_text(result)
        return result

    def chat_completion(self, system_prompt: str, user_prompt: str, model: str = "gpt-3.5-turbo") -> str:
        messages: list[dict[str, str]] = [
            {"role": "user", "content": user_prompt},
            {"role": "system", "content": system_prompt},
        ]
        try:
            response_json = requests.post(
                url=self.url,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + os.getenv("OPENAI_API_KEY"),
                    "OpenAI-Organization": os.getenv("OPENAI_ORG_ID"),
                },
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                    "stop": self.stop_words,
                    "presence_penalty": self.presence_penalty,
                    "frequency_penalty": self.frequency_penalty,
                },
                timeout=self.timeout_seconds,
            ).json()
            response = response_json["choices"][0]["message"]["content"]
        except:
            # サーバーエラーもこっちに飛ぶ
            response = "Timeout"
        return response

    def summarize_day(self, chat_history: list[dict[str, str | int]], day: int) -> str:
        user_prompt: str = get_chat_history(chat_history) + DAY_SUMMARY_END.format(day)
        return self.chat_completion(DAY_SUMMARY_START.format(day), user_prompt)
    
    def vote_declare(self, chat_history: list[dict[str, str | int]], idx: int, queue):
        system_prompt: str = SYSTEM_VOTE_DECLARE.format(get_chat_history(chat_history), str(idx))
        user_prompt: str = USER_VOTE_DECLARE
        result = self.chat_completion(system_prompt, user_prompt, "gpt-4o-mini")
        vote_dict = {}
        if result != "Timeout" and "one" not in result:
            vote_list = result.split("\n")
            for vote in vote_list:
                try:
                    vote = re.sub(r"\D", "", vote)
                    actor = int(vote[1])
                    target = int(vote[3])
                    if actor != 6:
                        vote_dict[actor] = target
                except:
                    pass
        queue.put(vote_dict)
    
    def seer_declare(self, chat_history: list[dict[str, str | int]], idx: int, queue):
        system_prompt: str = SYSTEM_SEER_DECLARE.format(get_chat_history(chat_history), str(idx))
        user_prompt: str = USER_SEER_DECLARE
        result = self.chat_completion(system_prompt, user_prompt, "gpt-4o-mini")
        seer_info = []
        if result != "Timeout" and "one" not in result:
            seer_list = result.split("\n")
            for seer in seer_list:
                try:
                    actor, target, report = seer.split(", ")
                    actor = int(re.sub(r"\D", "", actor))
                    target = int(re.sub(r"\D", "", target))
                    if actor != 6:
                        seer_info.append({"actor": actor, "target": target, "report": report})
                except:
                    pass
        queue.put(seer_info)
    
    def pipe_model2agent(
        self,
        system_call: dict[str, str],
        chat_history: list[dict[str, str | int]],
        towards_me: list[dict[str, str]] = [],
        queue = None,
        ) -> None:
        result = self.multi_turn_chat_completion(system_call, chat_history, towards_me)
        queue.put(result)


def main() -> None:
    App = GptClass()
    index = 3
    alive_agents = ["Agent[01]", "Agent[02]", "Agent[03]", "Agent[04]", "Agent[05]"]
    system_call = {
        "request": "talk",
        "idx": f"Agent[0{index}]",
        "alive": ", ".join(alive_agents),
        "behavior": "SEER",
    }
    with open("data/sample.json") as f:
        chat_history: list[dict[str, str]] = json.load(f)

    # day日目のchat_historyを取得
    day = 1
    day_history = [history for history in chat_history if history["day"] == day]
    result = "Nothing to do."

    # day日目の要約+(day+1)日目1ターン目の発話を生成
    dayily_summarize: bool = False
    if dayily_summarize:
        result = App.multi_turn_chat_completion(
            system_call, chat_history, App.summarize_day(day_history, day)
        )

    # day日目のrandomターン目の発話を生成
    turn_summarize: bool = True
    if turn_summarize:
        import random

        chat_history_until_now = []
        for history in day_history:
            if random.randint(1, 3) == 1 and history["agent"] == index:
                result = App.multi_turn_chat_completion(
                    system_call=system_call,
                    chat_history=chat_history_until_now,
                    model="gpt-3.5-turbo",
                    is_multi_process=False,
                    n_samples=3,
                )
                break
            chat_history_until_now.append(history)
    print(result)


if __name__ == "__main__":
    main()
