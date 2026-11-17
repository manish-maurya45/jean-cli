"""Dynamic Context Assembly / injection: a small block appended just before we send.

It goes at the END of the message list so the stable prefix in front of it
stays cached.
"""

from utils import env_info


def reminder():
    """The block we append to the messages on every turn."""
    return {
        "role": "user",
        "content": env_info(),
    }