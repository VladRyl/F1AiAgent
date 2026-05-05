import os
import time
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from dotenv import load_dotenv

COOKIE_CACHE_PATH = "cookie_cache.txt"

def get_f1_fantasy_cookie():
    load_dotenv()
    email = os.getenv("FANTASY_EMAIL")
    password = os.getenv("FANTASY_PASSWORD")
    
    if not email or not password:
        return "Error: FANTASY_EMAIL or FANTASY_PASSWORD not set in .env"

    try:
        with sync_playwright() as p:
            # Using persistent context to look more like a real browser
            user_data_dir = os.path.abspath("playwright_data")
            print(f"Using browser profile in {user_data_dir}")
            
            context = p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=True,
                ignore_default_args=["--enable-automation"],
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-web-security",
                ],
                viewport={'width': 1280, 'height': 800},
                locale="uk-UA",
                timezone_id="Europe/Kiev",
                bypass_csp=True
            )
            page = context.pages[0]
            # Apply stealth to the page
            Stealth().apply_stealth_sync(page)
            
            login_url = os.getenv("FANTASY_LOGIN_URL")
            print(f"Navigating to {login_url}...")
            page.goto(login_url)
            
            # Handle Cookies
            try:
                print("Waiting for cookie banner...")
                # Small wait for banner to appear
                time.sleep(3)
                
                # Check main page and all iframes
                found = False
                for frame in page.frames:
                    try:
                        # Try specific title attribute provided by user
                        accept_btn = frame.locator('button[title="Accept all"]')
                        if accept_btn.count() > 0 and accept_btn.first.is_visible():
                            accept_btn.first.click()
                            found = True
                            print(f"Accepted cookies in frame: {frame.name or 'main'}")
                            break
                        
                        # Try standard OneTrust ID
                        accept_btn = frame.locator('button#onetrust-accept-btn-handler')
                        if accept_btn.count() > 0 and accept_btn.first.is_visible():
                            accept_btn.first.click()
                            found = True
                            print(f"Accepted cookies via OneTrust ID in frame: {frame.name or 'main'}")
                            break
                    except Exception:
                        continue
                
                if not found:
                    print("Cookie banner not found or already dismissed.")
            except Exception as e:
                print(f"Cookie banner interaction failed: {e}")

            time.sleep(3)
                
            # Click Sign In
            print("Clicking Sign In button...")
            page.mouse.move(100, 200)
            time.sleep(1)
            page.mouse.wheel(0, 300)
            page.click('button[aria-label="SIGN IN"]')
            
            # Wait for login page fields - F1 login often uses account.formula1.com
            print("Waiting for login fields...")
            # We look for common login field attributes
            email_selector = 'input[name="Login"], input[name="Email"], input[type="email"], input.txtLogin'
            password_selector = 'input[name="Password"], input.txtPassword'
            
            try:
                # Use .first to avoid strict mode violations if multiple similar fields exist
                page.locator(email_selector).first.wait_for(timeout=20000)
            except Exception:
                print("Initial selectors failed, checking all frames...")
                # Sometimes the login form is also in a frame
                for frame in page.frames:
                    if frame.locator(email_selector).count() > 0:
                        print(f"Found login fields in frame: {frame.name}")
                        page = frame # Treat this frame as the main page for filling
                        break
            
            # Fill credentials
            print("Filling credentials...")
            page.locator(email_selector).first.type(email, delay=100)
            time.sleep(1)
            page.locator(password_selector).first.type(password, delay=100)
            
            # Small wait before submit to look more human
            page.mouse.move(100, 200)
            time.sleep(1)
            page.mouse.wheel(0, 300)

            # Submit
            print("Submitting login...")
            # Find the submit button
            submit_btn = page.locator('button:has-text("Log In"), button.btn-primary, button[type="submit"]')
            submit_btn.first.click()
            
            # Wait for redirect back to fantasy or for the session to be established
            # We look for a change in URL or a specific element on the fantasy page
            print("Waiting for redirect...")
            page.wait_for_url("**/fantasy.formula1.com/**", timeout=30000)
            
            # Extra wait for cookies to be set
            time.sleep(5)
            
            # Extract cookies
            cookies = context.cookies()
            cookie_string = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
            
            context.close()
            return cookie_string
    except Exception as e:
        return f"Error during automation: {str(e)}"

def update_env_cookie(cookie_string):
    if cookie_string.startswith("Error"):
        return False
    try:
        with open(COOKIE_CACHE_PATH, "w") as f:
            f.write(cookie_string)
        print(f"Updated cookie in {COOKIE_CACHE_PATH}")
        return True
    except Exception as e:
        print(f"Failed to save cookie: {e}")
        return False

def load_cached_cookie():
    if os.path.exists(COOKIE_CACHE_PATH):
        try:
            with open(COOKIE_CACHE_PATH, "r") as f:
                return f.read().strip()
        except Exception:
            return None
    return None

if __name__ == "__main__":
    cookie = get_f1_fantasy_cookie()
    if update_env_cookie(cookie):
        print("Successfully refreshed cookie.")
    else:
        print(f"Failed to refresh cookie: {cookie}")
