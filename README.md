# Foodpanda Web Scraper

A Python package for scraping restaurant information from Foodpanda, including restaurant details, location data, and menu items.

## Features

- Scrapes restaurant information including:
  - Restaurant details (name, image, address, contact info)
  - Location data (coordinates, postal code)
  - Menu items with descriptions, prices, and images
- Supports multiple locations/countries
- Handles captcha detection
- Saves data in both JSON and CSV formats
- Configurable scraping limits
- Headless browser support

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/foodpanda-scraper.git
cd foodpanda-scraper
```

2. Create and activate a virtual environment (optional but recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install the required packages:
```bash
pip install -r requirements.txt
```

## Usage

Run the scraper with default settings:
```bash
python ./app.py
```

### Command Line Arguments

- `--location`: Location to search for restaurants (default: "pakistan")
- `--limit`: Maximum number of restaurant URLs to collect (default: 100)
- `--max-restaurants`: Maximum number of restaurants to scrape (default: 100)
- `--headless`: Run browser in headless mode

Example:
```bash
python -m foodpanda_scraper --location singapore --limit 50 --max-restaurants 50 --headless
```

### Output

The scraper saves data in two formats:
1. `foodpanda_data.json`: Complete restaurant data in JSON format
2. `foodpanda_data.csv`: Flattened data in CSV format, including menu items

## Project Structure

```
foodpanda_scraper/
├── __init__.py
├── __main__.py
├── models.py
├── scrapers/
│   ├── __init__.py
│   ├── base_scraper.py
│   └── foodpanda_scraper.py
└── utils/
    ├── __init__.py
    └── helpers.py
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 