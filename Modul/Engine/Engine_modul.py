import colorama
import queue
import json

from Modul.Brain.Brain_modul import LLM
from Modul.Logger.Log import ConsoleLog

colorama.init(convert=True)
class An78:
    def __init__(self, project):
        with open("partials/config.json", "r") as f:
            self.config = json.load(f)

        self.llm = LLM()
        self.project = project
        self.project_path = project["path"]
        self.logger = ConsoleLog()
        self.q = queue.Queue()

        self.llm.set_project(self.project_path)

            
    def _load_config1(self):
        with open("partials/config.json", "r") as f:
            return json.load(f)
 
    def reload_config(self):
        self.config = self._load_config1()
        
    def _load_config2(self):
        with open("partials/config.json", "r") as f:
            self.config = json.load(f)
        return self.config

    # |||||||||| SHARED RESPONSE HANDLER |||||||||
    def _process_response(self, user_input: str) -> str:
        self.logger.log(user_input, "USER")
        self._load_config2()

        response_text = self.llm.agent_chat(user_input)

        try:
            conversation_log = {
                "messages": [
                    {"Dan": user_input.strip()},
                    {"An78": response_text.strip()}
                ]
            }
            with open("partials/logs.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(conversation_log, ensure_ascii=False) + "\n")
        except Exception as e:
            self.logger.log(f"Couldn't save finetune data: {e}", "ERROR")

        self.logger.log(response_text, "AN78")
        return response_text

    # |||||||||| CHAT LOOP |||||||||
    def chat_loop(self, user_input):
        #self.logger.log(user_input, "USER")
        return self._process_response(user_input)


    def callback(self, indata, frames, time_, status):
        self.q.put(bytes(indata))