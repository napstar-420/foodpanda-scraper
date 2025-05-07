"""
Foodpanda Web Scraper

This script scrapes restaurant information from Foodpanda, including:
- Restaurant details (name, image, address, contact info)
- Location data (coordinates, postal code)
- Menu items with descriptions, prices, and images

Usage:
1. Install required packages: pip install -r requirements.txt
2. Run the script: python app.py
3. Output will be saved to foodpanda_data.json
"""

import time
import json
import random
import argparse
import pandas as pd
from typing import Dict, List, Any, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
)
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import logging
import re
import os
from urllib.parse import urljoin

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("foodpanda_scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class FoodpandaScraper:
    """Class to scrape restaurant data from Foodpanda"""
    
    def __init__(self, headless: bool = True, location: str = "pakistan"):
        """
        Initialize the scraper with webdriver configuration
        
        Args:
            headless: Whether to run browser in headless mode
            location: Location/city to search for restaurants
        """
        self.location = location
        self.base_url = f"https://www.foodpanda.{self._get_domain_extension(location)}"
        self.restaurants_url = f"{self.base_url}/restaurants/new?lng=74.31613&lat=31.53391"
        self.data = []
        self.setup_webdriver(headless)
        logger.info(f"Initialized scraper for {self.restaurants_url}")
        
    def _get_domain_extension(self, location: str) -> str:
        """Get the appropriate domain extension based on location"""
        location_map = {
            "singapore": "sg",
            "malaysia": "my",
            "thailand": "co.th",
            "philippines": "ph",
            "hong kong": "hk",
            "taiwan": "tw",
            "pakistan": "pk",
            "bangladesh": "com.bd",
            "japan": "jp",
            "germany": "de"
        }
        return location_map.get(location.lower(), "com")
    
    def setup_webdriver(self, headless: bool) -> None:
        """Set up the Chrome WebDriver"""
        try:
            chrome_options = Options()
            if headless:
                chrome_options.add_argument("--headless=new")  # Use new headless mode
            
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--disable-notifications")
            chrome_options.add_argument("--disable-popup-blocking")
            chrome_options.add_argument("--disable-infobars")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--lang=en-US")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Add user agent to avoid detection
            chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Set page load timeout
            self.driver.set_page_load_timeout(30)
            
            # Execute CDP commands to prevent detection
            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    })
                '''
            })
            
            logger.info("WebDriver setup complete")
            
        except Exception as e:
            logger.error(f"Error setting up WebDriver: {str(e)}")
            raise
    
    def get_restaurant_urls(self, limit: Optional[int] = None) -> List[str]:
        """
        Get URLs for individual restaurant pages
        
        Args:
            limit: Maximum number of restaurant URLs to collect (None for all available)
            
        Returns:
            List of restaurant URLs
        """
        try:
            logger.info(f"Navigating to restaurants page: {self.restaurants_url}")
            self.driver.get(self.restaurants_url)
            
            # Check for captcha and wait for user to solve it
            try:
                captcha_selectors = [
                    "iframe[src*='captcha']",
                    "iframe[src*='recaptcha']",
                    "div[class*='captcha']",
                    "div[class*='recaptcha']"
                ]
                
                for selector in captcha_selectors:
                    try:
                        captcha_element = WebDriverWait(self.driver, 5).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                        )
                        if captcha_element:
                            logger.info("Captcha detected. Please solve the captcha manually...")
                            input("Press Enter after solving the captcha to continue...")
                            break
                    except TimeoutException:
                        continue
            except Exception as e:
                logger.warning(f"Error checking for captcha: {str(e)}")
            
            # Wait for any loading indicators to disappear
            try:
                WebDriverWait(self.driver, 10).until_not(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[class*='loading'], [class*='spinner']"))
                )
            except TimeoutException:
                logger.warning("Loading indicators not found or not disappearing")
            
            # Try multiple selectors for restaurant cards
            restaurant_selectors = [
                "a[data-testid='restaurant-card']",
                "a[href*='/restaurant/']",
                "a[class*='restaurant']",
                "a[class*='vendor']"
            ]
            
            restaurant_urls = []
            for selector in restaurant_selectors:
                try:
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                    cards = soup.select(selector)
                    
                    for card in cards:
                        url = card.get('href')
                        if url and url not in restaurant_urls:
                            full_url = urljoin(self.base_url, url)
                            restaurant_urls.append(full_url)
                    
                    if restaurant_urls:
                        break
                except TimeoutException:
                    continue
            
            if not restaurant_urls:
                logger.warning("No restaurant URLs found with any selector")
                return []
            
            # Scroll to load more restaurants
            prev_count = 0
            scroll_attempts = 0
            max_scroll_attempts = 20
            
            while (limit is None or len(restaurant_urls) < limit) and scroll_attempts < max_scroll_attempts:
                # Extract restaurant URLs
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                for selector in restaurant_selectors:
                    cards = soup.select(selector)
                    for card in cards:
                        url = card.get('href')
                        if url and url not in restaurant_urls:
                            full_url = urljoin(self.base_url, url)
                            restaurant_urls.append(full_url)
                
                if len(restaurant_urls) == prev_count:
                    scroll_attempts += 1
                else:
                    scroll_attempts = 0
                
                prev_count = len(restaurant_urls)
                logger.info(f"Found {len(restaurant_urls)} restaurant URLs so far")
                
                # Scroll down to load more results
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(1.5, 3.0))
                
                # Check if we've reached our limit
                if limit and len(restaurant_urls) >= limit:
                    restaurant_urls = restaurant_urls[:limit]
                    break
            
            logger.info(f"Successfully collected {len(restaurant_urls)} restaurant URLs")
            return restaurant_urls
            
        except Exception as e:
            logger.error(f"Error getting restaurant URLs: {str(e)}")
            return []
    
    def extract_restaurant_details(self, url: str) -> Dict[str, Any]:
        """
        Extract detailed information from a restaurant page
        
        Args:
            url: URL of the restaurant page
            
        Returns:
            Dictionary containing restaurant information
        """
        try:
            logger.info(f"Scraping restaurant: {url}")
            self.driver.get(url)
            
            # Check for captcha and wait for user to solve it
            try:
                captcha_selectors = [
                    "iframe[src*='captcha']",
                    "iframe[src*='recaptcha']",
                    "div[class*='captcha']",
                    "div[class*='recaptcha']"
                ]
                
                for selector in captcha_selectors:
                    try:
                        captcha_element = WebDriverWait(self.driver, 5).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                        )
                        if captcha_element:
                            logger.info("Captcha detected in restaurant page. Please solve the captcha manually...")
                            input("Press Enter after solving the captcha to continue...")
                            break
                    except TimeoutException:
                        continue
            except Exception as e:
                logger.warning(f"Error checking for captcha: {str(e)}")
            
            # Wait for page to load
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "h1"))
            )
            
            # Allow time for dynamic content to load
            time.sleep(random.uniform(3.0, 5.0))
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # Basic restaurant info
            restaurant_data = {
                "name": self._get_text(soup, "h1"),
                "image": self._get_image(soup),
                "state": "punjab",
                "city": "Lahore",
                "country_code": "PK",
                "postal_code": "54000",
                "email": "",
                "cuisines": self._get_cuisines(soup),
                "latitude": self._get_latitude(soup),
                "longitude": self._get_longitude(soup),
                "price_range": "$$$",
                "phone": "",
                "menu": self._get_menu(soup),
                "address": self._get_address(soup),
            }
            
            logger.info(f"Successfully scraped restaurant: {restaurant_data['name']}")
            return restaurant_data
            
        except Exception as e:
            logger.error(f"Error extracting restaurant details from {url}: {e}")
            return {"url": url, "error": str(e)}
    
    def _get_text(self, soup, selector, default=""):
        """Extract text from an element or return default value"""
        try:
            element = soup.select_one(selector)
            return element.get_text(strip=True) if element else default
        except Exception:
            return default
    
    def _get_image(self, soup):
        """Extract restaurant main image"""
        try:
            # Try finding image in hero section first
            hero_img = soup.select_one("img.vendor-logo__image")
            if hero_img and hero_img.get('src'):
                return hero_img['src']
            
            # Fallback to other image containers
            img = soup.select_one("img[data-testid='restaurant-header-image']")
            if img and img.get('src'):
                return img['src']
                
            # Secondary fallback
            any_img = soup.select_one("img.restaurant-image")
            if any_img and any_img.get('src'):
                return any_img['src']
                
            return ""
        except Exception:
            return ""
    
    def _get_address(self, soup):
        """Extract restaurant address"""
        # Scroll to top of page first
        try:
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(0.5)  # Brief pause to let scroll complete
        except Exception as e:
            logger.debug(f"Could not scroll to top: {e}")

        try:
            # Click the "more info" button to reveal address
            try:
                more_info_btn = self.driver.find_element(By.CSS_SELECTOR, "[data-testid='vendor-info-more-info-btn']")
                more_info_btn.click()
                time.sleep(1)  # Wait for content to load
                
                # Get updated page source after click
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            except Exception as e:
                logger.debug(f"Could not click more info button: {e}")
            # Try multiple selectors where address might be found
            address_selectors = [
                "div[data-testid='vendor-info-modal-vendor-address'] h1",
            ]
            
            for selector in address_selectors:
                address_elem = soup.select_one(selector)
                if address_elem:
                    return address_elem.get_text(strip=True)
            return ""
        except Exception:
            return ""
    
    def _get_state(self, soup):
        """Extract state from address or metadata"""
        try:
            meta_region = soup.select_one("meta[property='og:region']")
            if meta_region and meta_region.get('content'):
                return meta_region['content']
                
            # Try to extract from address
            address = self._get_address(soup)
            # Logic to extract state from address string - would vary by country format
            return ""
        except Exception:
            return ""
    
    def _get_city(self, soup):
        """Extract city from address or metadata"""
        try:
            meta_city = soup.select_one("meta[property='og:locality']")
            if meta_city and meta_city.get('content'):
                return meta_city['content']
                
            # Alternative selectors
            city_elem = soup.select_one("span.city, div.city")
            if city_elem:
                return city_elem.get_text(strip=True)
                
            return ""
        except Exception:
            return ""
    
    def _get_country_code(self):
        """Get country code based on domain"""
        domain_parts = self.base_url.split('.')
        if len(domain_parts) >= 2:
            tld = domain_parts[-1]
            if tld == 'sg':
                return 'SG'
            elif tld == 'my':
                return 'MY'
            elif tld == 'hk':
                return 'HK'
            elif 'co.th' in self.base_url:
                return 'TH'
            # Add more mappings as needed
        return ""
    
    def _get_postal_code(self, soup):
        """Extract postal code from address"""
        try:
            address = self._get_address(soup)
            # Generic postal code pattern - adjust based on country format
            postal_pattern = r'\b\d{5,6}\b'
            match = re.search(postal_pattern, address)
            if match:
                return match.group(0)
            return ""
        except Exception:
            return ""
    
    def _get_email(self, soup):
        """Extract email if available"""
        try:
            # Look for email in contact information
            email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
            
            # Search in page text
            page_text = soup.get_text()
            email_match = re.search(email_pattern, page_text)
            if email_match:
                return email_match.group(0)
                
            # Look for mailto links
            mailto_link = soup.select_one("a[href^='mailto:']")
            if mailto_link and mailto_link.get('href'):
                return mailto_link['href'].replace('mailto:', '')
                
            return ""
        except Exception:
            return ""
    
    def _get_cuisines(self, soup):
        """Extract cuisine types"""
        try:
            cuisines = []
            
            # Try multiple selectors where cuisines might be found
            cuisine_selectors = [
                "ul.main-info__characteristics span",
            ]
            
            for selector in cuisine_selectors:
                cuisine_elements = soup.select(selector)
                if cuisine_elements:
                    for elem in cuisine_elements:
                        cuisine = elem.get_text(strip=True)
                        if cuisine and cuisine not in cuisines:
                            cuisines.append(cuisine)

            return cuisines
        except Exception:
            return []
    
    def _get_latitude(self, soup):
        """Extract latitude from page"""
        try:
            # Look for latitude in meta tags or script data
            meta_lat = soup.select_one("meta[property='place:location:latitude']")
            if meta_lat and meta_lat.get('content'):
                return meta_lat['content']
            
            # Try to find coordinates in script tags
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string:
                    lat_match = re.search(r'"latitude":\s*([-\d.]+)', script.string)
                    if lat_match:
                        return lat_match.group(1)
            
            return ""
        except Exception:
            return ""
    
    def _get_longitude(self, soup):
        """Extract longitude from page"""
        try:
            # Look for longitude in meta tags or script data
            meta_lng = soup.select_one("meta[property='place:location:longitude']")
            if meta_lng and meta_lng.get('content'):
                return meta_lng['content']
            
            # Try to find coordinates in script tags
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string:
                    lng_match = re.search(r'"longitude":\s*([-\d.]+)', script.string)
                    if lng_match:
                        return lng_match.group(1)
            
            return ""
        except Exception:
            return ""
    
    def _get_price_range(self, soup):
        """Extract price range indicator"""
        try:
            # Look for price range indicators ($, $$, $$$)
            price_elem = soup.select_one("span.price-range, div.price-range")
            if price_elem:
                return price_elem.get_text(strip=True)
            
            # Alternative: count $ symbols
            price_symbols = soup.select_one("span[data-testid='price-range']")
            if price_symbols:
                return price_symbols.get_text(strip=True)
                
            return ""
        except Exception:
            return ""
    
    def _get_phone(self, soup):
        """Extract phone number if available"""
        try:
            # Look for phone in contact information
            phone_pattern = r'(?:\+\d{1,3}[-\s]?)?\(?\d{3,4}\)?[-\s]?\d{3}[-\s]?\d{4}'
            
            # Search in page text
            page_text = soup.get_text()
            phone_match = re.search(phone_pattern, page_text)
            if phone_match:
                return phone_match.group(0)
                
            # Look for tel links
            tel_link = soup.select_one("a[href^='tel:']")
            if tel_link and tel_link.get('href'):
                return tel_link['href'].replace('tel:', '')
                
            return ""
        except Exception:
            return ""
    
    def _get_menu(self, soup):
        """Extract menu categories and items"""
        try:
            menu = []
            
            # Find menu categories
            category_selectors = [
                "ul.bds-c-tabs__list button span"
            ]
            
            # Scroll to bottom of page to load all content
            try:
                last_height = self.driver.execute_script("return document.body.scrollHeight")
                while True:
                    # Scroll down slowly in smaller increments
                    for i in range(0, last_height, 300):
                        self.driver.execute_script(f"window.scrollTo(0, {i});")
                        time.sleep(0.3)  # Small delay between scroll steps
                    
                    # Check if we've reached bottom
                    new_height = self.driver.execute_script("return document.body.scrollHeight")
                    if new_height == last_height:
                        break
                    last_height = new_height
                    
                # Get updated page source after scrolling
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            except Exception as e:
                logger.warning(f"Error during page scrolling: {str(e)}")
            
            for selector in category_selectors:
                category_elements = soup.select(selector)
                if category_elements:
                    for i, category_elem in enumerate(category_elements):
                        category_name = re.sub(r'\(\d+\)$', '', category_elem.get_text(strip=True)).strip()
                        
                        # Find category container to extract items
                        menu_items_container = soup.select_one("div.menu")
                        if not menu_items_container:
                            continue

                        menu_items = self._get_menu_items(menu_items_container.contents[i])

                        if menu_items:
                            menu.append({
                                "category": category_name,
                                "items": menu_items
                            })

            return menu
        except Exception as e:
            logger.error(f"Error extracting menu: {e}")
            return []
    
    def _get_menu_items(self, container):
        """Extract menu items from a container"""
        try:
            items = []
            
            # Find menu item containers
            item_selectors = [
                "ul.dish-list-grid"
            ]
            
            for selector in item_selectors:
                item_containers = container.select(selector)
                if item_containers:
                    for container in item_containers:
                        # Find all individual menu items
                        menu_items = container.select("li")
                        for item_elem in menu_items:
                            # Extract item details
                            name = self._get_text(item_elem, "h3 span[data-testid='menu-product-name']", "")
                            description = self._get_text(item_elem, "p.product-tile__description", "")
                            price_text = self._get_text(item_elem, "p[data-testid='menu-product-price']", "")
                            
                            # Clean price text and extract numeric value
                            price = ""
                            if price_text:
                                # Extract only digits, ignoring any text or currency symbols
                                price_match = re.search(r'\d+', price_text)
                                if price_match:
                                    price = price_match.group(0)
                            
                            # Extract image
                            img_elem = item_elem.select_one("picture.product-tile__image div")
                            image = ""
                            if img_elem and img_elem.get('style'):
                                style = img_elem['style']
                                bg_match = re.search(r'background-image:\s*url\([\'"]?(.*?)[\'"]?\)', style)
                                if bg_match:
                                    image = bg_match.group(1)
                            
                            if name:  # Only add items with a name
                                items.append({
                                    "name": name,
                                    "description": description,
                                    "price": price,
                                    "image": image
                                })
            
            return items
        except Exception as e:
            logger.error(f"Error extracting menu items: {e}")
            return []
    
    def scrape(self, limit: Optional[int] = None, max_restaurants: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Main scraping method to extract restaurant data
        
        Args:
            limit: Maximum number of restaurant URLs to collect
            max_restaurants: Maximum number of restaurants to scrape
            
        Returns:
            List of restaurant data dictionaries
        """
        try:
            restaurant_urls = self.get_restaurant_urls(limit)
            
            if max_restaurants:
                restaurant_urls = restaurant_urls[:max_restaurants]
            
            total = len(restaurant_urls)
            logger.info(f"Starting to scrape {total} restaurants")
            
            for i, url in enumerate(restaurant_urls):
                logger.info(f"Processing restaurant {i+1}/{total}: {url}")
                
                # Add random delay between requests
                if i > 0:
                    delay = random.uniform(2.0, 5.0)
                    logger.info(f"Waiting {delay:.2f} seconds before next request")
                    time.sleep(delay)
                
                restaurant_data = self.extract_restaurant_details(url)
                restaurant_data["url"] = url
                self.data.append(restaurant_data)
                
                # Save intermediate results
                if (i + 1) % 5 == 0 or i == total - 1:
                    self._save_data()
            
            return self.data
            
        except Exception as e:
            logger.error(f"Error during scraping: {e}")
            return self.data
        finally:
            self._save_data()
            self.close()
    
    def _save_data(self) -> None:
        """Save the scraped data to JSON and CSV files"""
        try:
            # Save to JSON
            with open("foodpanda_data.json", "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            
            # Save to CSV (flattened structure)
            flattened_data = []
            for restaurant in self.data:
                if not restaurant or "error" in restaurant:
                    continue
                    
                basic_info = {k: v for k, v in restaurant.items() if k != "menu"}
                basic_info["cuisines"] = ", ".join(basic_info.get("cuisines", []))
                
                # Process menu items
                menu = restaurant.get("menu", [])
                if not menu:
                    flattened_data.append(basic_info)
                    continue
                
                for category in menu:
                    cat_name = category.get("category", "")
                    items = category.get("items", [])
                    
                    for item in items:
                        item_data = basic_info.copy()
                        item_data["menu_category"] = cat_name
                        item_data["menu_item_name"] = item.get("name", "")
                        item_data["menu_item_description"] = item.get("description", "")
                        item_data["menu_item_price"] = item.get("price", "")
                        item_data["menu_item_image"] = item.get("image", "")
                        flattened_data.append(item_data)
            
            # Save flattened data
            if flattened_data:
                df = pd.DataFrame(flattened_data)
                df.to_csv("foodpanda_data.csv", index=False, encoding="utf-8")
                
            logger.info(f"Data saved successfully. Current count: {len(self.data)} restaurants")
        except Exception as e:
            logger.error(f"Error saving data: {e}")
    
    def close(self) -> None:
        """Close the WebDriver"""
        try:
            if hasattr(self, 'driver'):
                self.driver.quit()
                logger.info("WebDriver closed")
        except Exception as e:
            logger.error(f"Error closing WebDriver: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape restaurant data from Foodpanda")
    parser.add_argument("--location", type=str, default="pakistan", help="Location to search for restaurants")
    parser.add_argument("--limit", type=int, default=100, help="Maximum number of restaurant URLs to collect")
    parser.add_argument("--max-restaurants", type=int, default=100, help="Maximum number of restaurants to scrape")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    
    args = parser.parse_args()
    
    try:
        scraper = FoodpandaScraper(headless=args.headless, location=args.location)
        data = scraper.scrape(limit=args.limit, max_restaurants=args.max_restaurants)
        
        print(f"Scraping completed. Collected data for {len(data)} restaurants.")
        print(f"Data saved to foodpanda_data.json and foodpanda_data.csv")
    except Exception as e:
        logger.error(f"Script execution failed: {e}")