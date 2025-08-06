# KumaReport - Uptime Kuma PDF Reporting Tool

KumaReport is a powerful Python script that connects to your Uptime Kuma instance and generates detailed, professional reports on monitor downtime and performance. It's designed for system administrators, DevOps engineers, and anyone who needs to analyze and share uptime metrics.

The script provides a comprehensive summary of monitor health, including downtime incidents, duration, and ping statistics over various time periods, and can export this data to **PDF**, **CSV**, or **XLSX** formats.

## Features

* **Multiple Export Formats:** Generate reports as a professional **PDF**, a data-rich **CSV**, or a multi-sheet **XLSX** file.
* **In-Depth Downtime Analysis:** Automatically calculates the number of downtime incidents and their duration.
* **Comprehensive Summary Table:** For each monitor, view key metrics over the last day, week, and month, including:
    * Total downtime incidents.
    * Average downtime duration.
    * Average and maximum ping response times.
    * Overall downtime percentage.
* **Detailed Event Log:** A chronological log of every downtime incident, showing when it started and how long it lasted.
* **Smart Configuration:** On first run, it creates a `config.yml` to securely store your server URL, username, timezone, and preferred export format.
* **Timezone Aware:** All timestamps in the report are converted to your specified timezone for accurate, localized reporting.
* **Customizable Branding:** Easily add your own company logo to PDF report headers by placing a `logo.png` file in the script's directory.

## Installation

### Prerequisites

* Python 3.7+

### Dependencies

Install the required Python libraries using pip. 
```
pip install uptime-kuma-api fpdf2 PyYAML pytz pandas openpyxl
```

## Configuration

1.  **`config.yml` (Automatic)**
    * This file is created automatically the first time you run the script successfully. It stores your Uptime Kuma URL, username, timezone, and default export format.
    * You do not need to create this file manually.
2.  **`logo.png` (Optional)**
    * To add a custom logo to your PDF reports, place a PNG file named `logo.png` in the same directory as the `kuma_report.py` script.
    * The script will automatically detect and embed it in the header of the PDF.

## Usage

Execute the script from your terminal:
```
python kumareport.py
```

### First-Time Use

The first time you run the script, it will prompt you for the following information:

1.  Your Uptime Kuma URL (e.g., `http://127.0.0.1:3001`)
2.  Your Uptime Kuma username
3.  Your timezone (e.g., `America/New_York`, `Europe/London`). Defaults to `UTC` if left blank.
4.  Your preferred export format (`pdf`, `csv`, or `xlsx`).
5.  Your password (will not be displayed as you type).

After a successful connection, it will save your settings to `config.yml`.

### Subsequent Use

On all subsequent runs, the script will load the saved settings and will only prompt you for your password.

After authenticating, you will be presented with a list of your available monitors. You can select one or more monitors by entering their corresponding numbers (e.g., `1, 3, 5`) or type `all` to generate a report for every monitor.

The script will then process the data and save a timestamped file (e.g., `kumareport_08_05_25_21_30_00.pdf`) in your chosen format in the same directory.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
