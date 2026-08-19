import os, re, sys, json, asyncio, requests, winreg
import nodriver as uc
from urllib.parse import urlparse
from tqdm import tqdm
from datetime import datetime
from colorama import Fore, Style


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
        print(f"{self.colors['lightblack']}{self.timestamp()} » {self.colors['lightgreen']}SUCC {self.colors['lightblack']}• {self.colors['white']}{message} : {self.colors['lightgreen']}{obj}{self.colors['white']} {self.colors['reset']}")

    def error(self, message, obj):
        print(f"{self.colors['lightblack']}{self.timestamp()} » {self.colors['lightred']}ERRR {self.colors['lightblack']}• {self.colors['white']}{message} : {self.colors['lightred']}{obj}{self.colors['white']} {self.colors['reset']}")

    def warning(self, message, obj):
        print(f"{self.colors['lightblack']}{self.timestamp()} » {self.colors['lightyellow']}WARN {self.colors['lightblack']}• {self.colors['white']}{message} : {self.colors['lightyellow']}{obj}{self.colors['white']} {self.colors['reset']}")

    def info(self, message, obj):
        print(f"{self.colors['lightblack']}{self.timestamp()} » {self.colors['lightblue']}INFO {self.colors['lightblack']}• {self.colors['white']}{message} : {self.colors['lightblue']}{obj}{self.colors['white']} {self.colors['reset']}")

    def done(self, message, obj):
        print(f"{self.colors['lightblack']}{self.timestamp()} » {self.colors['lightmagenta']}DONE {self.colors['lightblack']}• {self.colors['white']}{message} : {self.colors['lightmagenta']}{obj}{self.colors['white']} {self.colors['reset']}")

log = console()
log.clear()

CF_WAIT_SECS = 120
TURNSTILE_WAIT_SECS = 25
CLICK_WIDGET_AFTER_SECS = 7
TYPICAL_PART_SIZE = 524288000
PROFILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".temp_browser_profile")

def get_default_browser():
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

def resolve_output_path(downloads_folder, file_name):
    candidates = [
        os.path.join(downloads_folder, file_name),
        os.path.join(os.getcwd(), file_name),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return candidates[0]

def download_file(download_url, output_path):
    existing_size = os.path.getsize(output_path) if os.path.isfile(output_path) else 0
    req_headers = {}
    if existing_size > 0:
        req_headers["Range"] = f"bytes={existing_size}-"

    response = requests.get(download_url, stream=True, headers=req_headers)
    block_size = 8192

    if response.status_code == 416:
        log.success("File already complete", os.path.basename(output_path))
        return True

    if response.status_code == 206:
        content_range = response.headers.get("Content-Range", "")
        match = re.search(r"/(\d+)$", content_range)
        total_size = int(match.group(1)) if match else existing_size + int(response.headers.get("content-length", 0))
        if existing_size >= total_size > 0:
            log.success("File already complete", os.path.basename(output_path))
            return True
        mode = "ab"
        initial = existing_size
        log.info("Resuming download", f"{os.path.basename(output_path)} from {existing_size} bytes")
    elif response.status_code == 200:
        total_size = int(response.headers.get("content-length", 0))
        if existing_size > 0 and total_size and existing_size >= total_size:
            log.success("File already complete", os.path.basename(output_path))
            return True
        if existing_size > 0:
            log.warning("Server ignored Range, re-downloading", os.path.basename(output_path))
        mode = "wb"
        initial = 0
    else:
        log.error("Failed to download file", response.status_code)
        return False

    with open(output_path, mode) as f, tqdm(
        total=total_size,
        initial=initial,
        unit="B",
        unit_scale=True,
        unit_divisor=1024,
    ) as bar:
        for data in response.iter_content(block_size):
            f.write(data)
            bar.set_description(
                f"{log.colors['lightblack']}{log.timestamp()} » {log.colors['lightblue']}INFO "
                f"{log.colors['lightblack']}• {log.colors['white']}Downloading -> "
                f"{os.path.basename(output_path)[:55]} {log.colors['reset']}"
            )
            bar.update(len(data))

    final_size = os.path.getsize(output_path)
    if total_size and final_size < total_size:
        log.error("Download incomplete", f"{final_size}/{total_size} bytes")
        return False

    short = f"{output_path[:35]}...{output_path[55:]}" if len(output_path) > 55 else output_path
    log.success("Successfully downloaded file", short)
    return True

def remove_link(processed_link, input_file="input.txt"):
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

async def run(links, downloads_folder):
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

    tab = await browser.get("about:blank")

    try:
        for link in links:
            log.info("Started processing", f"{link[:30]}...{link[60:]}" if len(link) > 60 else link)

            fragment_name = urlparse(link).fragment.strip()
            file_name = fragment_name or "default_file_name"
            output_path = resolve_output_path(downloads_folder, file_name)

            if os.path.isfile(output_path) and os.path.getsize(output_path) == TYPICAL_PART_SIZE:
                log.success("Skipping existing complete file", file_name)
                remove_link(link)
                continue

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
                if download_file(download_url, output_path):
                    remove_link(link)
            except Exception as e:
                log.error("Failed to download file", str(e))

            await asyncio.sleep(1)
    finally:
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
        game_name = fragment.split("--")[0].strip("_")
    else:
        game_name = "downloads"

    downloads_folder = os.path.join("downloads", game_name)
    os.makedirs(downloads_folder, exist_ok=True)
    log.info("Download folder", downloads_folder)
    log.info("Links to process", len(links))

    asyncio.run(run(links, downloads_folder))
    log.done("Finished", downloads_folder)

if __name__ == "__main__":
    main()
