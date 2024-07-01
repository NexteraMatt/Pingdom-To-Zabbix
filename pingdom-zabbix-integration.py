import os
import json
import logging
import requests
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# Load environment variables from .env file
load_dotenv()

# Environment variables and validation
class Config:
    def __init__(self):
        self.pingdom_api_key = os.getenv('PINGDOM_API_KEY')
        self.zabbix_api_url = os.getenv('ZABBIX_API_URL')
        self.zabbix_api_user = os.getenv('ZABBIX_API_USER')
        self.zabbix_api_password = os.getenv('ZABBIX_API_PASSWORD')
        self.zabbix_host_group_id = os.getenv('ZABBIX_HOST_GROUP_ID')
        self.zabbix_template_id = os.getenv('ZABBIX_TEMPLATE_ID')
        self.pingdom_api_url = "https://api.pingdom.com/api/3.1/checks"

        required_vars = [
            self.pingdom_api_key, self.zabbix_api_url, self.zabbix_api_user, 
            self.zabbix_api_password, self.zabbix_host_group_id, self.zabbix_template_id
        ]
        if not all(required_vars):
            raise EnvironmentError("Missing one or more required environment variables.")

config = Config()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configure session with retry strategy
def create_session():
    retry_strategy = Retry(
        total=3,
        status_forcelist=[429, 500, 502, 503, 504],
        method_whitelist=["HEAD", "GET", "OPTIONS", "POST"],
        backoff_factor=1
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

session = create_session()

# Cache for host IDs
host_id_cache = {}

def zabbix_login():
    """Log in to the Zabbix API and return the authentication token."""
    payload = {
        "jsonrpc": "2.0",
        "method": "user.login",
        "params": {"user": config.zabbix_api_user, "password": config.zabbix_api_password},
        "id": 1
    }
    headers = {'Content-Type': 'application/json-rpc'}
    response = session.post(config.zabbix_api_url, headers=headers, data=json.dumps(payload))
    response.raise_for_status()
    return response.json()['result']

def get_pingdom_checks():
    """Fetch checks from the Pingdom API."""
    headers = {'Authorization': f'Bearer {config.pingdom_api_key}'}
    response = session.get(config.pingdom_api_url, headers=headers)
    response.raise_for_status()
    return response.json()

def get_zabbix_host_id(auth_token, host_name):
    """Get the Zabbix host ID for the given host name."""
    if host_name in host_id_cache:
        return host_id_cache[host_name]

    payload = {
        "jsonrpc": "2.0",
        "method": "host.get",
        "params": {"filter": {"host": [host_name]}},
        "auth": auth_token,
        "id": 1
    }
    headers = {'Content-Type': 'application/json-rpc'}
    response = session.post(config.zabbix_api_url, headers=headers, data=json.dumps(payload))
    response.raise_for_status()
    result = response.json().get('result', [])
    host_id = result[0]['hostid'] if result else None
    if host_id:
        host_id_cache[host_name] = host_id
    return host_id

def create_zabbix_host(auth_token, host_name):
    """Create a new host in Zabbix."""
    payload = {
        "jsonrpc": "2.0",
        "method": "host.create",
        "params": {
            "host": host_name,
            "interfaces": [{"type": 1, "main": 1, "useip": 1, "ip": "127.0.0.1", "dns": "", "port": "10050"}],
            "groups": [{"groupid": config.zabbix_host_group_id}],
            "templates": [{"templateid": config.zabbix_template_id}]
        },
        "auth": auth_token,
        "id": 1
    }
    headers = {'Content-Type': 'application/json-rpc'}
    response = session.post(config.zabbix_api_url, headers=headers, data=json.dumps(payload))
    response.raise_for_status()
    result = response.json()
    if 'result' in result and 'hostids' in result['result']:
        host_id = result['result']['hostids'][0]
        host_id_cache[host_name] = host_id
        return host_id
    logging.error(f"Error creating Zabbix host {host_name}. Response: {response.text}")
    return None

def create_zabbix_item_batch(auth_token, host_ids, check_names):
    """Create items in Zabbix in batch."""
    items_payload = [
        {
            "name": check_name,
            "key_": f"pingdom.status[{check_name}]",
            "hostid": host_id,
            "type": 2,
            "value_type": 3,
            "delay": "60s",
            "history": "7d",
            "trends": "365d"
        } for host_id, check_name in zip(host_ids, check_names)
    ]

    payload = {
        "jsonrpc": "2.0",
        "method": "item.create",
        "params": items_payload,
        "auth": auth_token,
        "id": 1
    }
    headers = {'Content-Type': 'application/json-rpc'}
    response = session.post(config.zabbix_api_url, headers=headers, data=json.dumps(payload))
    response.raise_for_status()
    return response.json()

def create_zabbix_trigger_batch(auth_token, host_ids, check_names):
    """Create triggers in Zabbix in batch."""
    triggers_payload = [
        {
            "description": f"Pingdom check {check_name} is down",
            "expression": f"{{Pingdom_{check_name}:pingdom.status[{check_name}].last()}}=0",
            "priority": 4,
            "hostid": host_id
        } for host_id, check_name in zip(host_ids, check_names)
    ]

    payload = {
        "jsonrpc": "2.0",
        "method": "trigger.create",
        "params": triggers_payload,
        "auth": auth_token,
        "id": 1
    }
    headers = {'Content-Type': 'application/json-rpc'}
    response = session.post(config.zabbix_api_url, headers=headers, data=json.dumps(payload))
    response.raise_for_status()
    return response.json()

def send_data_to_zabbix_batch(auth_token, host_ids, check_names, statuses):
    """Update items in Zabbix in batch."""
    items_payload = [
        {
            "hostid": host_id,
            "key_": f"pingdom.status[{check_name}]",
            "value_type": 3,
            "value": status
        } for host_id, check_name, status in zip(host_ids, check_names, statuses)
    ]

    payload = {
        "jsonrpc": "2.0",
        "method": "item.update",
        "params": items_payload,
        "auth": auth_token,
        "id": 1
    }
    headers = {'Content-Type': 'application/json-rpc'}
    response = session.post(config.zabbix_api_url, headers=headers, data=json.dumps(payload))
    response.raise_for_status()
    return response.json()

def process_check(auth_token, check):
    """Process a single Pingdom check."""
    check_name = check['name']
    status = 1 if check['status'] == "up" else 0
    host_name = f"Pingdom_{check_name}"
    host_id = get_zabbix_host_id(auth_token, host_name)
    if not host_id:
        logging.info(f"Creating new host: {host_name}")
        host_id = create_zabbix_host(auth_token, host_name)
    return host_id, check_name, status

def main():
    """Main function to orchestrate the data flow between Pingdom and Zabbix."""
    try:
        auth_token = zabbix_login()
        checks = get_pingdom_checks()
        
        host_ids = []
        check_names = []
        statuses = []

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(process_check, auth_token, check) for check in checks['checks']]
            for future in as_completed(futures):
                host_id, check_name, status = future.result()
                host_ids.append(host_id)
                check_names.append(check_name)
                statuses.append(status)
        
        # Create items in batch
        if host_ids and check_names:
            create_zabbix_item_batch(auth_token, host_ids, check_names)
        
        # Create triggers in batch
        if host_ids and check_names:
            create_zabbix_trigger_batch(auth_token, host_ids, check_names)
        
        # Send data to Zabbix in batch
        if host_ids and check_names and statuses:
            send_data_to_zabbix_batch(auth_token, host_ids, check_names, statuses)

    except requests.exceptions.RequestException as e:
        logging.error(f"Request failed: {e}")
    except KeyError as e:
        logging.error(f"Key error: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
