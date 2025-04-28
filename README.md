# Basic Instructions

If you want to simply view the output (strongly recommended first step) please feel free to open the `TedlarAI.html` file in your browser.
The `TedlarAI.html` file is a web-based dashboard that provides an interactive interface for viewing leads and their associated information. If you click on a company name it will expand to show relevant employees and their LinkedIn profile link as well as an option to copy into your clipboard a customised message for that individual (this is automated).

If you want to play with the code itself, you'll want to start with the `scrape_trade_show.py` file. This is the main entry point for the program as it is the point at which all companies exhibiting are scraped. It's important to note that it will not run in headless mode and will likely adjust the rest of the code as you have begun the process of data scraping. 
The next step is to run `scraper.py` which will scrape the market caps and revenues of the companies from the trade show. This will create a CSV file with the company names, market caps, and revenues.

Following this, `ranker.py` should be run and subsequently `lead_info.py` can be run. This will pull the necessary information for the leads at each company from Google.

At this point you're ready to open the `TedlarAI.html` file in your browser.

Alternatively, after editing `scrape_trade_show_vendors.py` if you were doing this for a different company's set of desired trade shows, you could subsequently run the `auto.py` script which will run everything sequentially for you!