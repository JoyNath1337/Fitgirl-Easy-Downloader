import os, re, requests
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from tqdm import tqdm
from datetime import datetime
from colorama import Fore, Style


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

headers = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'accept-language': 'en-US,en;q=0.5',
    'referer': 'https://fitgirl-repacks.site/',
    'sec-ch-ua': '"Brave";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
}

def download_file(download_url, output_path):
    response = requests.get(download_url, stream=True)
    if response.status_code == 200:
        total_size = int(response.headers.get('content-length', 0))
        block_size = 8192

        with open(output_path, 'wb') as f, tqdm(
            total=total_size,
            unit='B',
            unit_scale=True,
            unit_divisor=1024,
        ) as bar:
            for data in response.iter_content(block_size):
                f.write(data)
                bar.set_description(f"{log.colors['lightblack']}{log.timestamp()} » {log.colors['lightblue']}INFO {log.colors['lightblack']}• {log.colors['white']}Downloading -> {os.path.basename(output_path)[:55]} {log.colors['reset']}")
                bar.update(len(data))

        log.success(f"Successfully Downloaded File", F"{output_path[:35]}...{output_path[55:]}")
    else:
        log.error(f"Failed To Download File", response.status_code)

def remove_link(processed_link, input_file=INPUT_FILE):
    with open(input_file, 'r') as file:
        lines = file.readlines()
    with open(input_file, 'w') as file:
        for line in lines:
            if line.strip() != processed_link:
                file.write(line)

# --- Read game name and links from input.txt ---
with open(INPUT_FILE, 'r') as file:
    all_lines = [line.strip() for line in file if line.strip()]

if not all_lines:
    log.warning("input.txt is empty", "run get_links.py first")
    raise SystemExit(1)

first_line = all_lines[0]
if first_line.lower().startswith("game name"):
    parts = first_line.split(":", 1)
    if len(parts) == 2 and parts[1].strip():
        game_name = parts[1].strip()
        links = all_lines[1:]
    else:
        log.error("Game name line is malformed", first_line)
        raise SystemExit(1)
else:
    log.error("No game name found in input.txt", "run get_links.py first")
    raise SystemExit(1)

if not links:
    log.warning("No links found in input.txt", "run get_links.py first")
    raise SystemExit(1)

log.info("Game", game_name)
downloads_folder = os.path.join("downloads", game_name)
os.makedirs(downloads_folder, exist_ok=True)
log.info("Download folder", downloads_folder)

for link in links:
    log.info(f"Started Processing", f"{link[:30]}...{link[60:]}")
    response = requests.get(link, headers=headers)

    if response.status_code != 200:
        log.error(f"Failed To Fetch Page", response.status_code)
        continue

    soup = BeautifulSoup(response.text, 'html.parser')
    meta_title = soup.find('meta', attrs={'name': 'title'})
    file_name = meta_title['content'] if meta_title else "default_file_name"
    script_tags = soup.find_all('script')
    download_function = None
    for script in script_tags:
        if 'function download' in script.text:
            download_function = script.text
            break

    if download_function:
        match = re.search(r'window\.open\(["\'](https?://[^\s"\'\)]+)', download_function)
        if match:
            download_url = match.group(1)
            log.info(f"Found Download Url", f"{download_url[:70]}...")
            output_path = os.path.join(downloads_folder, file_name)
            try:
                download_file(download_url, output_path)
                remove_link(link)
            except Exception as e:
                log.error(f"Failed To Download File", str(e))
        else:
            log.error("No Download Url Found", response.status_code)
    else:
        log.error("Download Function Not Found", response.status_code)