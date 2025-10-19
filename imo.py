import json
import time
import os
import random
import re
import shutil
import base64
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.keys import Keys

from prediction import solve_captcha

# --- BROWSER SELECTION ---
# Change this variable to "chrome", "firefox", or "edge"
selectBrowser = "edge"
START_URL = "https://www.immobilienscout24.de/Suche/de/berlin/berlin/wohnung-mieten"

# --- Configuration ---
FORCE_CAPTCHA_LOWERCASE = True
IGNORE_KEYWORDS = ["senioren", "seniorenwohnung", "service-wohnen"]
FORM_DATA = {
    "salutation": "Herr", "firstName": "John", "lastName": "Musterman",
    "emailAddress": "john.musterman@gmail.com", "phoneNumber": "+1234567890",
    "street": "Musterstraße", "houseNumber": "2", "postcode": "12345", "city": "Berlin",
    "moveInDateType": "ab sofort", "numberOfPersons": "Einpersonenhaushalt",
    "employmentRelationship": "Student:in", "income": "1.000 - 1.500 €",
    "applicationPackageCompleted": "Vorhanden", "numberOfAdults": "1",
    "numberOfKids": "0", "incomeAmount": "1.400", "hasPets": "Nein",
    "employmentStatus": "Unbefristet", "forCommercialPurposes": "Nein",
    "rentArrears": "Nein", "insolvencyProcess": "Nein", "smoker": "Nein",
}

COVER_LETTER = """cover_letter": "Sehr geehrte Damen und Herren, mein Name ist John Musterman, ich bin 26 Jahre alt und studiere derzeit Informatik (M.Sc) an der TU Berlin. Ich arbeite als Werkstudent bei der Mustermedia, mit stabilem Einkommen und kann mir die Wohnung ohne Probleme leisten. Ich bin ruhig, zuverlässig, rauche nicht und habe keine Haustiere. Ich bin sehr an der Wohnung interessiert, da sie ideal zu meinen Vorstellungen von einem langfristigen und ruhigen Zuhause passt. Ich würde mich sehr über eine Rückmeldung und eine Einladung zur Besichtigung freuen. Mit freundlichen Grüßen John Musterman"
"""
LISTING_HISTORY_FILE = 'listing_history.json'
TODO_FILE = 'todo.json'
REPEAT_FILE = 'repeat.json'
CAPTCHA_IMAGE_PATH = 'captcha_screenshot.png'

def load_json_file(filename):
    if not os.path.exists(filename): return []
    try:
        with open(filename, 'r', encoding='utf-8') as f: return json.load(f)
    except json.JSONDecodeError: return []

def save_json_file(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def save_to_history(name, url, status="success"):
    history = load_json_file(LISTING_HISTORY_FILE)
    history.append({"name": name, "url": url, "status": status, "timestamp": time.time()})
    if len(history) > 150: history = history[-150:]
    save_json_file(LISTING_HISTORY_FILE, history)

def handle_captcha(driver):
    print("- Checking for CAPTCHA...")
    SUCCESS_DIR, FAIL_DIR = os.path.join("captcha_dataset", "success"), os.path.join("captcha_dataset", "fail")
    os.makedirs(SUCCESS_DIR, exist_ok=True); os.makedirs(FAIL_DIR, exist_ok=True)
    try:
        time.sleep(20)
        WebDriverWait(driver, 5).until(EC.visibility_of_element_located((By.XPATH, "//img[contains(@src, 'getimage.go')]")))
        print("- CAPTCHA detected.")
    except TimeoutException:
        try:
            WebDriverWait(driver, 2).until(EC.visibility_of_element_located((By.XPATH, "//*[contains(text(), 'Nachricht gesendet')]")))
            print("- Success! No CAPTCHA needed."); return True
        except TimeoutException:
            print("- No CAPTCHA or success message found."); return False
    session_screenshots = []
    for attempt in range(6):
        print(f"\n--- CAPTCHA Attempt {attempt + 1}/6 ---")
        try:
            img_element = WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.XPATH, "//img[contains(@src, 'getimage.go')]")))
            javascript = "var ele = arguments[0]; var cnv = document.createElement('canvas'); cnv.width = ele.naturalWidth; cnv.height = ele.naturalHeight; var ctx = cnv.getContext('2d'); ctx.drawImage(ele, 0, 0); return cnv.toDataURL('image/png').substring(22);"
            image_base64 = driver.execute_script(javascript, img_element)
            with open(CAPTCHA_IMAGE_PATH, 'wb') as f: f.write(base64.b64decode(image_base64))
            solution = solve_captcha(CAPTCHA_IMAGE_PATH)
            if not solution: solution = "unknown"
            if FORCE_CAPTCHA_LOWERCASE: solution = solution.lower()
            sanitized_solution = re.sub(r'[\\/*?:"<>|]', "", solution)
            timestamp = int(time.time() * 1000)
            fail_path = os.path.join(FAIL_DIR, f"{sanitized_solution}_{timestamp}.png")
            shutil.copy(CAPTCHA_IMAGE_PATH, fail_path)
            session_screenshots.append(fail_path)
            print(f"- Prediction: '{solution}'. Screenshot saved to FAIL folder.")
            input_field = driver.find_element(By.ID, "userAnswer")
            input_field.clear(); input_field.send_keys(solution)
            driver.find_element(By.XPATH, "//button[text()='Bestätigen']").click()
            print("- Submitted solution. Waiting 5s...")
            time.sleep(5)
            if "Nachricht gesendet" in driver.page_source:
                print("+++ CAPTCHA Solved! +++")
                last_attempt_path = session_screenshots[-1]
                success_path = os.path.join(SUCCESS_DIR, os.path.basename(last_attempt_path))
                shutil.move(last_attempt_path, success_path)
                print(f"- Moved screenshot to SUCCESS folder.")
                return True
            elif "Die Eingabe weicht vom Bild ab" in driver.page_source:
                print("- Incorrect solution.")
            else:
                print("- Unknown response.")
        except Exception as e:
            print(f"- Error during CAPTCHA attempt: {e}")
    print("--- Max CAPTCHA attempts reached. ---"); return False

def process_listing_page(driver, listing_url, search_page_url):
    print(f"\n--- Processing listing: {listing_url} ---")
    try:
        driver.get(listing_url)
        try:
            WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, "//*[contains(., 'Alle akzeptieren')]"))).click()
        except TimeoutException: pass
        contact_button_xpath = "//button[@data-testid='contact-button'] | //button[.//span[contains(text(), 'Nachricht')]] | //a[contains(., 'Nachricht')]"
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.XPATH, contact_button_xpath)))
        all_possible_buttons = driver.find_elements(By.XPATH, contact_button_xpath)
        button_clicked = False
        for button in all_possible_buttons:
            try:
                if button.is_displayed() and button.is_enabled():
                    button.click(); button_clicked = True; print("- Clicked 'Nachricht' button."); break
            except Exception: continue
        if not button_clicked: raise Exception("Could not find any interactable 'Nachricht' button.")
        message_box = WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.NAME, "message")))
        print("- Form is visible. Filling...")
        message_box.send_keys(Keys.CONTROL + "a"); message_box.send_keys(Keys.BACK_SPACE)
        message_box.send_keys(COVER_LETTER)
        for key, value in FORM_DATA.items():
            try:
                element = None
                try: element = driver.find_element(By.NAME, key)
                except NoSuchElementException: element = driver.find_element(By.ID, key)
                if element.tag_name == 'select': Select(element).select_by_visible_text(value)
                elif element.get_attribute('type') in ['text', 'email', 'tel'] and not element.get_attribute('disabled'):
                    element.send_keys(Keys.CONTROL + "a"); element.send_keys(Keys.BACK_SPACE); element.send_keys(value)
            except Exception: pass
        print("- Form filled. Waiting 10s...")
        time.sleep(10)
        driver.find_element(By.XPATH, "//form[@data-testid='contact-form']//button[@type='submit']").click()
        print("- Clicked 'Abschicken'.")
        success = handle_captcha(driver)
        return success
    except Exception as e:
        print(f"An unexpected error occurred: {e}"); return False
    finally:
        print("- Navigating back to search results."); driver.get(search_page_url)


def main():
    print("--- ImmoScout24 Automation Bot ---")
    print(f"Selected browser: {selectBrowser.upper()}")
    port = 2828 if selectBrowser.lower() == "firefox" else 9222
    print(f"Attempting to attach to 127.0.0.1:{port}...")

    try:
        if selectBrowser.lower() == "chrome":
            options = ChromeOptions()
            options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
            driver = webdriver.Chrome(options=options)

        elif selectBrowser.lower() == "edge":
            options = EdgeOptions()
            # Ensure Chromium mode for modern Edge
            try:
                options.use_chromium = True
            except Exception:
                pass
            options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
            driver = webdriver.Edge(options=options)

        elif selectBrowser.lower() == "firefox":
            from selenium.webdriver.firefox.service import Service as FirefoxService
            service = FirefoxService(port=2828)
            driver = webdriver.Firefox(service=service)

        elif selectBrowser.lower() == "opera":
            # Opera support removed (selenium.webdriver.opera deprecated in Selenium 4)
            print("Error: Opera is not supported in this build. Please use Chrome, Edge, or Firefox.")
            return
            
        else:
            print(f"Error: Invalid browser '{selectBrowser}'. Please choose 'chrome', 'edge', 'firefox', or 'opera'.")
            return
        print("Successfully connected to the browser.")
        print("CONNECTED_OK")

        try:
            current = driver.current_url
        except Exception:
            current = ""
        if "Suche" not in current:
            print(f"- Not on a search page. Navigating to start URL: {START_URL}")
            driver.get(START_URL)
            try:
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            except Exception:
                pass

    except Exception as e:
        print(f"Error connecting to browser: {e}")
        print("Please ensure the browser was started with the correct remote debugging command and port.")
        return

    while True:
        print("\n--- Main Loop: Checking for tasks ---")
        try:
            print("- Checking for new listings using 'view-source' method...")
            current_search_url = driver.current_url
            if "Suche" not in current_search_url:
                print("Error: Not on a search results page. Waiting..."); time.sleep(30); continue
            driver.get("view-source:" + current_search_url)
            raw_html_string = driver.find_element(By.TAG_NAME, "body").text
            driver.get(current_search_url)
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            history_urls = {item['url'] for item in load_json_file(LISTING_HISTORY_FILE)}
            todo_list = load_json_file(TODO_FILE)
            todo_urls = {item['url'] for item in todo_list}
            repeat_urls = {item['url'] for item in load_json_file(REPEAT_FILE)}
            pattern = re.compile(r'"@type":"RealEstateListing","name":"(.*?)","url":"(.*?)"')
            matches = pattern.findall(raw_html_string)
            if matches:
                all_listings = [{'name': name, 'url': url} for name, url in matches]
                newly_found_listings = []
                for listing in all_listings[:20]:
                    name = listing['name'].encode('utf-8').decode('unicode_escape')
                    url = listing['url']
                    if any(keyword in name.lower() for keyword in IGNORE_KEYWORDS): continue
                    if url not in history_urls and url not in todo_urls and url not in repeat_urls:
                        newly_found_listings.append({'name': name, 'url': url})
                if newly_found_listings:
                    print(f"- Found {len(newly_found_listings)} new listings. Adding to to-do list.")
                    todo_list = newly_found_listings + todo_list
                    save_json_file(TODO_FILE, todo_list)
                else:
                    print("- No new listings found in the source data.")
            else:
                print("- Could not find any listings using the Regex pattern.")
            if todo_list:
                next_task = todo_list.pop(0)
                print(f"- Processing from TO-DO list: {next_task['name']}")
                success = process_listing_page(driver, next_task['url'], current_search_url)
                if success:
                    save_to_history(next_task['name'], next_task['url'], status="success")
                    print(f"- SUCCESS. Moved '{next_task['name']}' to history.")
                else:
                    repeat_list = load_json_file(REPEAT_FILE)
                    repeat_list.append(next_task)
                    save_json_file(REPEAT_FILE, repeat_list)
                    print(f"- FAILED. Moved '{next_task['name']}' to repeat list.")
                save_json_file(TODO_FILE, todo_list)
            elif (repeat_list := load_json_file(REPEAT_FILE)):
                next_task = repeat_list.pop(0)
                print(f"- To-do list empty. Processing from REPEAT list: {next_task['name']}")
                success = process_listing_page(driver, next_task['url'], current_search_url)
                status = "success_on_retry" if success else "failed_on_retry"
                save_to_history(next_task['name'], next_task['url'], status=status)
                print(f"- Moved '{next_task['name']}' to history with status: {status}.")
                save_json_file(REPEAT_FILE, repeat_list)
            else:
                wait_time = random.uniform(30, 70)
                print(f"- All lists empty. Waiting for {wait_time:.0f} seconds.")
                time.sleep(wait_time)
        except Exception as e:
            print(f"An critical error occurred in main loop: {e}")
            print("Waiting 60 seconds before retrying...")
            time.sleep(60)

if __name__ == "__main__":
    main()