import os, re, sys, json, time, shlex, shutil, asyncio, argparse, threading, subprocess, requests
import nodriver as uc
from urllib.parse import urlparse, unquote
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
from datetime import datetime
from colorama import Fore, Style

if sys.platform == "win32":
    import winreg


class console:
    def __init__(self) -> None:
        self.colors = {
            "green": Fore.GREEN, "red": Fore.RED, "yellow": Fore.YELLOW, "blue": Fore.BLUE,
            "magenta": Fore.MAGENTA, "cyan": Fore.CYAN, "white": Fore.WHITE, "black": Fore.BLACK,
            "reset": Style.RESET_ALL, "lightblack": Fore.LIGHTBLACK_EX, "lightred": Fore.LIGHTRED_EX,
            "lightgreen": Fore.LIGHTGREEN_EX, "lightyellow": Fore.LIGHTYELLOW_EX,
            "lightblue": Fore.LIGHTBLUE_EX, "lightmagenta": Fore.LIGHTMAGENTA_EX,
            "lightcyan": Fore.LIGHTCYAN_EX, "lightwhite": Fore.LIGHTWHITE_EX,
        }

    def clear(self):
        os.system("cls" if os.name == "nt" else "clear")

    def timestamp(self):
        return datetime.now().strftime("%H:%M:%S")

    def success(self, message, obj):
        tqdm.write(f"{self.colors['lightblack']}{self.timestamp()} » {self.colors['lightgreen']}SUCC {self.colors['lightblack']}• {self.colors['white']}{message} : {self.colors['lightgreen']}{obj}{self.colors['white']} {self.colors['reset']}")

    def error(self, message, obj):
        tqdm.write(f"{self.colors['lightblack']}{self.timestamp()} » {self.colors['lightred']}ERRR {self.colors['lightblack']}• {self.colors['white']}{message} : {self.colors['lightred']}{obj}{self.colors['white']} {self.colors['reset']}")

    def warning(self, message, obj):
        tqdm.write(f"{self.colors['lightblack']}{self.timestamp()} » {self.colors['lightyellow']}WARN {self.colors['lightblack']}• {self.colors['white']}{message} : {self.colors['lightyellow']}{obj}{self.colors['white']} {self.colors['reset']}")

    def info(self, message, obj):
        tqdm.write(f"{self.colors['lightblack']}{self.timestamp()} » {self.colors['lightblue']}INFO {self.colors['lightblack']}• {self.colors['white']}{message} : {self.colors['lightblue']}{obj}{self.colors['white']} {self.colors['reset']}")

    def done(self, message, obj):
        tqdm.write(f"{self.colors['lightblack']}{self.timestamp()} » {self.colors['lightmagenta']}DONE {self.colors['lightblack']}• {self.colors['white']}{message} : {self.colors['lightmagenta']}{obj}{self.colors['white']} {self.colors['reset']}")

log = console()
log.clear()

CF_WAIT_SECS = 120
TURNSTILE_WAIT_SECS = 25
CLICK_WIDGET_AFTER_SECS = 7
TYPICAL_PART_SIZE = 524288000
PROFILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".temp_browser_profile")

# Downloading
CHUNK_SIZE = 64 * 1024
MIN_STEAL_SIZE = 256 * 1024
REQUEST_TIMEOUT = (15, 20)  # connect, and max seconds with no data before reconnecting
SEGMENT_RETRIES = 5
MIN_SEGMENT_SIZE = 8 * 1024 * 1024
DEFAULT_CONNECTIONS = 8
DEFAULT_JOBS = 3

# Set on Ctrl+C so every download thread saves its progress and returns.
STOP = threading.Event()
LINKS_LOCK = threading.Lock()

# Bytes received across every download, for the window title's total speed.
BYTES_LOCK = threading.Lock()
BYTES_RECEIVED = 0

def count_bytes(n):
    global BYTES_RECEIVED
    with BYTES_LOCK:
        BYTES_RECEIVED += n

def set_title(text):
    """Set the terminal window title."""
    if not sys.stdout.isatty():
        return
    try:
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.kernel32.SetConsoleTitleW(text)
        else:
            with tqdm.get_lock():
                sys.stdout.write(f"\033]0;{text}\007")
                sys.stdout.flush()
    except Exception:
        pass


def get_default_browser_windows():
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice"
        ) as key:
            prog_id, _ = winreg.QueryValueEx(key, "ProgId")

        command_paths = [
            rf"Software\Classes\{prog_id}\shell\open\command",
            rf"Software\Classes\{prog_id}\Application",
        ]

        for path in command_paths:
            try:
                with winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    path
                ) as key:
                    command, _ = winreg.QueryValueEx(key, "")
                    if command:
                        match = re.match(r'"([^"]+\.exe)"', command)

                        if match:
                            exe = match.group(1)
                            if os.path.isfile(exe):
                                return exe

                        match = re.match(r'(.+?\.exe)', command, re.IGNORECASE)
                        if match:
                            exe = match.group(1).strip('"')
                            if os.path.isfile(exe):
                                return exe

            except FileNotFoundError:
                pass

        for path in command_paths:
            try:
                with winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    path
                ) as key:
                    command, _ = winreg.QueryValueEx(key, "")

                    if command:
                        match = re.match(r'"([^"]+\.exe)"', command)

                        if match:
                            exe = match.group(1)
                            if os.path.isfile(exe):
                                return exe

            except FileNotFoundError:
                pass

    except Exception as e:
        log.warning("Could not detect default browser", str(e))

    return None

# nodriver drives the browser over the Chrome DevTools Protocol, so only
# Chromium-based browsers work (Firefox and friends do not).
CHROMIUM_BROWSER_HINTS = (
    "chrome", "chromium", "brave", "edge", "vivaldi", "opera", "thorium", "yandex",
)

def _linux_default_desktop_id():
    """Name of the default browser's .desktop file, e.g. 'brave-browser.desktop'."""
    for cmd in (
        ["xdg-settings", "get", "default-web-browser"],
        ["xdg-mime", "query", "default", "x-scheme-handler/https"],
        ["xdg-mime", "query", "default", "x-scheme-handler/http"],
    ):
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=5).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            continue
        if out.endswith(".desktop"):
            return out
    return None

def _linux_desktop_dirs():
    data_home = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    data_dirs = (os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":")
    return [os.path.join(d, "applications") for d in [data_home, *data_dirs] if d]

def _linux_desktop_exec(desktop_id):
    """Exec= line from the [Desktop Entry] group of a .desktop file."""
    for directory in _linux_desktop_dirs():
        path = os.path.join(directory, desktop_id)
        if not os.path.isfile(path):
            continue
        in_entry = False
        with open(path, "r", encoding="utf-8", errors="ignore") as file:
            for line in file:
                line = line.strip()
                if line.startswith("["):
                    in_entry = line == "[Desktop Entry]"
                elif in_entry and line.startswith("Exec="):
                    return line[len("Exec="):]
    return None

def get_default_browser_linux():
    try:
        desktop_id = _linux_default_desktop_id()
        if not desktop_id:
            log.warning("Could not detect default browser", "xdg-settings returned nothing")
            return None

        command = _linux_desktop_exec(desktop_id)
        if not command:
            log.warning("Could not read browser launcher", desktop_id)
            return None

        # Drop desktop field codes (%U, %f, ...) and any leading `env VAR=value`.
        args = [a for a in shlex.split(command) if not re.fullmatch(r"%[a-zA-Z]", a)]
        while args and (args[0] == "env" or "=" in args[0]):
            args.pop(0)
        if not args:
            return None

        if os.path.basename(args[0]) in ("flatpak", "snap"):
            log.warning("Default browser is sandboxed", f"{desktop_id} (flatpak/snap not supported)")
            return None

        exe = shutil.which(args[0])
        if not exe:
            return None

        name = os.path.basename(os.path.realpath(exe)).lower() + " " + os.path.basename(exe).lower()
        if not any(hint in name for hint in CHROMIUM_BROWSER_HINTS):
            log.warning("Default browser is not Chromium-based", exe)
            return None

        return exe

    except Exception as e:
        log.warning("Could not detect default browser", str(e))

    return None

def get_default_browser():
    if sys.platform == "win32":
        return get_default_browser_windows()
    if sys.platform.startswith("linux"):
        return get_default_browser_linux()
    return None

def resolve_output_path(downloads_folder, file_name):
    candidates = [
        os.path.join(downloads_folder, file_name),
        os.path.join(os.getcwd(), file_name),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return candidates[0]

def safe_file_name(name):
    """Strip characters Windows/exFAT/NTFS refuse in file names."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", unquote(name)).strip(" .")
    return name[:200]

def _name_from_disposition(header):
    match = re.search(r"filename\*\s*=\s*[^']*'[^']*'([^;]+)", header, re.IGNORECASE)
    if match:
        return match.group(1).strip().strip('"')
    match = re.search(r'filename\s*=\s*"([^"]+)"', header, re.IGNORECASE) \
        or re.search(r"filename\s*=\s*([^;]+)", header, re.IGNORECASE)
    return match.group(1).strip() if match else None

def probe_download(download_url):
    """Ask for one byte to learn the size, Range support and server-side file name."""
    with requests.get(download_url, headers={"Range": "bytes=0-0"}, stream=True, timeout=30) as r:
        r.raise_for_status()
        total, ranges = 0, False
        if r.status_code == 206:
            match = re.search(r"/(\d+)$", r.headers.get("Content-Range", ""))
            if match:
                total, ranges = int(match.group(1)), True
        else:
            total = int(r.headers.get("content-length", 0))

        name = _name_from_disposition(r.headers.get("Content-Disposition", ""))
        if not name:
            tail = os.path.basename(urlparse(r.url).path)
            name = tail if "." in tail else None
    return total, ranges, (safe_file_name(name) if name else None)

def progress_path(output_path):
    return output_path + ".progress"

def is_complete(output_path, total):
    return (
        os.path.isfile(output_path)
        and not os.path.exists(progress_path(output_path))
        and os.path.getsize(output_path) == total
    )

def short_name(name, width=32):
    """Keep the end of long names, where the part number is."""
    return name if len(name) <= width else "…" + name[-(width - 1):]

def make_bar(output_path, total, initial, position=0):
    return tqdm(
        position=position,
        leave=False,
        dynamic_ncols=True,
        total=total or None,
        initial=initial,
        unit="B",
        unit_scale=True,
        unit_divisor=1024,
        mininterval=0.5,
        desc=(
            f"{log.colors['lightblack']}{log.timestamp()} » {log.colors['lightblue']}INFO "
            f"{log.colors['lightblack']}• {log.colors['white']}Downloading -> "
            f"{short_name(os.path.basename(output_path))} {log.colors['reset']}"
        ),
    )

def download_single(download_url, output_path, position=0):
    """One connection; resumes from the existing file size when the server allows it."""
    existing_size = os.path.getsize(output_path) if os.path.isfile(output_path) else 0
    req_headers = {"Range": f"bytes={existing_size}-"} if existing_size else {}

    with requests.get(download_url, stream=True, headers=req_headers, timeout=REQUEST_TIMEOUT) as response:
        if response.status_code == 416:
            return True

        if response.status_code == 206:
            match = re.search(r"/(\d+)$", response.headers.get("Content-Range", ""))
            total_size = int(match.group(1)) if match else existing_size + int(response.headers.get("content-length", 0))
            mode, initial = "ab", existing_size
            log.info("Resuming download", f"{os.path.basename(output_path)} from {existing_size} bytes")
        elif response.status_code == 200:
            total_size = int(response.headers.get("content-length", 0))
            if existing_size:
                log.warning("Server ignored Range, re-downloading", os.path.basename(output_path))
            mode, initial = "wb", 0
        else:
            log.error("Failed to download file", response.status_code)
            return False

        with open(output_path, mode) as f, make_bar(output_path, total_size, initial, position) as bar:
            for data in response.iter_content(CHUNK_SIZE):
                if STOP.is_set():
                    return False
                f.write(data)
                bar.update(len(data))
                count_bytes(len(data))

    final_size = os.path.getsize(output_path)
    if total_size and final_size < total_size:
        log.error("Download incomplete", f"{final_size}/{total_size} bytes")
        return False
    return True

def _load_segments(output_path, total):
    try:
        with open(progress_path(output_path), "r", encoding="utf-8") as f:
            state = json.load(f)
        if state.get("total") == total:
            return state["segments"]
    except (OSError, ValueError, KeyError):
        pass
    return None

def _save_segments(output_path, total, segments):
    tmp = progress_path(output_path) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"total": total, "segments": segments}, f)
    os.replace(tmp, progress_path(output_path))

def _split(start, total, connections):
    remaining = total - start
    count = max(1, min(connections, remaining // MIN_SEGMENT_SIZE))
    step = remaining // count
    bounds = [start + i * step for i in range(count)] + [total]
    # [next byte to fetch, end (exclusive)]
    return [[bounds[i], bounds[i + 1]] for i in range(count)]

def download_segmented(download_url, output_path, total, connections, position=0):
    """Fetch byte ranges in parallel threads, writing each straight to its offset.

    Progress is kept in <file>.progress so an interrupted download resumes.
    """
    segments = _load_segments(output_path, total)
    if segments is None:
        # A plain partial file from an older run is a finished first segment.
        existing = os.path.getsize(output_path) if os.path.isfile(output_path) else 0
        start = existing if existing < total else 0
        segments = _split(start, total, connections)
        if start:
            log.info("Resuming download", f"{os.path.basename(output_path)} from {start} bytes")
    else:
        log.info("Resuming download", os.path.basename(output_path))

    with open(output_path, "ab"):
        pass
    if os.path.getsize(output_path) != total:
        with open(output_path, "r+b") as f:
            f.truncate(total)
    _save_segments(output_path, total, segments)

    done = total - sum(end - pos for pos, end in segments)
    # One lock guards the segment list, the shared file handle and the bar, so a
    # split never races a write: bytes past a segment's (possibly moved) end are dropped.
    lock = threading.Lock()
    failed = []
    stop = threading.Event()
    unowned = [seg for seg in segments if seg[0] < seg[1]]

    def next_segment():
        """Take an unclaimed range, else split the largest one still running."""
        with lock:
            if unowned:
                return unowned.pop(0)
            if stop.is_set() or STOP.is_set():
                return None
            biggest = max(segments, key=lambda s: s[1] - s[0])
            remaining = biggest[1] - biggest[0]
            if remaining < 2 * MIN_STEAL_SIZE:
                return None
            mid = biggest[0] + remaining // 2
            stolen = [mid, biggest[1]]
            biggest[1] = mid
            segments.append(stolen)
            return stolen

    def fetch(f, segment, bar):
        errors = 0
        while not (stop.is_set() or STOP.is_set()):
            with lock:
                if segment[0] >= segment[1]:
                    return
                headers = {"Range": f"bytes={segment[0]}-{segment[1] - 1}"}
            try:
                with requests.get(download_url, headers=headers, stream=True, timeout=REQUEST_TIMEOUT) as r:
                    if r.status_code != 206:
                        raise IOError(f"HTTP {r.status_code}")
                    for data in r.iter_content(CHUNK_SIZE):
                        if stop.is_set() or STOP.is_set():
                            return
                        with lock:
                            take = segment[1] - segment[0]
                            if take <= 0:
                                break
                            data = data[:take]
                            f.seek(segment[0])
                            f.write(data)
                            segment[0] += len(data)
                            bar.update(len(data))
                            count_bytes(len(data))
                            if segment[0] >= segment[1]:
                                break
                errors = 0
            except Exception as e:
                errors += 1
                if errors > SEGMENT_RETRIES:
                    failed.append(str(e))
                    stop.set()
                    return
                time.sleep(2 * errors)

    def worker(f, bar):
        while True:
            segment = next_segment()
            if segment is None:
                return
            fetch(f, segment, bar)

    def save():
        with lock:
            snapshot = [list(seg) for seg in segments]
        _save_segments(output_path, total, snapshot)

    with open(output_path, "r+b", buffering=0) as f, make_bar(output_path, total, done, position) as bar:
        threads = [
            threading.Thread(target=worker, args=(f, bar), daemon=True)
            for _ in range(max(1, min(connections, len(unowned))))
        ]
        for t in threads:
            t.start()
        try:
            last_save = time.monotonic()
            while any(t.is_alive() for t in threads) and not STOP.is_set():
                time.sleep(0.2)
                if time.monotonic() - last_save >= 1:
                    save()
                    last_save = time.monotonic()
        finally:
            # Writes and position updates happen together under the lock, so this
            # snapshot is exact even if a thread is still mid-request.
            stop.set()
            save()

    if any(pos < end for pos, end in segments):
        if STOP.is_set():
            log.warning("Paused, progress saved", os.path.basename(output_path))
        else:
            log.error("Download incomplete", failed[-1] if failed else "interrupted")
        return False

    os.remove(progress_path(output_path))
    return True

def download_file(download_url, output_path, total=0, ranges=False, connections=DEFAULT_CONNECTIONS, position=0):
    if total and is_complete(output_path, total):
        log.success("File already complete", os.path.basename(output_path))
        return True

    if ranges and total and connections > 1:
        ok = download_segmented(download_url, output_path, total, connections, position)
    else:
        ok = download_single(download_url, output_path, position)

    if ok:
        short = f"{output_path[:35]}...{output_path[55:]}" if len(output_path) > 55 else output_path
        log.success("Successfully downloaded file", short)
    return ok

def remove_link(processed_link, input_file="input.txt"):
    with LINKS_LOCK:
        _remove_link(processed_link, input_file)

def _remove_link(processed_link, input_file):
    with open(input_file, "r", encoding="utf-8") as file:
        links = file.readlines()
    with open(input_file, "w", encoding="utf-8") as file:
        for link in links:
            if link.strip() != processed_link:
                file.write(link)

def file_id_from_link(link):
    return urlparse(link).path.strip("/").split("/")[-1]

async def js(tab, expression, await_promise=False):
    """Evaluate JS that returns a JSON string, and decode it.

    nodriver hands back its internal RemoteObject whenever a result is falsy,
    which reads as truthy in Python, so every result is JSON encoded in the
    page and decoded here.
    """
    raw = await tab.evaluate(
        expression,
        await_promise=await_promise,
        return_by_value=True,
    )
    if not isinstance(raw, str):
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None

async def page_ready(tab):
    """True once Cloudflare interstitial is gone and download page loaded."""
    state = await js(
        tab,
        """(() => {
            const title = document.title || '';
            const body = (document.body && document.body.innerText) || '';
            const hasChallenge = title.includes('Just a moment')
                || body.includes('Verifying you are human')
                || !!document.querySelector('#challenge-running, #cf-challenge-running, .cf-browser-verification');
            const hasDownload = !!document.querySelector('a.link-button')
                || !!document.querySelector('#cf-turnstile')
                || !!document.querySelector('meta[name="title"]')
                || /DOWNLOAD/i.test(body);
            return JSON.stringify({ hasChallenge, hasDownload, title });
        })()""",
    )
    if not isinstance(state, dict):
        return False
    return bool(not state.get("hasChallenge") and state.get("hasDownload"))

async def wait_for_cf_clear(tab):
    log.info("Waiting for Cloudflare check", "solve/wait in the browser window if needed")
    last_err = None
    for i in range(CF_WAIT_SECS):
        try:
            if await page_ready(tab):
                log.success("Cloudflare cleared", f"after {i + 1}s")
                return True
        except Exception as e:
            last_err = e
        await asyncio.sleep(1)
        if i and i % 15 == 0:
            extra = f" ({last_err})" if last_err else ""
            log.info("Still waiting for download page", f"{i}s{extra}")
    return False

async def has_turnstile_widget(tab):
    """Trusted sessions get served the page without a captcha widget at all."""
    return await js(tab, "JSON.stringify(!!document.getElementById('cf-turnstile'))") is True

async def click_turnstile_widget(tab):
    """Nudge an interactive Turnstile checkbox that is waiting on a real click."""
    try:
        widget = await tab.select("#cf-turnstile", timeout=2)
        await widget.mouse_click()
        return True
    except Exception:
        return False

async def wait_for_turnstile(tab):
    """Wait for a fresh Turnstile token; it is single use per /go request."""
    log.info("Waiting for Turnstile token", "click checkbox if shown")
    clicked = False
    for i in range(TURNSTILE_WAIT_SECS):
        try:
            token = await js(
                tab,
                """JSON.stringify(
                    window.turnstileToken
                    || document.querySelector('[name="cf-turnstile-response"]')?.value
                    || ''
                )""",
            )
            if isinstance(token, str) and len(token) > 20:
                log.success("Turnstile ready", f"after {i + 1}s")
                return token
        except Exception:
            pass

        if not clicked and i == CLICK_WIDGET_AFTER_SECS:
            clicked = await click_turnstile_widget(tab)
            if clicked:
                log.info("Clicked Turnstile widget", "waiting for token")

        await asyncio.sleep(1)
    return None

async def post_go(tab, file_id, token):
    """Ask /go for the direct link from inside the cleared browser session."""
    return await js(
        tab,
        f"""
        (async () => {{
            const response = await fetch('/f/{file_id}/go', {{
                method: 'POST',
                headers: {{
                    'content-type': 'application/x-www-form-urlencoded',
                    'hx-request': 'true',
                    'hx-current-url': location.href,
                    'referer': location.href,
                }},
                body: new URLSearchParams({{ 'cf-turnstile-response': {json.dumps(token)} }}),
            }});
            const redirect = response.headers.get('HX-Redirect')
                || response.headers.get('hx-redirect');
            const body = await response.text();
            return JSON.stringify({{
                status: response.status,
                redirect: redirect,
                body: body.slice(0, 200),
            }});
        }})()
        """,
        await_promise=True,
    )

async def resolve_direct_url(tab, link, attempts=4):
    """Reloading the page each attempt gives Turnstile a fresh widget to solve."""
    file_id = file_id_from_link(link)
    last_error = "unknown error"

    for attempt in range(1, attempts + 1):
        await tab.get(link)

        if not await wait_for_cf_clear(tab):
            last_error = "Stuck on Cloudflare 'Just a moment' page"
        else:
            if await has_turnstile_widget(tab):
                token = await wait_for_turnstile(tab)
            else:
                log.info("No captcha widget on page", "session already trusted")
                token = ""

            if token is None:
                last_error = "Turnstile token not ready"
            else:
                result = await post_go(tab, file_id, token)
                if not isinstance(result, dict):
                    last_error = f"Unexpected browser response: {result!r}"
                elif result.get("redirect"):
                    return result["redirect"], None
                else:
                    last_error = f"No HX-Redirect ({result.get('body') or result.get('status')})"

        if attempt < attempts:
            log.warning("Retrying link", f"attempt {attempt + 1}/{attempts} — {last_error}")
            await asyncio.sleep(3)

    return None, last_error

async def shutdown_browser(browser):
    """Close browser and let its pipes drain before the event loop goes away."""
    try:
        browser.stop()
    except Exception:
        pass

    process = getattr(getattr(browser, "config", None), "browser_process", None)
    if process is not None:
        for _ in range(20):
            if process.poll() is not None:
                break
            await asyncio.sleep(0.1)
        else:
            try:
                process.kill()
            except Exception:
                pass

    # Give the transports a turn of the loop to close themselves.
    await asyncio.sleep(0.5)

def download_job(link, download_url, output_path, total, ranges, connections, position):
    """Runs in a worker thread; one per part being downloaded."""
    try:
        if download_file(download_url, output_path, total, ranges, connections, position):
            remove_link(link)
            return True
    except Exception as e:
        log.error("Failed to download file", f"{os.path.basename(output_path)}: {e}")
    return False

async def title_loop(stats, pending):
    """Keep the window title showing overall progress and speed."""
    last_bytes, last_time, speed = BYTES_RECEIVED, time.monotonic(), 0.0
    while True:
        await asyncio.sleep(1)
        now, received = time.monotonic(), BYTES_RECEIVED
        current = (received - last_bytes) / (now - last_time)
        speed = current if not speed else 0.7 * speed + 0.3 * current
        last_bytes, last_time = received, now
        set_title(
            f"FitGirl Downloader — {stats['game']} · {stats['done']}/{stats['total']} done"
            f" · {len(pending)} active · {tqdm.format_sizeof(speed, 'B/s', 1024)}"
        )

async def run(links, downloads_folder, connections=DEFAULT_CONNECTIONS, jobs=DEFAULT_JOBS):
    os.makedirs(PROFILE_DIR, exist_ok=True)
    log.info("Launching browser", "nodriver + persistent profile")

    browser_executable = get_default_browser()

    if browser_executable:
        log.info("Default browser detected", browser_executable)
    else:
        log.warning("Default browser not detected", "letting nodriver choose")

    browser = await uc.start(
        headless=False,
        user_data_dir=PROFILE_DIR,
        browser_executable_path=browser_executable,
        browser_args=[
            "--window-size=900,700",
            "--disable-popup-blocking",
        ],
    )
    browser_open = True

    tab = await browser.get("about:blank")

    loop = asyncio.get_running_loop()
    pool = ThreadPoolExecutor(max_workers=jobs)
    # Each slot is a download that may run at once, and the row its progress bar uses.
    slots = asyncio.Queue()
    for i in range(jobs):
        slots.put_nowait(i)
    pending = set()
    stats = {"game": os.path.basename(os.path.normpath(downloads_folder)), "done": 0, "total": len(links)}
    title_task = asyncio.create_task(title_loop(stats, pending))
    active_paths = set()

    def start_download(link, download_url, output_path, total, ranges, slot):
        future = loop.run_in_executor(
            pool, download_job, link, download_url, output_path, total, ranges, connections, slot,
        )
        pending.add(future)
        active_paths.add(output_path)

        def finished(fut):
            if not fut.cancelled() and fut.exception() is None and fut.result():
                stats["done"] += 1
            pending.discard(future)
            active_paths.discard(output_path)
            slots.put_nowait(slot)

        future.add_done_callback(finished)

    try:
        for link in links:
            fragment_name = safe_file_name(urlparse(link).fragment.strip())
            if fragment_name:
                output_path = resolve_output_path(downloads_folder, fragment_name)
                if (
                    os.path.isfile(output_path)
                    and not os.path.exists(progress_path(output_path))
                    and os.path.getsize(output_path) == TYPICAL_PART_SIZE
                ):
                    log.success("Skipping existing complete file", fragment_name)
                    remove_link(link)
                    stats["done"] += 1
                    continue

            # Only resolve once a download slot is free, so direct links don't sit
            # around (and possibly expire) waiting for their turn.
            slot = await slots.get()
            started = False
            try:
                log.info("Started processing", f"{link[:30]}...{link[60:]}" if len(link) > 60 else link)

                try:
                    download_url, err = await resolve_direct_url(tab, link)
                except Exception as e:
                    log.error("Browser resolve failed", str(e))
                    continue

                if not download_url:
                    log.error("Failed to get download url", err)
                    continue

                log.info("Fetched download url", f"{download_url[:70]}...")

                try:
                    total, ranges, server_name = await asyncio.to_thread(probe_download, download_url)
                except Exception as e:
                    log.warning("Could not probe download", str(e))
                    total, ranges, server_name = 0, False, None

                file_name = fragment_name or server_name or file_id_from_link(link)
                output_path = resolve_output_path(downloads_folder, file_name)

                if total and is_complete(output_path, total):
                    log.success("Skipping existing complete file", file_name)
                    remove_link(link)
                    stats["done"] += 1
                    continue

                if output_path in active_paths:
                    log.warning("Already downloading, skipping duplicate", file_name)
                    continue

                start_download(link, download_url, output_path, total, ranges, slot)
                started = True
            finally:
                if not started:
                    slots.put_nowait(slot)

        # Every link is resolved; the browser is no longer needed.
        browser_open = False
        await shutdown_browser(browser)

        if pending:
            log.info("All links resolved", f"waiting for {len(pending)} download(s)")
            await asyncio.wait(list(pending))
    except asyncio.CancelledError:
        if pending:
            log.warning("Stopping", f"saving progress of {len(pending)} download(s), please wait")
        raise
    finally:
        if pending:
            STOP.set()
            await asyncio.wait(list(pending))
        title_task.cancel()
        set_title(
            f"FitGirl Downloader — {stats['game']} · {stats['done']}/{stats['total']} done"
            + (" · paused" if STOP.is_set() else " · finished")
        )
        pool.shutdown(wait=True)
        if browser_open:
            await shutdown_browser(browser)

def silence_pipe_teardown_noise(unraisable):
    """Chrome's pipes are collected after the loop closes, which asyncio reports
    from __del__ as an unraisable error. Nothing actionable, so drop only those."""
    message = str(unraisable.exc_value)
    if isinstance(unraisable.exc_value, (ValueError, RuntimeError)) and (
        "closed pipe" in message or "Event loop is closed" in message
    ):
        return
    sys.__unraisablehook__(unraisable)

def main():
    sys.unraisablehook = silence_pipe_teardown_noise

    parser = argparse.ArgumentParser(description="Download FitGirl repack parts from input.txt")
    parser.add_argument(
        "-o", "--output",
        default="downloads",
        help="folder to save into, e.g. on an external drive (default: ./downloads). "
             "When links carry FitGirl file names, a <game-name> subfolder is created inside.",
    )
    parser.add_argument(
        "-c", "--connections",
        type=int,
        default=DEFAULT_CONNECTIONS,
        help=f"parallel connections per file (default: {DEFAULT_CONNECTIONS}, 1 = single stream)",
    )
    parser.add_argument(
        "-j", "--jobs",
        type=int,
        default=DEFAULT_JOBS,
        help=f"parts to download at the same time (default: {DEFAULT_JOBS})",
    )
    args = parser.parse_args()
    output_base = os.path.expanduser(args.output)

    if args.output != parser.get_default("output") and not os.path.isdir(output_base):
        log.error("Output folder not found (is the drive mounted?)", output_base)
        raise SystemExit(1)

    with open("input.txt", "r", encoding="utf-8") as file:
        links = [line.strip() for line in file if line.strip()]

    if not links:
        log.warning("input.txt is empty", "add links and re-run")
        raise SystemExit(1)

    first_game_link = next((l for l in links if "fitgirl-repacks.site" in urlparse(l).fragment), None)
    if not first_game_link:
        first_game_link = links[0]

    fragment = urlparse(first_game_link).fragment
    if "fitgirl-repacks.site" in fragment:
        downloads_folder = os.path.join(output_base, fragment.split("--")[0].strip("_"))
    else:
        downloads_folder = output_base
    os.makedirs(downloads_folder, exist_ok=True)
    log.info("Download folder", downloads_folder)
    log.info("Links to process", len(links))

    log.info("Concurrency", f"{max(1, args.jobs)} part(s) at once x {max(1, args.connections)} connection(s) each")

    try:
        asyncio.run(run(links, downloads_folder, max(1, args.connections), max(1, args.jobs)))
    except KeyboardInterrupt:
        log.warning("Stopped", "progress saved, run again to resume")
        raise SystemExit(130) from None
    log.done("Finished", downloads_folder)

if __name__ == "__main__":
    main()
