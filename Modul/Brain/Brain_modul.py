import json
import os
import socket
from urllib import error as urlerror
from urllib import request as urlrequest

from Modul.Logger.Log import ConsoleLog
from Modul.Tools.file_tools import ProjectFileTools, TOOL_SCHEMAS


class LLMHTTPError(Exception):
    def __init__(self, status, body):
        self.status = status
        self.body = body
        super().__init__(f"HTTP {status}: {body}")


class LLM:
    """Chat client supporting local Ollama and OpenRouter."""

    _instance = None
    CONFIG_PATH = "partials/config.json"
    OLLAMA_MODEL = "qwen3:14b"
    OPENROUTER_MODEL = "openrouter/free"
    DESTRUCTIVE_TOOLS = {"write_file", "delete_file"}
    DEFAULT_MAX_CONTINUATIONS = 3
    DEFAULT_HISTORY_MAX_CHARS = 24000
    CONFIRM_ANSWERS = {"y", "yes", "a", "ano", "áno"}

    # ASCII variants avoid terminal encoding differences in interactive prompts.
    CONFIRM_ANSWERS = {"y", "yes", "a", "ano"}

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self.logger = ConsoleLog()
        self.history, self.simple_history = [], []
        self.project_path = self.tools_handler = None
        self._load_provider_config()
        self._initialized = True

    def _read_config(self):
        try:
            with open(self.CONFIG_PATH, "r", encoding="utf-8") as file:
                return json.load(file)
        except (OSError, json.JSONDecodeError):
            return {}

    def _load_provider_config(self):
        """Reload on every request so Settings changes apply immediately."""
        config = self._read_config()
        self.provider = config.get("llm_provider", "ollama").lower()
        if self.provider == "openrouter":
            self.url = "https://openrouter.ai/api/v1/chat/completions"
            self.model = config.get("openrouter_model", self.OPENROUTER_MODEL)
            self.api_key = os.environ.get(
                "OPENROUTER_API_KEY", config.get("openrouter_api_key", "")
            ).strip()
            self.headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "X-OpenRouter-Title": "An78",
            }
        else:
            self.provider = "ollama"
            host = config.get("llm_host", "localhost")
            self.url = f"http://{host}:11434/api/chat"
            self.model = config.get("llm_model", self.OLLAMA_MODEL)
            self.api_key = ""
            self.headers = {"Content-Type": "application/json"}

    def set_project(self, project_path):
        if project_path != self.project_path:
            self.history = []
        self.project_path = project_path
        self.tools_handler = ProjectFileTools(project_path)
        self.logger.log(f"Project set to: {project_path}", "SYSTEM")

    def get_system_instructions(self):
        project_info = (f"Current project folder: {self.project_path}"
                        if self.project_path else "No project is currently open.")
        return f"""You are An78, an expert coding agent running on Dan's computer.

{project_info}

Help Dan write, debug, explain, refactor and maintain code in the current project.
You can use list_files, read_file, write_file, delete_file and create_dir. These tools only work inside the project folder.
- Use list_files before inspecting an unfamiliar project.
- Read an existing file before overwriting it.
- When asked to change code, call write_file; do not only print code.
- Use delete_file only when explicitly asked.
- Do not claim a change succeeded until the tool result confirms it.
- Do not ask for a textual confirmation: the application handles write/delete confirmation.
- If a tool result says the user declined, do not repeat that call.

Be direct and concise. Use Markdown and fenced code blocks. Preserve existing functionality unless asked otherwise and briefly explain successful changes."""

    def _call_llm(self, messages, use_tools):
        self._load_provider_config()
        if self.provider == "openrouter":
            if not self.api_key:
                raise ValueError("OpenRouter API key is missing. Set OPENROUTER_API_KEY or add it in Settings.")
            payload = {"model": self.model, "messages": messages, "stream": False,
                       "temperature": 0.3, "top_p": 0.8}
        else:
            payload = {"model": self.model, "messages": messages, "stream": False,
                       "keep_alive": -1,
                       "options": {"temperature": 0.3, "num_ctx": 8192,
                                   "repeat_penalty": 1.1, "top_p": 0.8}}
        if use_tools:
            payload["tools"] = TOOL_SCHEMAS
        body = json.dumps(payload).encode("utf-8")
        request = urlrequest.Request(self.url, data=body, headers=self.headers, method="POST")
        try:
            with urlrequest.urlopen(request, timeout=180) as response:
                return json.loads(response.read().decode("utf-8"))
        except urlerror.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")[:500]
            raise LLMHTTPError(error.code, detail) from error

    def _assistant_message(self, data):
        if self.provider == "openrouter":
            choices = data.get("choices", [])
            if not choices:
                raise ValueError("OpenRouter returned no completion choices.")
            return choices[0].get("message") or {}
        return data.get("message", {}) or {}

    def _finish_reason(self, data):
        """Return the provider's reason for ending a response, when available."""
        if self.provider == "openrouter":
            choices = data.get("choices", [])
            return str(choices[0].get("finish_reason", "")).lower() if choices else ""
        return str(data.get("done_reason", "")).lower()

    def _response_was_truncated(self, data):
        # OpenAI-compatible APIs use ``length``. Ollama normally uses the same
        # value, but accepting the other common spellings keeps this portable.
        return self._finish_reason(data) in {"length", "max_tokens", "token_limit"}

    def _max_continuations(self):
        value = self._read_config().get("max_continuations", self.DEFAULT_MAX_CONTINUATIONS)
        try:
            return max(0, min(int(value), 10))
        except (TypeError, ValueError):
            return self.DEFAULT_MAX_CONTINUATIONS

    def _recent_history(self, history):
        """Keep recent complete turns within a bounded input-context budget."""
        limit = self._read_config().get("history_max_chars", self.DEFAULT_HISTORY_MAX_CHARS)
        try:
            limit = max(0, int(limit))
        except (TypeError, ValueError):
            limit = self.DEFAULT_HISTORY_MAX_CHARS

        selected, used = [], 0
        # History is stored as user/assistant pairs. Do not retain half a turn.
        for index in range(len(history) - 2, -1, -2):
            turn = history[index:index + 2]
            turn_size = sum(len(str(text)) for _, text in turn)
            if selected and used + turn_size > limit:
                break
            if not selected and turn_size > limit:
                # A single fresh turn is still more useful than no context.
                selected[0:0] = turn
                break
            selected[0:0] = turn
            used += turn_size
        return selected

    @staticmethod
    def _continuation_prompt():
        return (
            "Your previous answer was cut off by the provider's output-token limit. "
            "Continue exactly where it ended. Do not repeat completed text; finish "
            "the original task."
        )

    def _execute_tool(self, name, args):
        if self.tools_handler is None:
            return "No project is currently open."
        try:
            if name == "list_files": return self.tools_handler.list_files(args.get("relative_path", "."))
            if name == "read_file": return self.tools_handler.read_file(args["relative_path"])
            if name == "write_file": return self.tools_handler.write_file(args["relative_path"], args.get("content", ""))
            if name == "delete_file": return self.tools_handler.delete_file(args["relative_path"])
            if name == "create_dir": return self.tools_handler.create_dir(args["relative_path"])
            return f"Unknown tool: {name}"
        except Exception as error:
            return f"Tool error: {error}"

    def _requires_confirmation(self):
        return self._read_config().get("confirm_file_changes", True)

    def _confirm_action(self, name, args):
        if name == "write_file":
            preview = args.get("content", "")
            preview = preview[:200] + ("..." if len(preview) > 200 else "")
            print(f"\n[CONFIRM] AI wants to write '{args.get('relative_path')}':\n---\n{preview}\n---")
        else:
            print(f"\n[CONFIRM] AI wants to delete '{args.get('relative_path')}'.")
        return input("Confirm? (y/n): ").strip().lower() in self.CONFIRM_ANSWERS

    @staticmethod
    def _parse_tool_arguments(raw_args):
        if isinstance(raw_args, dict):
            return raw_args
        if isinstance(raw_args, str):
            try:
                return json.loads(raw_args)
            except json.JSONDecodeError:
                pass
        return {}

    def _tool_result_message(self, call, result):
        message = {"role": "tool", "content": str(result)}
        # OpenRouter/OpenAI requires the corresponding assistant tool-call ID.
        if self.provider == "openrouter" and call.get("id"):
            message["tool_call_id"] = call["id"]
        return message

    def _request_error(self, error):
        if isinstance(error, ValueError):
            detail = str(error)
        elif isinstance(error, urlerror.URLError):
            detail = "LLM server is unreachable."
        elif isinstance(error, socket.timeout):
            detail = "LLM request timed out. Try again."
        elif isinstance(error, LLMHTTPError):
            detail = f"LLM returned HTTP {error.status}: {error.body}"
        else:
            detail = f"LLM response error: {error}"
        self.logger.log(detail, "ERROR")
        return detail

    def agent_chat(self, user_input, max_steps=30):
        messages = [{"role": "system", "content": self.get_system_instructions()}]
        messages.extend({"role": role, "content": text} for role, text in self._recent_history(self.history))
        messages.append({"role": "user", "content": user_input})
        final_text = ""
        final_parts = []
        continuations = 0

        for _ in range(max_steps):
            try:
                data = self._call_llm(messages, self.tools_handler is not None)
                message = self._assistant_message(data)
            except Exception as error:
                return self._request_error(error)
            tool_calls = message.get("tool_calls") or []
            if not tool_calls:
                part = (message.get("content") or "").strip()
                if part:
                    final_parts.append(part)
                if self._response_was_truncated(data) and continuations < self._max_continuations():
                    continuations += 1
                    self.logger.log(
                        f"Response reached token limit; continuing ({continuations}/{self._max_continuations()}).",
                        "SYSTEM",
                    )
                    messages.append(message)
                    messages.append({"role": "user", "content": self._continuation_prompt()})
                    continue
                final_text = "\n\n".join(final_parts)
                if self._response_was_truncated(data):
                    final_text += "\n\n[The response is still incomplete after the automatic continuation limit.]"
                break
            messages.append(message)
            for call in tool_calls:
                function = call.get("function", {}) or {}
                name = function.get("name")
                args = self._parse_tool_arguments(function.get("arguments", {}))
                self.logger.log(f"Tool call: {name}({args})", "SYSTEM")
                if name in self.DESTRUCTIVE_TOOLS and self._requires_confirmation() and not self._confirm_action(name, args):
                    result = "User declined this action. Do not repeat it; ask what to do instead."
                else:
                    result = self._execute_tool(name, args)
                self.logger.log(f"Tool result: {str(result)[:300]}", "SYSTEM")
                messages.append(self._tool_result_message(call, result))
        else:
            final_text = "\n\n".join(final_parts)
            suffix = "Reached the maximum number of tool steps without a final answer."
            final_text = f"{final_text}\n\n{suffix}" if final_text else suffix
        if final_text:
            self.history.extend((("user", user_input), ("assistant", final_text)))
        return final_text

    def get_simple_chat_instructions(self):
        return """You are An78, a helpful general-purpose AI assistant. This is a quick chat, not tied to a project. Answer directly, be clear and concise, use Markdown, and put code in correctly tagged fenced code blocks."""

    def simple_chat(self, user_input):
        messages = [{"role": "system", "content": self.get_simple_chat_instructions()}]
        messages.extend({"role": role, "content": text} for role, text in self._recent_history(self.simple_history))
        messages.append({"role": "user", "content": user_input})
        final_parts = []
        for continuation in range(self._max_continuations() + 1):
            try:
                data = self._call_llm(messages, False)
                message = self._assistant_message(data)
            except Exception as error:
                return self._request_error(error)
            part = (message.get("content") or "").strip()
            if part:
                final_parts.append(part)
            if not self._response_was_truncated(data):
                break
            if continuation == self._max_continuations():
                final_parts.append("[The response is still incomplete after the automatic continuation limit.]")
                break
            self.logger.log(
                f"Response reached token limit; continuing ({continuation + 1}/{self._max_continuations()}).",
                "SYSTEM",
            )
            messages.append(message)
            messages.append({"role": "user", "content": self._continuation_prompt()})
        final_text = "\n\n".join(final_parts)
        if final_text:
            self.simple_history.extend((("user", user_input), ("assistant", final_text)))
        return final_text
