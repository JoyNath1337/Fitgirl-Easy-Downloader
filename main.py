import os
import re
import json
import time
import asyncio
import requests
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
TURNSTILE_WAIT_SECS = 90
TYPICAL_PART_SIZE = 524288000
PROFILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".ff_browser_profile")


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
    """Evaluate JS and always get a real Python value back from nodriver."""
    return await tab.evaluate(
        expression,
        await_promise=await_promise,
        return_by_value=True,
    )


async def page_ready(tab):
    """True once Cloudflare interstitial is gone and download page loaded."""
    raw = await js(
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
    if not raw:
        return False
    if isinstance(raw, dict):
        state = raw
    else:
        try:
            state = json.loads(raw)
        except Exception:
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


async def wait_for_turnstile(tab):
    log.info("Waiting for Turnstile token", "click checkbox if shown")
    for i in range(TURNSTILE_WAIT_SECS):
        try:
            token = await js(
                tab,
                """(() => {
                    return window.turnstileToken
                        || document.querySelector('[name="cf-turnstile-response"]')?.value
                        || '';
                })()""",
            )
            if isinstance(token, str) and len(token) > 20:
                log.success("Turnstile ready", f"after {i + 1}s")
                return token
            # Button may already be unlocked via previous success on this page
            cleared = await js(tab, "!!window.dlCleared")
            if cleared:
                log.info("dlCleared set", "trying without fresh token")
                return ""
        except Exception:
            pass
        await asyncio.sleep(1)
        if i and i % 15 == 0:
            log.info("Still waiting for Turnstile", f"{i}s")
    return None


async def resolve_direct_url(tab, link):
    file_id = file_id_from_link(link)
    await tab.get(link)

    if not await wait_for_cf_clear(tab):
        return None, "Stuck on Cloudflare 'Just a moment' page"

    token = await wait_for_turnstile(tab)
    if token is None:
        return None, "Turnstile token not ready"

    raw = await js(
        tab,
        f"""
        (async () => {{
            const token = window.turnstileToken
                || document.querySelector('[name="cf-turnstile-response"]')?.value
                || '';
            const response = await fetch('/f/{file_id}/go', {{
                method: 'POST',
                headers: {{
                    'content-type': 'application/x-www-form-urlencoded',
                    'hx-request': 'true',
                    'hx-current-url': location.href,
                    'referer': location.href,
                }},
                body: new URLSearchParams({{ 'cf-turnstile-response': token }}),
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

    if isinstance(raw, dict):
        result = raw
    else:
        try:
            result = json.loads(raw)
        except Exception:
            return None, f"Unexpected browser response: {raw!r}"

    if result.get("redirect"):
        return result["redirect"], None
    return None, f"No HX-Redirect ({result.get('body') or result.get('status')})"



async def run(links, downloads_folder):
    os.makedirs(PROFILE_DIR, exist_ok=True)
    log.info("Launching browser", "nodriver + persistent profile")

    browser = await uc.start(
        headless=False,
        user_data_dir=PROFILE_DIR,
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
        try:
            browser.stop()
        except Exception:
            pass


def main():
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
