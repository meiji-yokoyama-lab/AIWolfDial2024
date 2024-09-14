import concurrent.futures
import json
import os
import time
from typing import Optional

import google.generativeai as genai
import requests
from retry import retry

from src.models.gpt.main import GptClass
from src.models.lib.generate_message import make_messages
from src.models.lib.prompt import *
from src.models.lib.utils import (get_chat_history,
                                  make_unified_prompt_from_list, output_log)


class GeminiClass:
    def __init__(self) -> None:
        genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
        self.model: str = "gemini-pro"
        self.max_tokens: int = 500
        self.stop_words = None
        self.temperature: float = 0.7
        self.candidate: int = 1
        self.timeout_seconds: float = 4.5
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={os.environ['GEMINI_API_KEY']}"
        self.header = {"Content-Type": "application/json"}

    def make_gemini_format_message(
        self,
        system_call: dict[str, str],
        chat_history: list[dict[str, str | int]],
        towards_me: list[dict[str, str]] = [],
    ) -> str:
        system_prompt, user_prompt = make_messages(
            system_call, chat_history, towards_me
        )
        content_message: str = system_prompt + "\n## やるべきこと\n" + user_prompt
        return content_message

    @retry(tries=3, backoff=0, jitter=0, max_delay=None, delay=0.3)
    def multi_turn_chat_completion(
        self,
        system_call: dict[str, str],
        chat_history: list[dict[str, int | str]],
        towards_me: list[dict[str, str]] = [],
        is_multi_process: bool = False,
        n_samples: int = 3,
        next_model: Optional[str] = "gemini-pro",
    ) -> str:
        start_time = time.time()
        messages: list[dict[str, str]] = [
            {"role": "user", "parts": {"text": GEMINI_USER_PROMPT}},
            {"role": "model", "parts": {"text": GEMINI_MODEL_PROMPT}},
            {
                "role": "user",
                "parts": {
                    "text": self.make_gemini_format_message(
                        system_call, chat_history, towards_me
                    )
                },
            },
        ]
        if is_multi_process and n_samples > 1 and next_model:
            # 並列処理
            # 並列化させるためにnコのpromptを作成
            prompts: list[list[dict[str, str]]] = [messages] * n_samples

            with concurrent.futures.ThreadPoolExecutor() as executor:
                responses: list[str] = list(
                    executor.map(
                        lambda prompt: requests.post(
                            url=self.url,
                            headers=self.header,
                            json={
                                "contents": prompt,
                                "safety_settings": {
                                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                                    "threshold": "BLOCK_LOW_AND_ABOVE",
                                },
                                "generation_config": {
                                    "max_output_tokens": self.max_tokens,
                                    "stop_sequences": self.stop_words,
                                    "temperature": self.temperature,
                                    "candidate_count": self.candidate,
                                },
                            },
                            timeout=self.timeout_seconds,
                        ).json(),
                        prompts,
                    )
                )
                if "gemini" in next_model:
                    response = self.chat_completion(
                        make_unified_prompt_from_list(responses)
                    )
                else:
                    raise "next_modelは循環参照を避けるためにGeminiのみ対応しています"
                    response = GptClass().chat_completion(
                        make_unified_prompt_from_list("", responses)
                    )
        else:
            # 同期処理
            try:
                response_json = requests.post(
                    url=self.url,
                    headers=self.header,
                    json={
                        "contents": messages,
                        "safety_settings": {
                            "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                            "threshold": "BLOCK_LOW_AND_ABOVE",
                        },
                        "generation_config": {
                            "max_output_tokens": self.max_tokens,
                            "stop_sequences": self.stop_words,
                            "temperature": self.temperature,
                            "candidate_count": self.candidate,
                        },
                    },
                    timeout=self.timeout_seconds,
                ).json()
                response = response_json["candidates"][0]["content"]["parts"][0]["text"]
            except:
                # TODO: 5s以内で返答が帰ってこなかった場合
                response = "Timeout"
        elapsed_time: float = time.time() - start_time
        output_log(self.model, response, elapsed_time, messages, response)
        return response

    @retry(tries=3, backoff=0, jitter=0, max_delay=None, delay=0.3)
    def chat_completion(self, input_text: str) -> str:
        try:
            response_json = requests.post(
                url=self.url,
                headers=self.header,
                json={
                    "contents": {"role": "user", "parts": {"text": input_text}},
                    "safety_settings": {
                        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        "threshold": "BLOCK_LOW_AND_ABOVE",
                    },
                    "generation_config": {
                        "max_output_tokens": self.max_tokens,
                        "stop_sequences": self.stop_words,
                        "temperature": self.temperature,
                        "candidate_count": self.candidate,
                    },
                },
                timeout=self.timeout_seconds,
            ).json()
            response = response_json["candidates"][0]["content"]["parts"][0]["text"]
        except:
            # TODO: 5s以内で返答が帰ってこなかった場合
            response = "Timeout"
        return response

    def summarize_day(self, chat_history: list[dict[str, str | int]], day: int) -> str:
        user_prompt: str = get_chat_history(chat_history) + DAY_SUMMARY_END.format(day)
        return self.chat_completion(DAY_SUMMARY_START.format(day) + "\n" + user_prompt)


def main() -> None:
    App = GeminiClass()
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
    dayily_summarize: bool = True
    if dayily_summarize:
        result = App.multi_turn_chat_completion(
            system_call=system_call,
            chat_history=chat_history,
            towards_me=[],
            is_multi_process=True,
            n_samples=3,
            next_model="gemini-pro",
        )

    # day日目のrandomターン目の発話を生成
    turn_summarize: bool = False
    if turn_summarize:
        import random

        chat_history_until_now = []
        for history in day_history:
            if random.randint(1, 3) == 1 and history["agent"] == index:
                result = App.multi_turn_chat_completion(
                    system_call=system_call,
                    chat_history=chat_history_until_now,
                    is_multi_process=False,
                    n_samples=3,
                    next_model="gemini-pro",
                )
                break
            chat_history_until_now.append(history)
    print(result)


if __name__ == "__main__":
    main()
