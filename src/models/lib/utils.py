import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import google.generativeai as genai
import openai
import tiktoken
from loguru import logger
from src.models.lib.prompt import GET_BEST_QUOLITY_PROMPT


def normalize_text(text: str) -> str:
    """Normalize the text."""
    text = re.sub(r"「|」", "", text)
    text = re.sub(r"；|;", "", text)
    text = re.sub(r":|：", "", text)
    text = re.sub(r"’|'", "", text)
    text = re.sub(r"　", "", text)      # 全角を削除
    text = re.sub(r"\(|\)", "", text)
    text = re.sub(r"XXX", "", text)
    text = re.sub(r"♪", "", text)
    text = re.sub(r'\.', '。', text)
    return text


def make_unified_prompt_from_list(responses: list[str]) -> str:
    prompt: str = GET_BEST_QUOLITY_PROMPT.format(len(responses))
    for idx, response in enumerate(responses):
        prompt += f"- {idx}\n{response}\n==============\n"
    return prompt


def check_towards_me(
    chat_history: list[dict[str, str]], index_sentence: str
) -> dict[str, str] | None:
    """Check if the chat history is directed towards me.

    Args:
        chat_history (list[dict[str, str]]): list of chat history
        index_sentence (str): Sentence that contains the index of the agent

    Returns:
        dict[str, str] | None: Dictionary that contains the agent and the text if the chat history is directed towards me, otherwise None
    """
    my_idx: int = re.sub(r"\D", "", index_sentence)[1]
    for chat in chat_history:
        if f">>Agent[0{my_idx}]" in chat["text"]:
            return {"from": chat["agent"], "text": chat["text"]}
    return None


def get_until_today_history(chat_history: list[dict[str, str]]) -> str:
    """Get the chat history for each day.

    Args:
        chat_history (list[dict[str, str]]): list of chat history.

    Returns:
        str: chat history for each day with markdown format.
    """
    today: int = chat_history[-1]["day"]
    until_today_history: str = ""
    for day in range(today + 1):
        day_history: str = get_chat_history(
            [chat for chat in chat_history if chat["day"] == day]
        )
        if day_history != "":
            until_today_history += f"### {day}日目\n" + day_history
    return until_today_history


def get_chat_history(chat_history: list[dict[str, str]]) -> str:
    """Get chat history from the list of chat history and formatting that LLM can read.

    Args:
        chat_history (list[dict[str, str]]): list of chat history

    Returns:
        str: chat history that is be concatenated with the role and message
    """
    concatenated_history: str = ""
    for chat in chat_history:
        concatenated_history += f"Agent[0{chat['agent']}]: {chat['text']}\n"
    return concatenated_history


def output_log(
    model: str,
    response: Any,
    elapsed_time: float,
    prompts: list[dict[str, str]],
    output: str,
) -> None:
    """Output log to the log file.

    Args:
        model (str): "gemini-pro", "gpt-3.5-turbo" or "gpt-4"
        response (Any): response from the model
        elapsed_time (float): elapsed time for the response
        prompts (list[str]): list of prompts
        output (str): output from the model
    """
    log_path = Path("logs")
    log_path.mkdir(parents=True, exist_ok=True)
    log_file = log_path / f"{datetime.now().strftime('%Y-%m-%d-%H:%M')}.log"

    logging.basicConfig(filename=log_file, level=logging.INFO, format="")

    if model == "gemini-pro":
        logging.info("model: gemini-pro")
        logging.info("costs: $0")
        logging.info(f"elapsed_time: {elapsed_time:.3f} sec")
        logging.info(f"prompts:")
        if isinstance(prompts, list):
            for prompt in prompts:
                logging.info(prompt)
        else:
            # prompts is a string
            logging.info(prompts)
        logging.info(f"output: {output}")
    else:
        costs: float = 0.0
        total_tokens = response.usage.total_tokens
        logging.info(f"model: {model}")
        logging.info(f"total_tokens: {total_tokens}")
        logging.info(f"elapsed_time: {elapsed_time:.3f} sec")
        if model == "gpt-3.5-turbo":
            costs = total_tokens * 0.0015 / 1000
            logging.info(f"costs: ${costs}")
        else:
            costs = total_tokens * 0.06 / 1000
            logging.info(f"costs: {costs}")
        logging.info(f"prompts:")
        if isinstance(prompts, list):
            (
                user_counts,
                system_counts,
                assistant_counts,
                overall_counts,
            ) = num_tokens_from_string(prompts)
            logging.info(f"user_num_tokens: {user_counts}")
            logging.info(f"system_num_tokens: {system_counts}")
            logging.info(f"assistant_num_tokens: {assistant_counts}")
            logging.info(f"overall_intput_num_tokens: {overall_counts}")
        else:
            # prompts is a string
            logging.info(prompts)
        logging.info(f"output: {output}")


def list_google_model() -> None:
    """List all the available models on Google AI."""
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    for model in genai.list_models():
        if "generateContent" in model.supported_generation_methods:
            logger.info(model.name)


def list_openai_model() -> None:
    """List all the available models on OpenAI."""
    models = openai.Model.list()

    for model in models.data:
        logger.info(f"{model.id}")


def num_tokens_from_string(
    messages: list[dict[str, str]], model_name: str = "gpt-4-0125-preview"
) -> tuple[int, int, int, int]:
    """Returns the number of tokens in a text string."""
    encoding = tiktoken.encoding_for_model(model_name)
    user_num_tokens = sum(
        len(encoding.encode(message["content"]))
        for message in messages
        if message["role"] == "user"
    )
    system_num_tokens = sum(
        len(encoding.encode(message["content"]))
        for message in messages
        if message["role"] == "system"
    )
    assistant_num_tokens = sum(
        len(encoding.encode(message["content"]))
        for message in messages
        if message["role"] == "assistant"
    )
    num_tokens = user_num_tokens + system_num_tokens + assistant_num_tokens
    return user_num_tokens, system_num_tokens, assistant_num_tokens, num_tokens


if __name__ == "__main__":
    messages = [
        {"role": "user", "content": "I want to buy a car."},
        {"role": "system", "content": "Sure, what kind of car are you looking for?"},
        {"role": "assistant", "content": "I can help you with that."},
    ]
    (
        user_num_tokens,
        system_num_tokens,
        assistant_num_tokens,
        num_tokens,
    ) = num_tokens_from_string(messages)
    print(f"user_num_tokens: {user_num_tokens}")
    print(f"system_num_tokens: {system_num_tokens}")
    print(f"assistant_num_tokens: {assistant_num_tokens}")
    print(f"num_tokens: {num_tokens}")
