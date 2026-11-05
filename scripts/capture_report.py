"""Optional one-screen capture. HTML/JSON are retained even without Playwright."""
from pathlib import Path
import sys

folder=Path(sys.argv[1]).resolve()
try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True)
        page=browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
        page.goto((folder/'summary.html').as_uri())
        page.screenshot(path=str(folder/'summary.png'),full_page=True)
        browser.close()
except Exception as error:
    print('Screenshot unavailable; open summary.html and capture one screen:',error)
