# Fitgirl-Easy-Downloader

This Tool Helps To Download Multiple Files Easily From fitgirl-repacks.site Through fuckingfast.co

## Prerequisites

Ensure you have the following installed before running the script :

`Python 3.8+`

```bash
pip install -r requirements.txt
```

Google Chrome is required (used to pass Cloudflare / Turnstile checks).

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
4. The script will :
   - Open a Chrome window to clear Cloudflare / Turnstile (click the checkbox if asked).
   - Process each link in `input.txt`.
   - Skip files that are already fully downloaded.
   - Resume partial downloads when possible.
   - Extract and download files to the `downloads/<game-name>/` folder.
   - Remove processed links from `input.txt`.

## Disclaimer

This tool is created for educational purposes and ethical use only. Any misuse of this tool for malicious purposes is not condoned. The developers of this tool are not responsible for any illegal or unethical activities carried out using this tool.
