import unittest
from unittest.mock import Mock, patch, MagicMock
import json
from bs4 import BeautifulSoup
from app import FoodpandaScraper

class TestFoodpandaScraper(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.scraper = FoodpandaScraper(headless=True)
        
        # Sample HTML content for testing
        self.sample_html = """
        <html>
            <head>
                <title>Test Restaurant</title>
            </head>
            <body>
                <h1>Test Restaurant Name</h1>
                <img class="vendor-logo__image" src="test-image.jpg"/>
                <div data-testid="vendor-info-modal-vendor-address">
                    <h1>123 Test Street, Lahore, Punjab 54000</h1>
                </div>
                <ul class="main-info__characteristics">
                    <span>Italian</span>
                    <span>Pizza</span>
                </ul>
                <ul class="bds-c-tabs__list">
                    <button><span>Appetizers (5)</span></button>
                    <button><span>Main Course (10)</span></button>
                </ul>
                <div class="menu">
                    <ul class="dish-list-grid">
                        <li>
                            <h3><span data-testid="menu-product-name">Test Item</span></h3>
                            <p class="product-tile__description">Test description</p>
                            <p data-testid="menu-product-price">Rs. 500</p>
                            <picture class="product-tile__image">
                                <div style="background-image: url('item-image.jpg')"></div>
                            </picture>
                        </li>
                        <li>
                            <h3><span data-testid="menu-product-name">Test Item 2</span></h3>
                            <p class="product-tile__description">Test description 2</p>
                            <p data-testid="menu-product-price">Rs. 1000</p>
                            <picture class="product-tile__image">
                                <div style="background-image: url('item-image.jpg')"></div>
                            </picture>
                        </li>
                    </ul>
                </div>
            </body>
        </html>
        """
        self.soup = BeautifulSoup(self.sample_html, 'html.parser')

    def test_get_domain_extension(self):
        """Test domain extension mapping for different locations"""
        test_cases = [
            ("pakistan", "pk"),
            ("singapore", "sg"),
            ("malaysia", "my"),
            ("invalid_location", "com")
        ]
        
        for location, expected in test_cases:
            with self.subTest(location=location):
                result = self.scraper._get_domain_extension(location)
                self.assertEqual(result, expected)

    def test_get_text(self):
        """Test text extraction from HTML elements"""
        # Test with existing element
        result = self.scraper._get_text(self.soup, "h1")
        self.assertEqual(result, "Test Restaurant Name")
        
        # Test with non-existing element
        result = self.scraper._get_text(self.soup, "non-existing")
        self.assertEqual(result, "")

    def test_get_image(self):
        """Test image URL extraction"""
        result = self.scraper._get_image(self.soup)
        self.assertEqual(result, "test-image.jpg")

    def test_get_cuisines(self):
        """Test cuisine extraction"""
        result = self.scraper._get_cuisines(self.soup)
        self.assertEqual(result, ["Italian", "Pizza"])

    def test_get_address(self):
        """Test address extraction"""
        result = self.scraper._get_address(self.soup)
        self.assertEqual(result, "123 Test Street, Lahore, Punjab 54000")

    @patch('selenium.webdriver.Chrome')
    def test_setup_webdriver(self, mock_chrome):
        """Test webdriver setup with mocked Chrome driver"""
        scraper = FoodpandaScraper(headless=True)
        mock_chrome.assert_called_once()
        self.assertIsNotNone(scraper.driver)

    @patch('selenium.webdriver.Chrome')
    def test_get_restaurant_urls(self, mock_chrome):
        """Test restaurant URL collection with mocked driver"""
        mock_driver = MagicMock()
        mock_chrome.return_value = mock_driver
        mock_driver.page_source = self.sample_html
        
        scraper = FoodpandaScraper(headless=True)
        urls = scraper.get_restaurant_urls(limit=1)
        
        self.assertIsInstance(urls, list)

    def test_extract_menu_items(self):
        """Test menu item extraction"""
        container = self.soup.select_one("div.menu")
        result = self.scraper._get_menu_items(container)
        
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["name"], "Test Item")
        self.assertEqual(result[0]["description"], "Test description")
        self.assertEqual(result[0]["price"], "500")
        self.assertEqual(result[0]["image"], "item-image.jpg")
        self.assertEqual(result[1]["name"], "Test Item 2")
        self.assertEqual(result[1]["description"], "Test description 2")
        self.assertEqual(result[1]["price"], "1000")
        self.assertEqual(result[1]["image"], "item-image.jpg")

    def test_save_data(self):
        """Test data saving functionality"""
        test_data = [{
            "name": "Test Restaurant",
            "cuisines": ["Italian"],
            "menu": [{
                "category": "Main",
                "items": [{
                    "name": "Test Item",
                    "description": "Test Description",
                    "price": "100",
                    "image": "test.jpg"
                }]
            }]
        }]
        
        self.scraper.data = test_data
        
        with patch('builtins.open', unittest.mock.mock_open()) as mock_file:
            self.scraper._save_data()
            mock_file.assert_called()

    def tearDown(self):
        """Clean up after each test method."""
        if hasattr(self.scraper, 'driver'):
            self.scraper.close()

if __name__ == '__main__':
    unittest.main() 