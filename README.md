# Fitgirl-Easy-Downloader
This Tool Helps To Download Multiple Files Easily From fitgirl-repacks.site Through fuckingfast.co

## Prerequisites
Ensure you have the following installed before running the script :
`Python 3.8+`
```bash
pip install -r requirements.txt
```

## Usage
1. **Get Direct Download Links** : Run `get_links.py` and enter the Fitgirl game page URL.
```bash
python get_links.py
```
   The script will :
   - Automatically extract the game name from the URL.
   - Scrape all FuckingFast download links from the page.
   - Copy the links to your clipboard.
   - Write everything to `input.txt` automatically (game name on line 1, links below).

   > If `input.txt` already contains a game, you will be asked whether to **keep** it (`k`) or **replace** it (`r`) with the new one.

2. **Run the Downloader** :
```bash
python main.py
```
3. The script will :
   - Read the game name and links from `input.txt`.
   - Download all files to the `downloads/<game-name>/` folder.
   - Remove processed links from `input.txt` as they complete.

> **Note :** You no longer need to manually paste links into `input.txt` — `get_links.py` handles that automatically.

## Disclaimer
This tool is created for educational purposes and ethical use only. Any misuse of this tool for malicious purposes is not condoned. The developers of this tool are not responsible for any illegal or unethical activities carried out using this tool.

[![Star History Chart](__https://api.star-history.com/svg?repos=JoyNath1337/Fitgirl-Easy-Downloader&type=Date__)](__https://star-history.t9t.io/#JoyNath1337/Fitgirl-Easy-Downloader&Date__)