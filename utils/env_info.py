import subprocess
from datetime import datetime


def git_branch():
    result = subprocess.run(
        "git branch --show-current", shell=True, capture_output=True, text=True
    )
    return result.stdout.strip() or "(detached)"


def env_info():
    """Return the <env> block (time + git branch) as a string."""
    return (
        "<env>\n"
        f"time: {datetime.now():%Y-%m-%d %H:%M}\n"
        f"git branch: {git_branch()}\n"
        "</env>"
    )