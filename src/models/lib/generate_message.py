from typing import Optional, Union

from src.models.lib.prompt import *
from src.models.lib.utils import get_until_today_history


def make_messages(
    system_call: dict[str, str],
    chat_history: Optional[list[dict[str, Union[str, int]]]],
    towards_me: list[dict[str, str]] = [],
) -> tuple[str, str]:
    content_message: str = ""
    request: str = system_call.get("request")
    behavior: str = system_call.get("behavior")
    idx: str = system_call.get("idx")
    alive: str = system_call.get("alive")
    dead: str = system_call.get("dead")
    target: str = system_call.get("target")

    map_to_personas = {
        'Agent[00]': PERSONA_0, # Avoid error
        'Agent[01]': PERSONA_1,
        'Agent[02]': PERSONA_2,
        'Agent[03]': PERSONA_3,
        'Agent[04]': PERSONA_4,
        'Agent[05]': PERSONA_5,
    }

    if request == "greet":
        content_message += MY_NUMBER.format(idx)
    elif request == "vote" or request == "divine" or request == "attack":
        content_message += MY_NUMBER.format(idx)
        if chat_history:
            content_message += CHAT_HISTORY_START + get_until_today_history(
                chat_history
            )
        content_message += TARGET.format(target)
    else:
        content_message += (
            GENERAL + RULE.format(PERSONA=map_to_personas[idx])+ YOURSELF.format(idx) + ALIVE.format(alive)
        )
        if dead:
            content_message += DEAD.format(dead)
        content_message += {
            "VILLAGER": VILLAGER,
            "SEER": SEER,
            "POSSESSED": POSSESSED,
            "WEREWOLF": WEREWOLF,
        }.get(behavior, "")
        content_message += UNDERSTAND + OUTPUT

        if chat_history:
            content_message += (
                CHAT_HISTORY_START
                + INPUT
                + get_until_today_history(chat_history)
                + PREDICT_OUTPUT_SYMBOL.format(idx)
            )

        if towards_me:
            towards_content = towards_me[0]
            content_message += TOWARDS_ME.format(
                towards_content["from"], towards_content["text"]
            )

    # gptの場合, role:systemにcontent_message, role:userにACTION.get(request, "")を返す
    return content_message, ACTION.get(request, "")
