import os


class ProjectFileTools:
    """
    Sandbox file operations to a single project folder.
    No tool call can read, write, or delete anything outside `project_path`.
    """

    IGNORED_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv"}
    MAX_READ_CHARS = 20000

    def __init__(self, project_path: str):
        self.root = os.path.abspath(project_path)

    def _resolve(self, relative_path: str) -> str:
        relative_path = relative_path or "."
        target = os.path.abspath(os.path.join(self.root, relative_path))

        if target != self.root and not target.startswith(self.root + os.sep):
            raise PermissionError(
                f"'{relative_path}' resolves outside the project folder."
            )
        return target

    def list_files(self, relative_path: str = ".") -> str:
        target = self._resolve(relative_path)

        if not os.path.exists(target):
            return f"Path '{relative_path}' does not exist."
        if not os.path.isdir(target):
            return f"'{relative_path}' is a file, not a directory."

        entries = []
        for root, dirs, files in os.walk(target):
            dirs[:] = [d for d in dirs if d not in self.IGNORED_DIRS]
            for f in files:
                rel = os.path.relpath(os.path.join(root, f), self.root)
                entries.append(rel)

        entries.sort()
        return "\n".join(entries) if entries else "(no files)"

    def read_file(self, relative_path: str) -> str:
        target = self._resolve(relative_path)

        if not os.path.exists(target):
            return f"File '{relative_path}' does not exist."
        if not os.path.isfile(target):
            return f"'{relative_path}' is not a file."

        try:
            with open(target, "r", encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError:
            return f"'{relative_path}' is a binary file and cannot be read as text."

        if len(content) > self.MAX_READ_CHARS:
            return (
                content[: self.MAX_READ_CHARS]
                + f"\n\n... [truncated, file has {len(content)} characters total]"
            )
        return content

    def write_file(self, relative_path: str, content: str) -> str:
        target = self._resolve(relative_path)
        os.makedirs(os.path.dirname(target), exist_ok=True)

        with open(target, "w", encoding="utf-8") as f:
            f.write(content)

        return f"File '{relative_path}' written successfully ({len(content)} characters)."

    def delete_file(self, relative_path: str) -> str:
        target = self._resolve(relative_path)

        if not os.path.exists(target):
            return f"File '{relative_path}' does not exist."
        if os.path.isdir(target):
            return f"'{relative_path}' is a directory, refusing to delete it via delete_file."

        os.remove(target)
        return f"File '{relative_path}' deleted."

    def create_dir(self, relative_path: str) -> str:
        target = self._resolve(relative_path)
        os.makedirs(target, exist_ok=True)
        return f"Directory '{relative_path}' created."


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": (
                "List all files in the project folder (or a subfolder). "
                "Use this first to learn the project's structure before reading or editing files."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "relative_path": {
                        "type": "string",
                        "description": "Subfolder to list, relative to the project root. Use '.' for the whole project.",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the full text content of a file in the project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "relative_path": {
                        "type": "string",
                        "description": "Path to the file, relative to the project root.",
                    }
                },
                "required": ["relative_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Create a new file or overwrite an existing file with the given content. "
                "Always read_file first if the file already exists, so you don't accidentally lose code."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "relative_path": {
                        "type": "string",
                        "description": "Path to the file, relative to the project root.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Full content to write into the file.",
                    },
                },
                "required": ["relative_path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "Permanently delete a file from the project. Only use when explicitly asked.",
            "parameters": {
                "type": "object",
                "properties": {
                    "relative_path": {
                        "type": "string",
                        "description": "Path to the file to delete, relative to the project root.",
                    }
                },
                "required": ["relative_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_dir",
            "description": "Create a new directory (and any missing parent directories) inside the project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "relative_path": {
                        "type": "string",
                        "description": "Path of the directory to create, relative to the project root.",
                    }
                },
                "required": ["relative_path"],
            },
        },
    },
]
