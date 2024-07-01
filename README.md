# Pingdom-Zabbix Integration Script

This script integrates Pingdom monitoring with Zabbix for automated host creation, item monitoring, trigger creation, and status updates. It fetches Pingdom checks, creates corresponding hosts in Zabbix if necessary, and synchronizes their status periodically.

## Table of Contents

1. [Script Details](#script-details)
2. [Prerequisites](#prerequisites)
3. [Setup](#setup)
4. [Configuration](#configuration)
5. [Usage](#usage)
6. [Logging](#logging)
7. [Error Handling](#error-handling)
8. [Cronjob Setup](#cronjob-setup)
9. [License](#license)

## Script Details

### Functionality

The script automates the integration between Pingdom and Zabbix for monitoring purposes. It fetches Pingdom checks using the Pingdom API, creates corresponding hosts in Zabbix if they don't exist, sets up monitoring items and triggers, and updates Zabbix with the latest status from Pingdom checks.

### Key Features

- **Pingdom Integration**: Fetches Pingdom checks using the Pingdom API.
- **Zabbix Host Management**: Creates Zabbix hosts dynamically based on Pingdom checks.
- **Item and Trigger Creation**: Sets up Zabbix items and triggers to monitor Pingdom check statuses.
- **Status Synchronization**: Updates Zabbix with the latest status information retrieved from Pingdom.

## Prerequisites

Before running the script, ensure you have the following:

- **Python 3.7+**: Installed on your system. [Download Python](https://www.python.org/downloads/)
- **Pingdom API Credentials**:
  - API key (`PINGDOM_API_KEY`).
- **Zabbix API Credentials**:
  - API URL (`ZABBIX_API_URL`).
  - Username (`ZABBIX_API_USER`).
  - Password (`ZABBIX_API_PASSWORD`).
- **Zabbix Configuration**:
  - Host group ID (`ZABBIX_HOST_GROUP_ID`): ID of the host group in Zabbix where hosts will be created.
  - Template ID (`ZABBIX_TEMPLATE_ID`): ID of the template in Zabbix to link with the created hosts.

Environment variables should be set up in a `.env` file in the root directory of the script with the following format:

```env
PINGDOM_API_KEY=your_pingdom_api_key
ZABBIX_API_URL=your_zabbix_api_url
ZABBIX_API_USER=your_zabbix_api_user
ZABBIX_API_PASSWORD=your_zabbix_api_password
ZABBIX_HOST_GROUP_ID=your_zabbix_host_group_id
ZABBIX_TEMPLATE_ID=your_zabbix_template_id
```

- **PINGDOM_API_KEY**: API key for accessing Pingdom API (e.g., `abcdef123456`).
- **ZABBIX_API_URL**: URL of the Zabbix API (e.g., `https://zabbix.example.com/api_jsonrpc.php`).
- **ZABBIX_API_USER**: Username for Zabbix API authentication (e.g., `admin`).
- **ZABBIX_API_PASSWORD**: Password for Zabbix API authentication (e.g., `mypassword`).
- **ZABBIX_HOST_GROUP_ID**: ID of the Zabbix host group to place new hosts (e.g., `1234`).
- **ZABBIX_TEMPLATE_ID**: ID of the Zabbix template to apply to new hosts (e.g., `5678`).

## Setup

1. **Clone the repository**:

```sh
git clone https://github.com/MattTHG/pingdom-to-zabbix.git
cd pingdom-to-zabbix
```

2. **Install dependencies**:

```sh
pip install -r requirements.txt
```

3. **Create a `.env` file** in the root directory and add your environment variables as mentioned in the Prerequisites section.

## Configuration

Ensure the `.env` file contains valid credentials and IDs required for accessing Pingdom and Zabbix APIs.

## Usage

To run the script, use Python 3.7+:

```sh
python script_name.py
```

The script will continuously fetch Pingdom checks, create Zabbix hosts and items if necessary, and update Zabbix with the latest statuses.

## Logging

- **INFO**: Detailed execution steps, successful operations.
- **WARNING**: Retries during HTTP requests.
- **ERROR**: Critical errors and exceptions.

Logs are printed to the console. Redirect or append logs to a file for long-term storage.

To append logs to a file, you can run the script with output redirection:

```sh
python3 pingdom-zabbix-integration.py >> python3 /path/to/logfile.log 2>&1
```

## Error Handling

The script handles various exceptions (e.g., HTTP errors, API request failures) and logs detailed error messages for troubleshooting.

## Cronjob Setup

To automate script execution, set up a cronjob:

1. Edit your crontab:

```sh
crontab -e
```

2. Add a cronjob to run the script at your desired interval (e.g., every minute):

```sh
* * * * * /usr/bin/python3 /path/to/pingdom-zabbix-integration.py >> /path/to/logfile.log 2>&1
```

This example runs the script every hour (`* * * * *`) and appends both stdout and stderr to `script_logs.log`.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.

---

### Notes:

- Replace `<placeholders>` with actual values relevant to your environment.
- Ensure all dependencies are installed from `requirements.txt` before running the script.
- Adjust the sleep interval (`await asyncio.sleep(60)`) in the `main_async()` function as per your monitoring requirements.
