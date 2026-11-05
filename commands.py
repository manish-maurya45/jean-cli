from pathlib import Path

from prompt_toolkit.completion import Completer, Completion


SKILLS_DIR = [
    Path.cwd() / "skills",
    Path.home() / ".jean" / "skills",
]
BUILTINS = {
    "/exit": "Quit the session",
    "/clear": "Clear the screen and reset the conversation",
    "/help": "Show available commands",
}


def discover_skills(roots=SKILLS_DIR):
    """Return {'/name': 'description'} from each skills/<name>/SKILL.md."""
    skills = {}

    for root in roots:
        if not root.is_dir():
            continue

        for md in sorted(root.glob("*/SKILL.md")):
            desc = ""

            for line in md.read_text(encoding="utf-8").splitlines():
                if line.startswith("description:"):
                    desc = line.split(":", 1)[1].strip().strip("\"'")
                    break

            skills[f"/{md.parent.name}"] = desc

    return skills

def all_commands():
    return {**BUILTINS, **discover_skills()}


class SlashCompleter(Completer):
    """Completes only the command word, and only when the input starts with '/'."""

    def __init__(self):
        self.skills = discover_skills()          # re-scanned on every prompt
        self.items = {**BUILTINS, **self.skills}
        self.no_arg = set(BUILTINS)              # commands that run immediately

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if not text.startswith("/") or any(c.isspace() for c in text):
            return
        for name, desc in self.items.items():
            if name.startswith(text.lower()):
                meta = desc if len(desc) <= 60 else desc[:57] + "..."
                yield Completion(
                    name,
                    start_position=-len(text),
                    display_meta=meta,
                )