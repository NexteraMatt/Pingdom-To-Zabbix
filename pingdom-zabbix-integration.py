import asyncio
import aiohttp
import json
import os
import logging
import re
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# Load environment variables from .env file
load_dotenv()

# Environment variables
pingdom_api_key = os.getenv('PINGDOM_API_KEY')
zabbix_api_url = os.getenv('ZABBIX_API_URL')
zabbix_api_user = os.getenv('ZABBIX_API_USER')
zabbix_api_password = os.getenv('ZABBIX_API_PASSWORD')
zabbix_host_group_id = os.getenv('ZABBIX_HOST_GROUP_ID')
zabbix_template_id = os.getenv('ZABBIX_TEMPLATE_ID')

pingdom_api_url = "https://api.pingdom.com/api/3.1/checks"

# Validate environment variables
required_vars = [
    pingdom_api_key, zabbix_api_url, zabbix_api_user, 
    zabbix_api_password, zabbix_host_group_id, zabbix_template_id
]
if not all(required_vars):
    raise EnvironmentError("Missing one or more required environment variables.")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configure retry strategy for requests
retry_strategy = Retry(
    total=3,
    status_forcelist=[429, 500, 502, 503, 504],
    method_whitelist=["HEAD", "GET", "OPTIONS", "POST"],
    backoff_factor=1
)
adapter = HTTPAdapter(max_retries=retry_strategy)
http = aiohttp.ClientSession()

# Cache for host IDs
host_id_cache = {}

def sanitize_host_name(host_name):
    """Sanitize host names to ensure they are valid for Zabbix."""
    return re.sub(r'[^a-zA-Z0-9_]', '_', host_name)

async def fetch_with_retry(session, url, method='GET', headers=None, payload=None):
    """Make an HTTP request with retry mechanism."""
    backoff_factor = retry_strategy.backoff_factor
    for attempt in range(retry_strategy.total):
        try:
            async with session.request(method, url, headers=headers, json=payload) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientResponseError as e:
            if e.status not in retry_strategy.status_forcelist:
                raise
            logging.warning(f"Retrying {method} request to {url} (attempt {attempt + 1}/{retry_strategy.total})...")
            await asyncio.sleep(backoff_factor * (2 ** attempt))
    raise aiohttp.ClientResponseError(f"Max retries exceeded for {method} request to {url}")

async def zabbix_login(session):
    """Authenticate with Zabbix API and return auth token."""
    payload = {
        "jsonrpc": "2.0",
        "method": "user.login",
        "params": {"user": zabbix_api_user, "password": zabbix_api_password},
        "id": 1
    }
    headers = {'Content-Type': 'application/json-rpc'}
    response_data = await fetch_with_retry(session, zabbix_api_url, method='POST', headers=headers, payload=payload)
    return response_data['result']

async def get_pingdom_checks(session):
    """Fetch Pingdom checks using the Pingdom API."""
    headers = {'Authorization': f'Bearer {pingdom_api_key}'}
    return await fetch_with_retry(session, pingdom_api_url, headers=headers)

async def get_zabbix_host_id(session, auth_token, host_name):
    """Retrieve Zabbix host ID based on host name."""
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
    response_data = await fetch_with_retry(session, zabbix_api_url, method='POST', headers=headers, payload=payload)
    host_id = response_data['result'][0]['hostid'] if response_data['result'] else None
    if host_id:
        host_id_cache[host_name] = host_id
    return host_id

async def create_zabbix_host(session, auth_token, host_name):
    """Create a Zabbix host if it does not already exist."""
    sanitized_host_name = sanitize_host_name(host_name)
    if await get_zabbix_host_id(session, auth_token, sanitized_host_name):
        logging.info(f"Host {sanitized_host_name} already exists in Zabbix. Skipping creation.")
        return host_id_cache[sanitized_host_name]

    payload = {
        "jsonrpc": "2.0",
        "method": "host.create",
        "params": {
            "host": sanitized_host_name,
            "interfaces": [{"type": 1, "main": 1, "useip": 1, "ip": "127.0.0.1", "dns": "", "port": "10050"}],
            "groups": [{"groupid": zabbix_host_group_id}],
            "templates": [{"templateid": zabbix_template_id}]
        },
        "auth": auth_token,
        "id": 1
    }
    headers = {'Content-Type': 'application/json-rpc'}
    response_data = await fetch_with_retry(session, zabbix_api_url, method='POST', headers=headers, payload=payload)
    try:
        host_id = response_data['result']['hostids'][0]
        host_id_cache[sanitized_host_name] = host_id
        logging.info(f"Successfully created host {sanitized_host_name} with ID {host_id}")
        return host_id
    except (KeyError, IndexError) as e:
        logging.error(f"Error creating Zabbix host {sanitized_host_name}. Response: {response_data}")
        return None

async def create_zabbix_item_batch(session, auth_token, host_ids, check_names):
    """Create Zabbix items in batch for monitoring Pingdom checks."""
    items_payload = []
    for host_id, check_name in zip(host_ids, check_names):
        item_key = f"pingdom.status[{check_name}]"
        item_payload = {
            "name": check_name,
            "key_": item_key,
            "hostid": host_id,
            "type": 2,
            "value_type": 3,
            "delay": "60s",
            "history": "7d",
            "trends": "365d"
        }
        items_payload.append(item_payload)

    payload = {
        "jsonrpc": "2.0",
        "method": "item.create",
        "params": items_payload,
        "auth": auth_token,
        "id": 1
    }
    headers = {'Content-Type': 'application/json-rpc'}
    response_data = await fetch_with_retry(session, zabbix_api_url, method='POST', headers=headers, payload=payload)
    try:
        logging.info(f"Items created successfully: {response_data}")
        return response_data
    except KeyError as e:
        logging.error(f"Error creating Zabbix items: {e}. Response: {response_data}")
        return None

async def create_zabbix_trigger_batch(session, auth_token, host_ids, check_names):
    """Create Zabbix triggers in batch based on Pingdom checks."""
    triggers_payload = []
    for host_id, check_name in zip(host_ids, check_names):
        item_key = f"pingdom.status[{check_name}]"
        trigger_expression = f"{{Pingdom_{check_name}:{item_key}.last()}}=0"
        trigger_payload = {
            "description": f"Pingdom check {check_name} is down",
            "expression": trigger_expression,
            "priority": 4,
            "hostid": host_id
        }
        triggers_payload.append(trigger_payload)

    payload = {
        "jsonrpc": "2.0",
        "method": "trigger.create",
        "params": triggers_payload,
        "auth": auth_token,
        "id": 1
    }
    headers = {'Content-Type': 'application/json-rpc'}
    response_data = await fetch_with_retry(session, zabbix_api_url, method='POST', headers=headers, payload=payload)
    try:
        logging.info(f"Triggers created successfully: {response_data}")
        return response_data
    except KeyError as e:
        logging.error(f"Error creating Zabbix triggers: {e}. Response: {response_data}")
        return None

async def send_data_to_zabbix_batch(session, auth_token, host_ids, check_names, statuses):
    """Send status data to Zabbix for monitoring."""
    items_payload = []
    for host_id, check_name, status in zip(host_ids, check_names, statuses):
        item_key = f"pingdom.status[{check_name}]"
        item_payload = {
            "hostid": host_id,
            "key_": item_key,
            "value_type": 3,
            "value": status
        }
        items_payload.append(item_payload)

    payload = {
        "jsonrpc": "2.0",
        "method": "item.update",
        "params": items_payload,
        "auth": auth_token,
        "id": 1
    }
    headers = {'Content-Type': 'application/json-rpc'}
    response_data = await fetch_with_retry(session, zabbix_api_url, method='POST', headers=headers, payload=payload)
    try:
        logging.info(f"Data sent to Zabbix successfully: {response_data}")
        return response_data
    except KeyError as e:
        logging.error(f"Error sending data to Zabbix: {e}. Response: {response_data}")
        return None

async def process_check(session, auth_token, check):
    """Process each Pingdom check."""
    check_name = check['name']
    status = 1 if check['status'] == "up" else 0
    host_name = f"Pingdom_{check_name}"
    sanitized_host_name = sanitize_host_name(host_name)

    logging.info(f"Processing check: {check_name}")
    host_id = await get_zabbix_host_id(session, auth_token, sanitized_host_name)
    if not host_id:
        logging.info(f"Host {sanitized_host_name} not found in Zabbix. Creating...")
        host_id = await create_zabbix_host(session, auth_token, sanitized_host_name)
        if not host_id:
            logging.error(f"Failed to create host {sanitized_host_name} in Zabbix. Skipping this check.")
            return None, None, None
        logging.info(f"Host {sanitized_host_name} created with ID {host_id}")
    
    logging.info(f"Processing check {check_name} for host {sanitized_host_name} with status {status}")
    return host_id, check_name, status

async def main_async():
    """Main asynchronous function."""
    try:
        async with aiohttp.ClientSession() as session:
            auth_token = await zabbix_login(session)
            logging.info("Logged into Zabbix successfully.")
            while True:
                pingdom_data = await get_pingdom_checks(session)
                logging.info(f"Retrieved Pingdom checks: {pingdom_data}")

                host_ids = []
                check_names = []
                statuses = []

                tasks = [process_check(session, auth_token, check) for check in pingdom_data['checks']]
                results = await asyncio.gather(*tasks)

                for result in results:
                    if result:
                        host_id, check_name, status = result
                        if host_id and check_name and status is not None:
                            host_ids.append(host_id)
                            check_names.append(check_name)
                            statuses.append(status)
                
                if host_ids and check_names and statuses:
                    logging.info("Creating items in Zabbix...")
                    await create_zabbix_item_batch(session, auth_token, host_ids, check_names)
                    logging.info("Creating triggers in Zabbix...")
                    await create_zabbix_trigger_batch(session, auth_token, host_ids, check_names)
                    logging.info("Sending data to Zabbix...")
                    await send_data_to_zabbix_batch(session, auth_token, host_ids, check_names, statuses)

                await asyncio.sleep(60)  # Adjust sleep time as per your monitoring interval

    except aiohttp.ClientError as e:
        logging.error(f"Request failed: {e}")
    except KeyError as e:
        logging.error(f"Key error: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(main_async())
