import requests, os, pyperclip
from bs4 import BeautifulSoup
from datetime import datetime
from colorama import Fore, Style
from urllib.parse import urlparse

class console:
    def __init__(self) -> None:
        self.colors = {"green": Fore.GREEN, "red": Fore.RED, "yellow": Fore.YELLOW, "blue": Fore.BLUE, "magenta": Fore.MAGENTA, "cyan": Fore.CYAN, "white": Fore.WHITE, "black": Fore.BLACK, "reset": Style.RESET_ALL, "lightblack": Fore.LIGHTBLACK_EX, "lightred": Fore.LIGHTRED_EX, "lightgreen": Fore.LIGHTGREEN_EX, "lightyellow": Fore.LIGHTYELLOW_EX, "lightblue": Fore.LIGHTBLUE_EX, "lightmagenta": Fore.LIGHTMAGENTA_EX, "lightcyan": Fore.LIGHTCYAN_EX, "lightwhite": Fore.LIGHTWHITE_EX}
    def clear(self):
        os.system("cls" if os.name == "nt" else "clear")
    def timestamp(self):
        return datetime.now().strftime("%H:%M:%S")
    def success(self, message, obj):
        print(f"{self.colors['lightblack']}{self.timestamp()} » {self.colors['lightgreen']}SUCC {self.colors['lightblack']}• {self.colors['white']}{message} : {self.colors['lightgreen']}{obj}{self.colors['white']} {self.colors['reset']}")
    def error(self, message, obj):
        print(f"{self.colors['lightblack']}{self.timestamp()} » {self.colors['lightred']}ERRR {self.colors['lightblack']}• {self.colors['white']}{message} : {self.colors['lightred']}{obj}{self.colors['white']} {self.colors['reset']}")
    def done(self, message, obj):
        print(f"{self.colors['lightblack']}{self.timestamp()} » {self.colors['lightmagenta']}DONE {self.colors['lightblack']}• {self.colors['white']}{message} : {self.colors['lightmagenta']}{obj}{self.colors['white']} {self.colors['reset']}")
    def warning(self, message, obj):
        print(f"{self.colors['lightblack']}{self.timestamp()} » {self.colors['lightyellow']}WARN {self.colors['lightblack']}• {self.colors['white']}{message} : {self.colors['lightyellow']}{obj}{self.colors['white']} {self.colors['reset']}")
    def info(self, message, obj):
        print(f"{self.colors['lightblack']}{self.timestamp()} » {self.colors['lightblue']}INFO {self.colors['lightblack']}• {self.colors['white']}{message} : {self.colors['lightblue']}{obj}{self.colors['white']} {self.colors['reset']}")
    def custom(self, message, obj, color):
        print(f"{self.colors['lightblack']}{self.timestamp()} » {self.colors[color.upper()]}{color.upper()} {self.colors['lightblack']}• {self.colors['white']}{message} : {self.colors[color.upper()]}{obj}{self.colors['white']} {self.colors['reset']}")
    def input(self, message):
        return input(f"{self.colors['lightblack']}{self.timestamp()} » {self.colors['lightcyan']}INPUT   {self.colors['lightblack']}• {self.colors['white']}{message}{self.colors['reset']}")

log = console()
log.clear()

INPUT_FILE = 'input.txt'
game_name = None

if os.path.exists(INPUT_FILE):
    with open(INPUT_FILE, 'r') as f:
        first_line = f.readline().strip()
    if first_line.lower().startswith("game name"):
        parts = first_line.split(":", 1)
        if len(parts) == 2 and parts[1].strip():
            game_name = parts[1].strip()
            log.info("Game already in input.txt", game_name)
            choice = log.input("Keep existing game or replace? (k/r) : ").strip().lower()
            if choice != 'r':
                log.warning("Keeping existing game", game_name)
                raise SystemExit(0)
            else:
                log.warning("Replacing existing game", game_name)
                game_name = None

url = log.input("Enter Fitgirl Game Link : ")

try:
    r = requests.get(url)
    r.raise_for_status()
except requests.exceptions.RequestException as e:
    log.error("HTTP request failed", f"{url} ({e})")
    raise SystemExit(1)

soup = BeautifulSoup(r.text, "html.parser")

if not game_name:
    slug = urlparse(url).path.strip("/").split("/")[-1]
    game_name = slug.replace("-", " ").title()
    log.warning("No game name in input.txt, extracted from URL", game_name)

links = [
    a["href"]
    for dlinks_div in soup.find_all("div", class_="dlinks")
    for a in dlinks_div.find_all("a", href=True)
    if a["href"].startswith("https://fuckingfast.co/")
]

if not links:
    log.error("No Matching URLs Found", "Retry..")
else:
    output = "\n".join(links)
    print("🔗 Matching URLs :")
    print(output)
    pyperclip.copy(output)
    log.success("All Links Copied To Clipboard", len(links))

    with open(INPUT_FILE, 'w') as f:
        f.write(f"game name : {game_name}\n{output}\n")

    log.success("Links Written To input.txt", len(links))