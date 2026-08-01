import os, re, requests, primp, json, threading, queue
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from tqdm import tqdm
from datetime import datetime
from colorama import Fore, Style
from concurrent.futures import ThreadPoolExecutor, as_completed

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

def load_settings(settings_file='settings.json'):
    default_settings = {"max_connections": 8}
    if os.path.exists(settings_file):
        try:
            with open(settings_file, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                return settings
        except Exception as e:
            log.warning("Could not parse settings.json, using defaults", str(e))
    else:
        log.warning("settings.json not found, using defaults", "")
    return default_settings

settings = load_settings()
max_connections = settings.get("max_connections", 8)
log.info("Max connections set to", max_connections)

headers = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'accept-language': 'en-US,en;q=0.5',
    'referer': 'https://fitgirl-repacks.site/',
    'sec-ch-ua': '"Brave";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
}

file_lock = threading.Lock()

def download_file(download_url, output_path, position=0):
    response = requests.get(download_url, stream=True)
    if response.status_code == 200:
        total_size = int(response.headers.get('content-length', 0))
        block_size = 8192

        with open(output_path, 'wb') as f, tqdm(
            total=total_size,
            unit='B',
            unit_scale=True,
            unit_divisor=1024,
            position=position,
            leave=False
        ) as bar:
            for data in response.iter_content(block_size):
                f.write(data)
                bar.set_description(f"{log.colors['lightblack']}{log.timestamp()} » {log.colors['lightblue']}INFO {log.colors['lightblack']}• {log.colors['white']}Downloading -> {os.path.basename(output_path)[:55]} {log.colors['reset']}")
                bar.update(len(data))

        log.success("Successfully downloaded file", f"{output_path[:35]}...{output_path[55:]}" if len(output_path) > 55 else output_path)
    else:
        log.error("Failed to download file", response.status_code)

def remove_link(processed_link, input_file='input.txt'):
    with file_lock:
        with open(input_file, 'r', encoding='utf-8') as file:
            links = file.readlines()
            
        with open(input_file, 'w', encoding='utf-8') as file:
            for link in links:
                if link.strip() != processed_link:
                    file.write(link)

def process_link(link, downloads_folder, slot_queue):
    slot = slot_queue.get()
    try:
        log.info("Started processing", f"{link[:30]}...{link[60:]}" if len(link) > 60 else link)
        response = primp.get(link, headers=headers)

        if response.status_code != 200:
            log.error("Failed to fetch page", response.status_code)
            return

        soup = BeautifulSoup(response.text, 'html.parser')
        meta_title = soup.find('meta', attrs={'name': 'title'})
        file_name = meta_title['content'] if meta_title else "default_file_name"

        download_btn = soup.find('a', class_='link-button')
        if not download_btn:
            log.error("Download button not found", response.status_code)
            return

        go_path = download_btn.get('hx-post')
        if not go_path:
            log.error("hx-post attribute not found", response.status_code)
            return

        go_url = urljoin(response.url, go_path)

        post_headers = {
            'accept': '*/*',
            'content-type': 'application/x-www-form-urlencoded',
            'hx-request': 'true',
            'hx-current-url': response.url,
            'origin': 'https://fuckingfast.co',
            'referer': response.url,
            'user-agent': headers['user-agent'],
        }

        go_response = primp.post(go_url, headers=post_headers)

        download_url = (
            go_response.headers.get('HX-Redirect')
            or go_response.headers.get('hx-redirect')
        )

        if not download_url:
            log.error("HX-Redirect header missing", go_response.headers)
            return

        log.info("Fetched download url", f"{download_url[:70]}...")

        output_path = os.path.join(downloads_folder, file_name)

        try:
            download_file(download_url, output_path, position=slot)
            remove_link(link)
        except Exception as e:
            log.error("Failed to download file", str(e))
    finally:
        slot_queue.put(slot)

with open('input.txt', 'r', encoding='utf-8') as file:
    links = [line.strip() for line in file if line.strip()]

if not links:
    log.warning("input.txt is empty", "add links and re-run")
    raise SystemExit(1)

first_game_link = next((l for l in links if "fitgirl-repacks.site" in urlparse(l).fragment), None)
if not first_game_link:
    log.error("Could not determine game name", "no fitgirl part files found in input.txt")
    raise SystemExit(1)
game_name = urlparse(first_game_link).fragment.split("--")[0].strip("_")
downloads_folder = os.path.join("downloads", game_name)
os.makedirs(downloads_folder, exist_ok=True)
log.info("Download folder", downloads_folder)

slot_queue = queue.Queue()
for i in range(max_connections):
    slot_queue.put(i)

with ThreadPoolExecutor(max_workers=max_connections) as executor:
    futures = [executor.submit(process_link, link, downloads_folder, slot_queue) for link in links]
    for future in as_completed(futures):
        try:
            future.result()
        except Exception as e:
            log.error("Task failed with error", str(e))

log.done("All downloads finished", "")
