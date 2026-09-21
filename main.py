import os
import json
import getpass

import Modul.Engine.Engine_modul as Engine_modul
import Modul.Brain.Brain_modul as Brain_modul
import Modul.Logger.Log as Logger_modul
from InquirerPy import inquirer

PROJECTS_DIR = "projects"

logger = Logger_modul.ConsoleLog()

def ensure_projects_dir():
    os.makedirs(PROJECTS_DIR, exist_ok=True)


def get_projects():
    ensure_projects_dir()

    projects = []

    for folder in os.listdir(PROJECTS_DIR):
        project_file = os.path.join(
            PROJECTS_DIR,
            folder,
            "project.json"
        )

        if os.path.exists(project_file):
            try:
                with open(project_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    projects.append(data)
            except Exception:
                pass

    return projects


def create_project():
    print("\n=== Create Project ===\n")

    name = input("Project name: ").strip()

    if not name:
        print("Invalid project name.")
        return None

    path = input("Project path: ").strip()

    if not os.path.exists(path):
        print("Path does not exist.")
        return None

    project = {
        "name": name,
        "path": path,
        "language": "Unknown"
    }

    project_dir = os.path.join(PROJECTS_DIR, name)

    os.makedirs(project_dir, exist_ok=True)

    with open(
        os.path.join(project_dir, "project.json"),
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(project, f, indent=4)

    print(f"Project '{name}' created.")

    return project


def select_project():
    projects = get_projects()

    if not projects:
        print("No projects found.")
        return None

    choices = [p["name"] for p in projects]

    selected = inquirer.select(
        message="Select project:",
        choices=choices
    ).execute()

    return next(
        p for p in projects
        if p["name"] == selected
    )


def project_chat(project):
    print(f"\nOpened project: {project['name']}")
    print(f"Path: {project['path']}\n")

    an78 = Engine_modul.An78(project)

    while True:
        user_input = input("You > ").strip()

        if user_input.lower() in [
            "exit",
            "quit",
            "back"
        ]:
            break

        if user_input:
            an78.chat_loop(user_input)

def project_files(project):
    print("\n=== Project Files ===\n")

    ignored = {"venv", ".git", "__pycache__", ".idea"}

    for root, dirs, files in os.walk(project["path"]):
        dirs[:] = [d for d in dirs if d not in ignored]

        for file in files:
            print(
                os.path.relpath(
                    os.path.join(root, file),
                    project["path"]
                )
            )

    print()

def quick_chat():
    print("\n=== Quick Chat (bez projektu) ===\n")

    llm = Brain_modul.LLM()

    while True:
        user_input = input("You > ").strip()

        if user_input.lower() in ["exit", "quit", "back"]:
            break

        if user_input:
            response = llm.simple_chat(user_input)
            print()
            logger.log(response, "AN78")
            print()

def settings_menu():
    """Configure application behavior stored in partials/config.json."""
    while True:
        try:
            with open("partials/config.json", "r", encoding="utf-8") as f:
                config = json.load(f)
        except (OSError, json.JSONDecodeError):
            config = {}

        confirmations_enabled = config.get("confirm_file_changes", True)
        state = "ON" if confirmations_enabled else "OFF"
        provider = config.get("llm_provider", "ollama")
        provider_label = "OpenRouter" if provider == "openrouter" else "Local Ollama"
        api_key_set = bool(os.environ.get("OPENROUTER_API_KEY") or config.get("openrouter_api_key"))
        choice = inquirer.select(
            message="Settings",
            choices=[
                f"LLM provider: {provider_label}",
                f"OpenRouter API key: {'set' if api_key_set else 'not set'}",
                f"Confirm file changes: {state}",
                "Back",
            ],
        ).execute()

        if choice == "Back":
            return

        if choice.startswith("LLM provider:"):
            if provider == "openrouter":
                config["llm_provider"] = "ollama"
                config.setdefault("llm_model", "qwen3:14b")
                print("LLM provider set to local Ollama.")
            else:
                config["llm_provider"] = "openrouter"
                config["openrouter_model"] = "openrouter/free"
                print("LLM provider set to OpenRouter")
        elif choice.startswith("OpenRouter API key:"):
            key = getpass.getpass("OpenRouter API key (leave blank to keep current): ").strip()
            if key:
                config["openrouter_api_key"] = key
                print("OpenRouter API key saved. OPENROUTER_API_KEY takes precedence when set.")
            else:
                print("OpenRouter API key unchanged.")
        else:
            config["confirm_file_changes"] = not confirmations_enabled
            print("File-change confirmation is now " + ("enabled." if config["confirm_file_changes"] else "disabled."))
        with open("partials/config.json", "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
            f.write("\n")


if __name__ == "__main__":

    print(r"""
██╗  ██╗ ██╗     ██████╗ ███████╗    ██████╗ ███████╗    ██████╗  █████╗ 
██║  ██║███║    ██╔════╝ ██╔════╝    ╚════██╗╚════██║    ╚════██╗██╔══██╗
███████║╚██║    ███████╗ █████╗       █████╔╝    ██╔╝     █████╔╝╚█████╔╝
╚════██║ ██║    ██╔═══██╗██╔══╝       ╚═══██╗   ██╔╝      ╚═══██╗██╔══██╗
     ██║ ██║    ╚██████╔╝███████╗    ██████╔╝   ██║      ██████╔╝╚█████╔╝
     ╚═╝ ╚═╝     ╚═════╝ ╚══════╝    ╚═════╝    ╚═╝      ╚═════╝  ╚════╝ 
""")

    current_project = None

    while True:

        menu = [
            "Quick Chat",
            "Open Project",
            "Create Project",
            "Settings",
            "Exit"
        ]

        if current_project:
            menu.insert(
                1,
                f"Continue ({current_project['name']})"
            )

        choice = inquirer.select(
            message="Main Menu",
            choices=menu
        ).execute()

        if choice == "Open Project":
            current_project = select_project()
        elif choice == "Quick Chat":
            quick_chat()

        elif choice.startswith("Continue"):
            while True:

                sub_choice = inquirer.select(
                    message=f"Project: {current_project['name']}",
                    choices=[
                        "Chat",
                        "Project Files",
                        "Change Project",
                        "Back"
                    ]
                ).execute()

                if sub_choice == "Chat":
                    project_chat(current_project)

                elif sub_choice == "Project Files":
                    project_files(current_project)

                elif sub_choice == "Change Project":
                    current_project = select_project()
                    break

                elif sub_choice == "Back":
                    break

        elif choice == "Create Project":
            project = create_project()

            if project:
                current_project = project

        elif choice == "Settings":
            settings_menu()

        elif choice == "Exit":
            break
