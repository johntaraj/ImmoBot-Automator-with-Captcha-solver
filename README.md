# ImmoScout24 Auto Messenger (GUI)

A Windows-friendly GUI app that automates contacting new listings on ImmoScout24. It attaches to a running browser (Chrome/Edge/Firefox), watches the search results page for new listings, fills your details and cover letter, and sends the message. Includes a built-in CAPTCHA solver powered by a local model.

> Status: Personal project. Use responsibly and in accordance with ImmoScout24’s terms. This tool interacts with a real website—be considerate with rates and volume.

https://github.com/user-attachments/assets/df178d38-94cf-4cfb-b6be-2ab55f6c9c87

## Features

- Simple GUI (PySide6)
- One‑click connect to running browser with auto-launch if needed
- Works with Chrome, Edge, and Firefox (Opera currently not supported)
- Persisted profile: your form details and cover letter are saved
- Live logs with levels and connection status indicators
- CAPTCHA solver using a local model (EfficientNet‑based; checkpoint included)
- Listing history and retry queues to avoid duplicates

## Contents


- `gui.py` — GUI application
- `runner.py` — Launches the bot with your config and selected browser
- `imo.py` — Selenium automation
- `prediction.py` — CAPTCHA solver (to get the local model "Checkpoint.pth" for solving the captchas check out my other repo https://github.com/johntaraj/pytorch-captcha-recognizer-notebook ) 
- `style.qss` — GUI styles
- `assets/` — UI assets (spinner/info icons)
- `data/` — App data files written at runtime

## Setup

```powershell
python -m pip install --upgrade pip ; `
  pip install PySide6 selenium beautifulsoup4 torch torchvision opencv-python-headless numpy pillow
```

## Run

```powershell
python gui.py
```

- Choose a browser (Chrome/Edge recommended)
- Optional: Use "Launch Selected Browser"
- Click "Connect & Start Bot"

The GUI will save your form details to `config.json` and show logs as the bot operates.



