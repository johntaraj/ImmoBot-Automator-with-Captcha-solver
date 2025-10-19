import sys
import json
import imo as imo_bot 

CONFIG_FILE = 'config.json'
SELECTED_BROWSER = 'edge' # Default

def run_bot():
    """
    Loads config from the GUI, patches the bot's variables,
    and runs the main function.
    """
    try:
        # Load settings saved by the GUI
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)

        imo_bot.FORM_DATA = config.get('form_data', {})
        imo_bot.COVER_LETTER = config.get('cover_letter', '')
        imo_bot.selectBrowser = SELECTED_BROWSER

        print(f"--- Runner script initiated for browser: {SELECTED_BROWSER.upper()} ---")
        print("--- Settings loaded from config.json ---")

        # Now, call the main function from your original script
        imo_bot.main()

    except FileNotFoundError:
        print(f"FATAL: {CONFIG_FILE} not found. Please save settings in the GUI first.")
    except Exception as e:
        print(f"An error occurred in the runner script: {e}")
        # This ensures the GUI knows something went wrong.
        sys.exit(1)

if __name__ == "__main__":
    # The browser type is passed as a command-line argument from the GUI
    if len(sys.argv) > 1:
        SELECTED_BROWSER = sys.argv[1]
    run_bot()