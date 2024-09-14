import json
import random
from multiprocessing import Process, Queue

from lib import util
from lib.commands import AIWolfCommand

from src.agent.lib.template import *
from src.models.gpt.main import GptClass
from src.models.gemini.main import GeminiClass


class Agent:
    def __init__(self, name: str) -> None:
        self.name = name
        self.received = []
        self.gameContinue = True
        model = "gpt"
        if model == "gpt":
            self.model = GptClass()
        else:
            self.model = GeminiClass()
        self.system_call = {
            "request": str,
            "idx": str,
            "alive": str,
            "target": str,
            "behavior": str,
        }

    def set_received(self, received: list) -> None:
        self.received = received

    def parse_info(self, receive: str) -> None:
        received_list = receive.split("}\n{")

        for index in range(len(received_list)):
            received_list[index] = received_list[index].rstrip()

            if received_list[index][0] != "{":
                received_list[index] = "{" + received_list[index]

            if received_list[index][-1] != "}":
                received_list[index] += "}"

            self.received.append(received_list[index])

    def get_info(self):
        data = json.loads(self.received.pop(0))
        self.request = data["request"]
        # ゲームの情報が変更されていれば適応
        if data["gameInfo"]:
            self.gameInfo = data["gameInfo"]
        if data["gameSetting"]:
            self.gameSetting = data["gameSetting"]
        # 発話履歴に更新があったか
        self.talkHistory = data["talkHistory"]
        if self.talkHistory:
            for talk in self.talkHistory:
                if talk["text"] == "Skip":
                    talk["text"] = SKIP[0]
                elif talk["text"] == "Over":
                    talk["text"] = OVER
                self.all_history.append(talk)

    def initialize(self) -> None:
        self.index = self.gameInfo["agent"]
        self.role = self.gameInfo["roleMap"][str(self.index)]
        self.day_count = -1
        self.all_history = []

    def daily_initialize(self) -> None:
        self.day_count += 1
        self.talk_count = 0
        self.reply = 0
        self.vote_dict = {}
        self.seer_dict = {}
        self.is_close = False
        self.alive = [
            int(agent)
            for agent in self.gameInfo["statusMap"]
            if self.gameInfo["statusMap"][agent] == "ALIVE"
        ]

        # 生存者と死亡者
        alive_list: list = []
        dead_list: list = []
        for agent_num in self.gameInfo["statusMap"]:
            if self.gameInfo["statusMap"][agent_num] == "ALIVE":
                alive_list.append(f"Agent[0{agent_num}]")
            else:
                dead_list.append(f"Agent[0{agent_num}]")

        # 各役職の振る舞い
        self.divine_result = ""
        if self.role == "SEER":
            if self.gameInfo["divineResult"]:
                divined = self.gameInfo["divineResult"]
                result = "人間" if divined["result"] == "HUMAN" else "人狼"
                self.divine_result = SEER_DECLARE[self.index].format(divined["target"], result)
            behavior = "SEER"
        elif self.role == "POSSESSED":
            if self.day_count == 2:
                behavior = "POSSESSED"
            else:
                behavior = "VILLAGER"
        else:
            behavior = "VILLAGER"

        # talkで使うsystem_call
        self.system_call = {
            "idx": f"Agent[0{self.index}]",
            "alive": ", ".join(alive_list),
            "dead": ", ".join(dead_list),
            "behavior": behavior,
        }

    def daily_finish(self) -> None:
        self.all_history = [
            talk
            for talk in self.all_history
            if talk["text"] != SKIP[0] and talk["text"] != OVER
        ]

    def get_name(self) -> str:
        return self.name

    def get_role(self) -> str:
        return self.role

    def talk(self) -> str:
        self.talk_count += 1
        # 1巡分の発話分析
        towards_me = []
        for chat in self.talkHistory:
            if f">>Agent[0{self.index}]" in chat["text"]:
                towards_me.append({"from": chat["agent"], "text": chat["text"][12:]})
            elif OVER in chat["text"]:
                if not self.vote_dict.get(chat["agent"]):
                    self.vote_dict[chat["agent"]] = 0
        if len(towards_me) != 1:
            towards_me = []
        # 発話生成
        if self.is_close:
            comment = "Over"
        elif self.day_count == 0:
            if self.talk_count == 1:
                comment = GLHF[self.index].format(self.index)
            else:
                comment = "Over"
        else:
            is_seer_analyze = self.day_count == 1 and ((self.talk_count < 4 and self.role == "WEREWOLF") or (self.talk_count < 3 and self.role == "POSSESSED"))
            if is_seer_analyze:
                q3 = Queue()
                before = [history for history in self.all_history if history["day"] == 1]
                p3 = Process(target=self.model.seer_declare, args=(before, self.index, q3))
                p3.start()
            q1 = Queue()
            p1 = Process(target=self.model.vote_declare, args=(self.talkHistory, self.index, q1))
            p1.start()
            if self.divine_result and self.talk_count == 1:
                comment = self.divine_result
            elif self.role == "POSSESSED" and self.talk_count == 1 and self.day_count == 2:
                comment = WEREWOLF_DECLARE[self.index].format(self.index)
            elif not self.talkHistory:
                comment = DAY1_MORNING[self.index] if self.day_count == 1 else DAY2_MORNING[self.index]
            else:
                self.system_call["request"] = "talk"
                is_strike = (self.day_count == 1 and self.talk_count == 3) or (self.day_count == 2 and self.talk_count == 2)
                if is_strike:
                    self.system_call["request"] = "strike"
                q2 = Queue()
                p2 = Process(target=self.model.pipe_model2agent,
                             args=(self.system_call, self.all_history, towards_me, q2))
                p2.start()
                comment = self.model.multi_turn_chat_completion(
                    self.system_call, self.all_history, towards_me, "gpt-4"
                )
                p2.join()
            # 保険
            if comment == "Timeout":
                comment = q2.get()
            # 保険の保険
            if comment == "Timeout":
                comment = SKIP[self.index]
            # 占いCOの分析
            if is_seer_analyze:
                p3.join()
                seer_info: list = q3.get()
                if self.role == "WEREWOLF":
                    alert = False
                    for info in seer_info:
                        if info["actor"] == self.index:
                            continue
                        elif info["report"] == "白" and info["target"] == self.index:
                            self.seer_dict[info["actor"]] = "poss"
                        elif info["report"] == "白" and info["target"] != self.index:
                            self.seer_dict[info["actor"]] = "seer"
                        elif info["report"] == "黒" and info["target"] != self.index:
                            self.seer_dict[info["actor"]] = "poss"
                        elif info["report"] == "黒" and info["target"] == self.index:
                            self.seer_dict[info["actor"]] = "seer"
                            alert = True
                            target = info["actor"]
                    if alert and self.system_call["behavior"] != "SEER" and len(self.seer_dict) == 1:
                        comment = COUNTER_SEER[self.index].format(target)
                        self.system_call["behavior"] = "SEER"
                elif self.role == "POSSESSED":
                    for info in seer_info:
                        actor = info["actor"]
                        if actor == self.index:
                            continue
                        self.seer_dict[actor] = info["report"]
                    if self.talk_count == 1 and len(self.seer_dict) < 2:
                        rnd = random.random()
                        if rnd < 0.5:
                            target_list = [idx for idx in range(1, 6) if idx != self.index]
                            target = random.choice(target_list)
                            result = "人狼"
                            comment = SEER_DECLARE[self.index].format(target, result)
                            self.system_call["behavior"] = "SEER"
                    elif self.talk_count == 2 and self.system_call["behavior"] != "SEER":
                        if len(self.seer_dict) == 0:
                            target_list = [idx for idx in range(1, 6) if idx != self.index]
                            target = random.choice(target_list)
                            result = "人狼"
                            comment = SEER_DECLARE[self.index].format(target, result)
                            self.system_call["behavior"] = "SEER"
                        elif len(self.seer_dict) == 1:
                            for k, v in self.seer_dict.items():
                                target = k
                                report = v
                            if report == "黒":
                                comment = COUNTER_SEER[self.index].format(target)
                                self.system_call["behavior"] = "SEER"
            # 投票先の分析
            p1.join()
            vote_dict: dict = q1.get()
            if vote_dict:
                self.vote_dict.update(vote_dict)
            # 投票先を宣言していない人々
            vote_undeclare: list = [agent for agent in self.alive if self.vote_dict.get(agent) is None]
            # 自分に投票すると宣言している人々
            snipers: list = [k for k, v in self.vote_dict.items() if v == self.index]
            # リプライ判定
            if towards_me and self.reply < 4:
                self.reply += 1
            else:
                # クローズ判定
                min_talk = 4 if self.day_count == 1 else 3
                is_ending = self.talk_count > min_talk + len(vote_undeclare)
                if is_ending:
                    self.is_close = True
                    if self.day_count == 2 and self.role == "POSSESSED":
                        comment = WEREWOLF_DEAD[self.index]
                    elif len(snipers) > (len(self.alive) // 2):
                        comment = DAY1_ENDING[self.index] if self.day_count == 1 else DAY2_ENDING[self.index]
                    else:
                        comment = DAY1_EVENING[self.index] if self.day_count == 1 else DAY2_EVENING[self.index]
                # メンション判定
                is_mention = self.day_count == 1 and self.talk_count == 4 and len(snipers) < 2
                if is_mention:
                    if self.index in vote_undeclare:
                        vote_undeclare.remove(self.index)
                    if vote_undeclare:
                        idx = int(random.choice(vote_undeclare))
                        comment = VOTE_INQUIRE[self.index].format(idx)
                        self.vote_dict[idx] = 6
        print(f"Agent[0{self.index}]: {comment}")
        return str(comment)

    def vote(self) -> str:
        target: list = [
            int(agent)
            for agent in self.gameInfo["statusMap"]
            if self.gameInfo["statusMap"][agent] == "ALIVE"
        ]
        target.remove(self.index)
        if self.vote_dict.get(self.index) in target:
            one = self.vote_dict.get(self.index)
        else:
            one = util.random_select(target)
        print(f"vote: {self.index} > {one}")
        data = {"agentIdx": one}

        return json.dumps(data, separators=(",", ":"))

    def divine(self) -> str:
        target = [
            int(agent)
            for agent in self.gameInfo["statusMap"]
            if self.gameInfo["statusMap"][agent] == "ALIVE"
        ]
        target.remove(self.index)
        if self.day_count == 0:
            self.divined = util.random_select(target)
            data = {"agentIdx": self.divined}
        elif self.day_count == 1:
            if self.divined in target:
                target.remove(self.divined)
            target_list: list[str] = []
            for agent in target:
                target_list.append(f"Agent[0{agent}]")
            self.system_call["target"] = ", ".join(target_list)
            self.system_call["request"] = "divine"
            result = self.model.multi_turn_chat_completion(
                self.system_call, self.all_history, []
            )
            print(f"divine: {self.index} > {result}")
            if result in target:
                data = {"agentIdx": result}
            else:
                data = {"agentIdx": util.random_select(target)}
        else:
            self.divined = util.random_select(target)
            data = {"agentIdx": self.divined}

        return json.dumps(data, separators=(",", ":"))

    def attack(self) -> str:
        target = [
            int(agent)
            for agent in self.gameInfo["statusMap"]
            if self.gameInfo["statusMap"][agent] == "ALIVE"
        ]
        target.remove(self.index)
        if self.day_count == 1:
            seer = [agent for agent, role in self.seer_dict.items() if agent in target and role == "seer"]
            if len(seer) == 2:
                vill = [agent for agent in target if agent not in seer]
                one = util.random_select(vill)
            elif len(seer) == 1:
                one = util.random_select(seer)
            else:
                one = util.random_select(target)
            print(f"attack: {self.index} > {one}")
            data = {"agentIdx": one}
        else:
            data = {"agentIdx": util.random_select(target)}

        return json.dumps(data, separators=(",", ":"))

    def whisper(self) -> None:
        pass

    def finish(self) -> str:
        self.gameContinue = False

    def action(self) -> str:
        if AIWolfCommand.is_initialize(request=self.request):
            self.initialize()
        elif AIWolfCommand.is_name(request=self.request):
            return self.get_name()
        elif AIWolfCommand.is_role(request=self.request):
            return self.get_role()
        elif AIWolfCommand.is_daily_initialize(request=self.request):
            self.daily_initialize()
        elif AIWolfCommand.is_daily_finish(request=self.request):
            self.daily_finish()
        elif AIWolfCommand.is_talk(request=self.request):
            return self.talk()
        elif AIWolfCommand.is_vote(request=self.request):
            return self.vote()
        elif AIWolfCommand.is_divine(request=self.request):
            return self.divine()
        elif AIWolfCommand.is_attack(request=self.request):
            return self.attack()
        elif AIWolfCommand.is_whisper(request=self.request):
            self.whisper()
        elif AIWolfCommand.is_finish(request=self.request):
            self.finish()
        return ""
