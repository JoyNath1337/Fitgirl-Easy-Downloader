# Fitgirl-Easy-Downloader

This Tool Helps To Download Multiple Files Easily From fitgirl-repacks.site Through fuckingfast.co


## Prerequisites

Ensure you have the following installed before running the script:

- `Python 3.13` (currently recommended; newer versions may not be supported yet)
- Required Python packages:

```bash
pip install -r requirements.txt
```

- A Chromium-based browser (Chrome, Chromium, Brave, Edge, Vivaldi, ...). Works on Windows and Linux.
  On Linux the default browser is detected via `xdg-settings`; if it isn't Chromium-based or is a
  Flatpak/Snap install, nodriver falls back to any Chrome/Chromium it finds on `PATH`.

## Usage

1. **Get Direct Download Links** : Run `get_links.py`, enter the Fitgirl game page URL, and all FuckingFast links will be copied to your clipboard automatically.
   ```bash
   python get_links.py
   ```
2. **Prepare Input Links** : Paste the copied links into `input.txt`, one per line.
3. **Run the Script** :
   ```bash
   python main.py
   ```
   Options:
   - `-o, --output PATH` : folder to save into (default `./downloads`), e.g. an external drive.
   - `-j, --jobs N` : parts to download at the same time (default 3).
   - `-c, --connections N` : connections per part (default 8, `1` = single stream).

   Press `Ctrl+C` to stop; progress is saved and the next run resumes.
4. The script will :
   - Open a Chrome window to clear Cloudflare / Turnstile (click the checkbox if asked).
   - Process each link in `input.txt`.
   - Skip files that are already fully downloaded.
   - Resume partial downloads when possible.
   - Extract and download files to the `downloads/<game-name>/` folder.
   - Remove processed links from `input.txt`.

## Disclaimer

This tool is created for educational purposes and ethical use only. Any misuse of this tool for malicious purposes is not condoned. The developers of this tool are not responsible for any illegal or unethical activities carried out using this tool.
