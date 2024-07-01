# Pingdom to Zabbix Integration Script

## Overview

This script automates the integration of Pingdom checks into a Zabbix monitoring environment. It fetches the current status of Pingdom checks and ensures that corresponding hosts, items, and triggers are created and updated in Zabbix, providing centralized monitoring through Zabbix.

## Optimization Update

- Optimized script to efficiently process Pingdom checks and update Zabbix monitoring every minute.
- Implemented asynchronous processing and optimized API calls for improved performance.

## Features

- **Automated Integration**: Automatically integrates Pingdom checks with Zabbix.
- **Batch Processing**: Efficiently processes checks in batches.
- **Concurrent Execution**: Utilizes concurrent processing to handle multiple checks efficiently.
- **Robust Error Handling**: Includes comprehensive error handling and logging.
- **Centralized Monitoring**: Allows centralized monitoring of Pingdom checks within Zabbix.

## Prerequisites

- Python 3.x
- Required Python packages: \`requests\`, \`python-dotenv\`
- Pingdom API Key
- Zabbix API credentials and access

## Setup

### Clone the Repository

```sh
git clone https://github.com/MattTHG/pingdom-to-zabbix.git
cd pingdom-to-zabbix
```

### Install Dependencies

```sh
pip install -r requirements.txt
```

### Configure Environment Variables

Create a `.env` file in the project directory and add the following environment variables:

```env
PINGDOM_API_KEY=your_pingdom_api_key
ZABBIX_API_URL=your_zabbix_api_url
ZABBIX_API_USER=your_zabbix_api_user
ZABBIX_API_PASSWORD=your_zabbix_api_password
ZABBIX_HOST_GROUP_ID=your_zabbix_host_group_id
ZABBIX_TEMPLATE_ID=your_zabbix_template_id
```

### Running the Script

To run the script manually:

```sh
python3 pingdom-zabbix-integration.py
```

### Setting Up a Cron Job

To run the script periodically, set up a cron job:

```sh
crontab -e
```

Add the following line to run the script every hour:

```cron
0 * * * * /usr/bin/python3 /path/to/pingdom-zabbix-integration.py >> /path/to/logfile.log 2>&1
```

## Script Details

### Main Functions

- `zabbix_login()`: Authenticates with the Zabbix API and retrieves an auth token.
- `get_pingdom_checks()`: Fetches the list of checks from Pingdom.
- `get_zabbix_host_id()`: Retrieves the host ID from Zabbix based on the host name.
- `create_zabbix_host()`: Creates a new host in Zabbix.
- `create_zabbix_item_batch()`: Creates items in Zabbix for each check.
- `create_zabbix_trigger_batch()`: Creates triggers in Zabbix for each check.
- `send_data_to_zabbix_batch()`: Updates the status of each check in Zabbix.
- `process_check()`: Processes each Pingdom check to ensure it is represented in Zabbix.
- `main()`: Orchestrates the overall workflow, from authentication to processing checks and updating Zabbix.

## Error Handling and Logging

The script includes comprehensive error handling and logging. Logs are saved to a file specified in the cron job configuration for easy monitoring and troubleshooting.

## Zabbix Compatibility

This script has been tested and confirmed to work with the following versions of Zabbix:

- Zabbix 4.0 and later versions

If you encounter any issues with other versions of Zabbix, please [open an issue](https://github.com/MattTHG/Pingdom-To-Zabbix/issues) to report the problem or contribute a fix.


## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any improvements or bug fixes.

## Acknowledgements

Special thanks to the developers of the \`requests\` and \`python-dotenv\` packages for their excellent libraries.

## Contact

For any questions or support, please open an issue on GitHub or contact matt.hodges@thg.com.
