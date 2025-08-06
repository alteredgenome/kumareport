import getpass
import datetime
import os
import yaml
import pytz
import pandas as pd
from uptime_kuma_api import UptimeKumaApi, UptimeKumaException
from fpdf import FPDF
from fpdf.enums import XPos, YPos

# --- Script Information ---
__version__ = "1.7.0"
__developer__ = "alteredgenome"
CONFIG_FILE = "config.yml"
LOGO_FILE = "logo.png"

# --- ASCII Art Banner ---
def print_banner():
    """Prints a startup banner with ASCII art and script information."""
    # Using an 'r' before the f-string (rf"...") treats backslashes as literal characters
    banner = rf"""
                               __                       _
  /\_/\_   _ _ __ ___   __ _  /__\____ _ __   ___  _ __| |_
 / //_/ | | | '_ ` _ \_/ _` |/ \/// _ \_'_ \_ / _ \| '__| __|
/ __ \| |_| | | | | | | (_| / _  \_ __/ |_)  | (_) | |  | |_
\/  \/ \__,_|_| |_| |_|\__,_\/ \_/\___| .__/  \___/|_|   \__|
                                      | |

    Version: {__version__}
    (c) 2025 {__developer__}
    ====================================================
"""
    print(banner)

# --- Configuration Management ---

def load_config():
    """Loads configuration from config.yml if it exists and is valid."""
    if not os.path.exists(CONFIG_FILE):
        return None, None, None, None
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = yaml.safe_load(f)
            # Basic validation
            if config and 'url' in config and 'username' in config:
                url = config['url']
                username = config['username']
                timezone = config.get('timezone', 'UTC')
                export_format = config.get('export_format', 'pdf')
                print(f"Loaded configuration from {CONFIG_FILE}.")
                return url, username, timezone, export_format
            else:
                print(f"Warning: {CONFIG_FILE} is malformed. Will prompt for new values.")
                return None, None, None, None
    except (yaml.YAMLError, IOError) as e:
        print(f"Warning: Could not read {CONFIG_FILE}. Error: {e}. Will prompt for new values.")
        return None, None, None, None

def save_config(url, username, timezone, export_format):
    """Saves the server URL, username, timezone, and export format to config.yml."""
    config_data = {
        'url': url,
        'username': username,
        'timezone': timezone,
        'export_format': export_format
    }
    try:
        with open(CONFIG_FILE, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False)
        print(f"Configuration saved to {CONFIG_FILE} for future use.")
    except IOError as e:
        print(f"Error: Could not save configuration to {CONFIG_FILE}. Error: {e}")

def handle_credentials():
    """Loads credentials from config or prompts the user if necessary."""
    url, username, timezone, export_format = load_config()
    save_needed = not all([url, username, timezone, export_format])

    if not url:
        url = input("Enter your Uptime Kuma URL (e.g., http://localhost:3001): ")
    if not username:
        username = input("Enter your Uptime Kuma username: ")
    if not timezone:
        timezone = input("Enter your timezone (e.g., America/New_York, default: UTC): ")
        if not timezone:
            timezone = 'UTC'
    if not export_format:
        while True:
            export_format = input("Choose export format (pdf, csv, xlsx): ").lower()
            if export_format in ['pdf', 'csv', 'xlsx']:
                break
            print("Invalid format. Please choose 'pdf', 'csv', or 'xlsx'.")

    password = getpass.getpass(f"Enter password for '{username}': ")
    return url, username, password, timezone, export_format, save_needed

# --- Helper Functions ---

def _format_timedelta(td):
    """Formats a timedelta object into a human-readable string."""
    if td is None:
        return "N/A"
    days, remainder = divmod(td.total_seconds(), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts = []
    if days > 0:
        parts.append(f"{int(days)}d")
    if hours > 0:
        parts.append(f"{int(hours)}h")
    if minutes > 0:
        parts.append(f"{int(minutes)}m")
    if seconds > 0 or not parts:
        parts.append(f"{int(seconds)}s")

    return " ".join(parts)

# --- Data Processing ---

def analyze_heartbeats(heartbeats, user_timezone_str):
    """
    Analyzes heartbeats to calculate downtime incidents and collect ping data.
    """
    try:
        user_tz = pytz.timezone(user_timezone_str)
    except pytz.UnknownTimeZoneError:
        print(f"Warning: Unknown timezone '{user_timezone_str}'. Defaulting to UTC.")
        user_tz = pytz.utc

    def to_datetime(time_val):
        if isinstance(time_val, str):
            try:
                naive_dt = datetime.datetime.strptime(time_val.split('.')[0], '%Y-%m-%d %H:%M:%S')
                utc_dt = pytz.utc.localize(naive_dt)
                return utc_dt.astimezone(user_tz)
            except ValueError:
                return None
        elif isinstance(time_val, (int, float)):
            utc_dt = datetime.datetime.fromtimestamp(float(time_val), tz=pytz.utc)
            return utc_dt.astimezone(user_tz)
        return None

    processed_beats = []
    ping_data = []
    for beat in heartbeats:
        dt = to_datetime(beat.get('time'))
        if dt:
            processed_beats.append({'datetime': dt, 'status': beat['status']})
            if beat.get('ping') is not None:
                ping_data.append({'datetime': dt, 'ping': beat['ping']})

    beats = sorted(processed_beats, key=lambda x: x['datetime'])

    incidents = []
    current_downtime_start_dt = None

    for beat in beats:
        is_down = beat['status'] == 0
        if is_down and current_downtime_start_dt is None:
            current_downtime_start_dt = beat['datetime']
        elif not is_down and current_downtime_start_dt is not None:
            incidents.append({
                "start": current_downtime_start_dt,
                "duration": beat['datetime'] - current_downtime_start_dt
            })
            current_downtime_start_dt = None

    if current_downtime_start_dt is not None:
        now_aware = datetime.datetime.now(user_tz)
        incidents.append({"start": current_downtime_start_dt, "duration": now_aware - current_downtime_start_dt, "ongoing": True})

    return {"downtime_incidents": incidents, "ping_data": ping_data}

def calculate_summary_stats(analysis_results, user_timezone_str):
    """Calculates summary statistics for daily, weekly, and monthly periods."""
    incidents = analysis_results['downtime_incidents']
    ping_data = analysis_results['ping_data']

    try:
        user_tz = pytz.timezone(user_timezone_str)
    except pytz.UnknownTimeZoneError:
        user_tz = pytz.utc

    now = datetime.datetime.now(user_tz)
    periods = {
        "Daily": datetime.timedelta(days=1),
        "Weekly": datetime.timedelta(days=7),
        "Monthly": datetime.timedelta(days=30)
    }

    summary = {}
    for name, delta in periods.items():
        period_start = now - delta

        # Downtime stats
        period_incidents = [inc for inc in incidents if inc['start'] >= period_start]
        count = len(period_incidents)
        total_duration = sum([inc['duration'] for inc in period_incidents], datetime.timedelta())
        avg_duration = total_duration / count if count > 0 else datetime.timedelta(0)
        percentage = (total_duration.total_seconds() / delta.total_seconds()) * 100 if delta.total_seconds() > 0 else 0

        # Ping stats
        period_pings = [p['ping'] for p in ping_data if p['datetime'] >= period_start]
        avg_ping = sum(period_pings) / len(period_pings) if period_pings else None
        max_ping = max(period_pings) if period_pings else None

        summary[name] = {
            "count": count,
            "avg_duration": avg_duration,
            "percentage": percentage,
            "avg_ping": avg_ping,
            "max_ping": max_ping
        }

    return summary

# --- Report Generation ---

def generate_pdf_report(username, selected_monitors, timezone, all_monitor_data):
    """Generates the full report in PDF format."""
    pdf = FPDF()
    pdf.add_page()

    generate_pdf_header(pdf, username, selected_monitors, timezone)

    for i, data in enumerate(all_monitor_data):
        generate_summary_pdf_section(pdf, data['monitor_name'], data['summary_stats'])
        generate_details_pdf_section(pdf, data['downtime_incidents'])

        if i < len(all_monitor_data) - 1:
            pdf.add_page()

    filename = datetime.datetime.now().strftime("kumareport_%m_%d_%y_%H_%M_%S.pdf")
    pdf.output(filename)
    return filename

def generate_csv_report(all_monitor_data):
    """Generates a CSV report from the analyzed data."""
    all_data_rows = []
    for data in all_monitor_data:
        for incident in reversed(data['downtime_incidents']):
            all_data_rows.append({
                "Monitor Name": data['monitor_name'],
                "Outage Start": incident['start'].strftime('%Y-%m-%d %H:%M:%S %Z'),
                "Duration (seconds)": incident['duration'].total_seconds(),
                "Ongoing": incident.get("ongoing", False)
            })

    df = pd.DataFrame(all_data_rows)
    filename = datetime.datetime.now().strftime("kumareport_%m_%d_%y_%H_%M_%S.csv")
    df.to_csv(filename, index=False)
    return filename

def generate_xlsx_report(all_monitor_data):
    """Generates an XLSX report with separate sheets for summary and details."""
    filename = datetime.datetime.now().strftime("kumareport_%m_%d_%y_%H_%M_%S.xlsx")
    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        # Summary Sheet
        summary_rows = []
        for data in all_monitor_data:
            for period, stats in data['summary_stats'].items():
                summary_rows.append({
                    "Monitor Name": data['monitor_name'],
                    "Period": period,
                    "Downtime Incidents": stats['count'],
                    "Avg. Downtime (s)": stats['avg_duration'].total_seconds(),
                    "Avg. Ping (ms)": stats['avg_ping'],
                    "Max. Ping (ms)": stats['max_ping'],
                    "Downtime %": stats['percentage']
                })
        summary_df = pd.DataFrame(summary_rows)
        summary_df.to_excel(writer, sheet_name='Summary', index=False)

        # Details Sheet
        details_rows = []
        for data in all_monitor_data:
            for incident in reversed(data['downtime_incidents']):
                details_rows.append({
                    "Monitor Name": data['monitor_name'],
                    "Outage Start": incident['start'].strftime('%Y-%m-%d %H:%M:%S %Z'),
                    "Duration (s)": incident['duration'].total_seconds(),
                    "Ongoing": incident.get("ongoing", False)
                })
        details_df = pd.DataFrame(details_rows)
        details_df.to_excel(writer, sheet_name='Downtime Log', index=False)

    return filename

def generate_pdf_header(pdf, username, selected_monitors, timezone_str):
    """Creates the header section of the PDF report."""
    if os.path.exists(LOGO_FILE):
        pdf.image(LOGO_FILE, x=10, y=8, w=25)

    pdf.set_font("Helvetica", 'B', 20)
    pdf.set_xy(40, 15)
    pdf.cell(0, 10, "Historical Status Monitor Report", align='L')

    pdf.set_font("Helvetica", '', 10)
    now_aware = datetime.datetime.now(pytz.timezone(timezone_str))
    generated_str = now_aware.strftime('%m/%d/%Y @ %H:%M:%S')
    pdf.set_xy(40, 25)
    pdf.cell(0, 8, f"Generated: {generated_str}")

    pdf.set_xy(40, 30)
    pdf.cell(0, 8, f"Prepared by: {username}")

    pdf.set_xy(10, 40)
    monitor_names = ", ".join([m['name'] for m in selected_monitors])
    pdf.multi_cell(0, 5, f"Included Monitors: {monitor_names}")

    pdf.ln(10)

def generate_summary_pdf_section(pdf, monitor_name, stats):
    """Adds the summary statistics section to the PDF for a monitor."""
    pdf.set_font("Helvetica", 'B', 12)
    pdf.cell(0, 10, f"Summary for: {monitor_name}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("Helvetica", 'B', 10)
    pdf.cell(30, 8, "Period", border=1)
    pdf.cell(35, 8, "Downtime Incidents", border=1)
    pdf.cell(35, 8, "Avg. Downtime", border=1)
    pdf.cell(30, 8, "Avg. Ping", border=1)
    pdf.cell(30, 8, "Max. Ping", border=1)
    pdf.cell(30, 8, "Downtime %", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("Helvetica", '', 10)
    for period, data in stats.items():
        avg_ping_str = f"{int(data['avg_ping'])} ms" if data['avg_ping'] is not None else "N/A"
        max_ping_str = f"{int(data['max_ping'])} ms" if data['max_ping'] is not None else "N/A"

        pdf.cell(30, 8, period, border=1)
        pdf.cell(35, 8, str(data['count']), border=1)
        pdf.cell(35, 8, _format_timedelta(data['avg_duration']), border=1)
        pdf.cell(30, 8, avg_ping_str, border=1)
        pdf.cell(30, 8, max_ping_str, border=1)
        pdf.cell(30, 8, f"{data['percentage']:.2f}%", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.ln(10)

def generate_details_pdf_section(pdf, incidents):
    """Adds the detailed list of downtime incidents to the PDF."""
    pdf.set_font("Helvetica", 'B', 12)
    pdf.cell(0, 10, "Downtime Event Log (Most Recent First)", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    if not incidents:
        pdf.set_font("Helvetica", '', 10)
        pdf.cell(0, 8, "No downtime incidents recorded in the analyzed period.", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        return

    for incident in reversed(incidents):
        start_str = incident['start'].strftime('%Y-%m-%d %H:%M:%S %Z')
        duration_str = _format_timedelta(incident['duration'])

        if incident.get("ongoing", False):
            duration_str += " (Ongoing)"

        pdf.set_font("Helvetica", 'B', 10)
        pdf.cell(30, 8, "Outage Start:")
        pdf.set_font("Helvetica", '', 10)
        pdf.cell(0, 8, start_str, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_font("Helvetica", 'B', 10)
        pdf.cell(30, 8, "Duration:")
        pdf.set_font("Helvetica", '', 10)
        pdf.cell(0, 8, duration_str, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(4)

# --- Main Application Logic ---

def select_monitors(monitors):
    """Displays a list of monitors and prompts the user to select one or more."""
    print("\nAvailable Monitors:")
    for i, monitor in enumerate(monitors):
        print(f"  [{i + 1}] {monitor['name']}")

    while True:
        try:
            selection = input("\nEnter the numbers of the monitors for the report (e.g., 1, 3, 4), or 'all': ")
            if selection.lower() == 'all':
                return monitors
            selected_indices = [int(s.strip()) - 1 for s in selection.split(',')]
            if all(0 <= i < len(monitors) for i in selected_indices):
                return [monitors[i] for i in selected_indices]
            else:
                print("Error: Invalid selection. Please try again.")
        except (ValueError, IndexError):
            print("Error: Invalid input. Please enter numbers separated by commas.")

def main():
    """Main function to run the report generation script."""
    print_banner()
    url, username, password, timezone, export_format, save_config_needed = handle_credentials()

    try:
        with UptimeKumaApi(url) as api:
            api.login(username, password)
            print("\nSuccessfully connected to Uptime Kuma!")

            if save_config_needed:
                save_config(url, username, timezone, export_format)

            monitors = api.get_monitors()
            if not monitors:
                print("No monitors found.")
                return

            selected_monitors = select_monitors(monitors)
            if not selected_monitors:
                print("No monitors selected. Exiting.")
                return

            print("\nAnalyzing data and generating report...")
            all_monitor_data = []
            for monitor in selected_monitors:
                monitor_id = monitor['id']
                monitor_name = monitor['name']
                print(f"  - Processing: {monitor_name}")

                heartbeats = api.get_monitor_beats(monitor_id, 10000)
                analysis_results = analyze_heartbeats(heartbeats, timezone)
                summary_stats = calculate_summary_stats(analysis_results, timezone)

                all_monitor_data.append({
                    "monitor_name": monitor_name,
                    "summary_stats": summary_stats,
                    "downtime_incidents": analysis_results['downtime_incidents']
                })

            # Generate the report in the chosen format
            if export_format == 'pdf':
                filename = generate_pdf_report(username, selected_monitors, timezone, all_monitor_data)
            elif export_format == 'csv':
                filename = generate_csv_report(all_monitor_data)
            elif export_format == 'xlsx':
                filename = generate_xlsx_report(all_monitor_data)

            print(f"\nReport successfully generated: {filename}")

    except UptimeKumaException as e:
        print(f"\nError connecting to Uptime Kuma: {e}")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
