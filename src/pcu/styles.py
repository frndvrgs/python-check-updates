GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
BLUE = "\033[34m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"

UPDATE_STYLE: dict[str, tuple[str, str]] = {
    "major": (RED, "major update"),
    "minor": (YELLOW, "minor update"),
    "patch": (BLUE, "patch update"),
}
