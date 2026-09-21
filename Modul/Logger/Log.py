import colorama
from rich.console import Console
from rich.markdown import Markdown

colorama.init(convert=True)
console = Console()


class ConsoleLog():
    def log(self, msg, level="INFO"):
        levels = {
            "INFO": colorama.Fore.RED,
            "USER": colorama.Fore.MAGENTA,
            "AN78": colorama.Fore.GREEN,
            "SEARCH": colorama.Fore.YELLOW,
            "SYSTEM": colorama.Fore.YELLOW,
            "WHISPER": colorama.Fore.GREEN,
            "MEMORY": colorama.Fore.BLUE,
            "SETTINGS": colorama.Fore.BLUE,
            "ERROR": colorama.Fore.RED
        }

        if level == "AN78":
            print(f"{levels.get(level, colorama.Fore.WHITE)}[-| {level} |-]{colorama.Fore.RESET}")
            console.print(Markdown(msg))
        else:
            print(f"{levels.get(level, colorama.Fore.WHITE)}[-| {level} |-]{colorama.Fore.RESET} {msg}")