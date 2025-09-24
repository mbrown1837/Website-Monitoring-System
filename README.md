# Automated Website Monitoring System

This project is an Automated Website Monitoring System designed to monitor a predefined list of websites, detect changes, and report discrepancies.

## Overview

The system performs the following key functions:
- Manages a list of websites to monitor.
- Schedules regular checks for each website.
- Retrieves web content (HTML).
- Captures HTML and visual (screenshot) snapshots of web pages.
- Compares current versions with previous snapshots to detect changes in:
    - Text content
    - HTML structure
    - Meta tags (description, keywords)
    - Canonical URLs
    - Embedded links
    - Image sources
    - Visual appearance (screenshots)
- Logs check history and detected changes.
- Sends email alerts for significant changes.
- Generates reports in JSON and CSV formats.

## Project Structure

```
.PROJECT_ROOT/
├── config/                 # Configuration files
│   └── config.yaml         # Main configuration (monitoring intervals, paths, SMTP, etc.)
├── data/                   # Data files generated and used by the system
│   ├── websites.json       # List of websites to monitor
│   ├── check_history.json  # Log of all monitoring checks
│   └── snapshots/          # Directory for storing HTML and visual snapshots
│       └── <site_id>/
│           ├── html/
           └── visual/
├── docs/                   # Project documentation (if any)
├── scripts/                # Utility scripts (if any)
├── src/                    # Source code
│   ├── __init__.py
│   ├── alerter.py          # Handles sending email alerts
│   ├── comparators.py      # Logic for comparing different aspects of web pages
│   ├── config_loader.py    # Loads configuration from config.yaml
│   ├── content_retriever.py # Fetches website content
│   ├── history_manager.py  # Manages check history records
│   ├── logger_setup.py     # Configures logging
│   ├── report_generator.py # Generates reports
│   ├── scheduler.py        # Schedules and runs monitoring tasks
│   ├── snapshot_tool.py    # Handles creating and saving snapshots
│   └── website_manager.py  # Manages the list of websites
├── tests/                  # Unit and integration tests
├── .gitignore
├── PROJECT_CHECKLIST.md    # Checklist of project tasks
├── requirements.txt        # Python dependencies
└── README.md               # This file
```

## Setup & Configuration

1.  **Clone the repository (if applicable).**
2.  **Install Python 3.x.**
3.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```
4.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
5.  **Configure the system:**
    - Copy `config/config.yaml` (if a template is provided) or edit it directly.
    - **Important:**
        - Set `webdriver_path` in `config.yaml` if `chromedriver` (or your browser's webdriver) is not in your system PATH. Download the webdriver compatible with your browser version.
        - For email alerts, configure SMTP settings (`notification_email_from`, `notification_email_to`, `smtp_server`, `smtp_port`, `smtp_username`, `smtp_password`, `smtp_use_tls`). For Gmail, you might need to use an "App Password".
        - Adjust `log_file_path`, `website_list_file_path`, `snapshot_directory`, and `check_history_file_path` if needed.
6.  **Add websites to monitor:**
    - You can manually edit `data/websites.json` to add initial sites, or use the functions in `src/website_manager.py` if running parts of the code interactively. An empty list `[]` is a valid starting point for `data/websites.json`. Alternatively, use the CLI `add-site` command (see below).

## Security Considerations

-   **`config.yaml` Permissions:** The `config/config.yaml` file may contain sensitive information, such as SMTP credentials. Ensure that this file has appropriate filesystem permissions to restrict access, especially in a multi-user environment.
-   **Input Handling:** While this is primarily a command-line tool, always be mindful of the source of input data (e.g., URLs in `websites.json`). The system relies on external libraries like `requests` and `selenium` which have their own security considerations when interacting with web content.

## Running the System

There are two main ways to interact with the system:

1.  **Running the Monitoring Scheduler:**
    The scheduler runs in the foreground, continuously monitoring websites according to their schedules.
    To start the scheduler:
    ```bash
    python src/scheduler.py 
    ```
    It will log its activities to the console and to the configured log file. Press `Ctrl+C` to stop it gracefully.

2.  **Using the Web Dashboard (New):**
    A Flask-based web dashboard provides a user interface to view monitored sites, their status, and check history, including visual comparisons.
    To start the dashboard:
    ```bash
    python src/dashboard_app.py
    ```
    By default, it will be accessible at `http://127.0.0.1:5001` (or the port configured in `config.yaml` under `dashboard_port`).
    The dashboard allows you to:
    - View all monitored websites and their current status.
    - Click on a site to see its detailed check history.
    - View HTML and visual snapshots for each check.
    - Compare visual snapshots side-by-side if changes were detected.

3.  **Using the Command Line Interface (CLI):**
    The `main.py` script provides a CLI for managing websites, viewing history, running manual checks, and generating reports.

    **General Usage:**
    ```bash
    python main.py [COMMAND] [OPTIONS]
    ```

    **Available Commands:**

    *   `add-site URL [OPTIONS]`: Adds a new website.
        *   `--name TEXT`: Friendly name for the site.
        *   `--interval INTEGER`: Monitoring interval in hours.
        *   `--active / --inactive`: Set site as active (default) or inactive.
        *   `--tags TEXT`: Comma-separated tags.
        *   Example: `python main.py add-site "http://example.com" --name "Example Site" --interval 12 --tags "official,test"`

    *   `list-sites [OPTIONS]`: Lists all monitored websites.
        *   `--active-only`: Show only active websites.
        *   Example: `python main.py list-sites --active-only`

    *   `remove-site SITE_ID_OR_URL`: Removes a website by its ID or URL.
        *   Example: `python main.py remove-site "http://example.com"`

    *   `update-site SITE_ID_OR_URL [OPTIONS]`: Updates an existing website.
        *   `--url TEXT`: New URL.
        *   `--name TEXT`: New name.
        *   `--interval INTEGER`: New interval.
        *   `--active / --inactive`: New active status.
        *   `--tags TEXT`: New comma-separated tags (replaces existing).
        *   Example: `python main.py update-site "http://example.com" --interval 24 --active`

    *   `get-history SITE_ID_OR_URL [OPTIONS]`: Shows check history for a website.
        *   `--limit INTEGER`: Number of records to show (0 for all, default 10).
        *   Example: `python main.py get-history "http://example.com" --limit 5`

    *   `run-check SITE_ID_OR_URL`: Manually triggers a monitoring check.
        *   Example: `python main.py run-check "http://example.com"`

    *   `generate-report [OPTIONS]`: Generates a report of check history.
        *   `--site-id TEXT`: Report for a specific site ID/URL (default: all sites).
        *   `--format [json|csv]`: Report format (default: json).
        *   `--output-file FILENAME`: Path to save the report (default: print to console).
        *   `--history-limit INTEGER`: Number of recent records per site (0 for all, default all).
        *   Example: `python main.py generate-report --format csv --output-file report.csv --site-id "http://example.com"`

    To see help for any command:
    ```bash
    python main.py [COMMAND] --help
    ```

The main entry point for running the monitoring scheduler is `src/scheduler.py`:

```bash
python src/scheduler.py
```

This will start the scheduler, which will periodically check the websites based on their configured intervals.

## Running Tests

The project includes a suite of unit tests located in the `tests/` directory. To run all tests, use the `run_tests.py` script from the project root:

```bash
python run_tests.py
```

This script will discover and execute all test cases and report the results.

## Key Modules

-   `src/config_loader.py`: Loads system-wide configurations.
-   `src/logger_setup.py`: Initializes logging.
-   `src/dashboard_app.py`: Flask application for the web UI.
-   `src/website_manager.py`: Manages the list of websites to be monitored (CRUD operations on `data/websites.json`).
-   `src/scheduler.py`: Schedules and executes monitoring tasks for websites.
-   `src/content_retriever.py`: Fetches HTML content from URLs.
-   `src/snapshot_tool.py`: Saves HTML content and takes visual screenshots of websites.
-   `src/comparators.py`: Contains various functions to compare old and new versions of website content (text, structure, meta tags, links, images, visual screenshots).
-   `src/history_manager.py`: Logs the results of each check, including paths to snapshots and detected changes.
-   `src/alerter.py`: Sends email notifications when significant changes are detected.
-   `src/report_generator.py`: Generates reports (JSON, CSV) from check history.

## Scalability Notes

- The `check_history.json` file can grow large over time. While the system uses in-memory caching for reads, writing involves rewriting the entire file. For very long-term monitoring or a high volume of checks, consider migrating `check_history.json` to a database solution or an append-friendly file format like JSONL for better write performance and scalability.

## TODO / Future Enhancements

-   Implement a main application script (`main.py` or `app.py`) to tie everything together and provide a clear entry point or CLI. - **DONE (main.py for CLI, scheduler.py for service)**
-   **Comprehensive Unit and Integration Tests:** Add a `tests/` suite.
-   More robust error handling and retry mechanisms (e.g., for network requests).
-   Database backend option for `website_manager` and `history_manager` for better scalability.
-   User Interface (Phase 10 - Optional Dashboard).
-   Advanced semantic content comparison (Task 6.5).
-   Support for `robots.txt` checking.
-   Proxy support for content retrieval.
-   More sophisticated change detection thresholds and customization.
-   Deployment scripts/Docker containerization.

This `README.md` provides a basic guide. Refer to the source code and docstrings for more details. # Deployment Test - Wed, Sep 24, 2025  9:36:31 AM
