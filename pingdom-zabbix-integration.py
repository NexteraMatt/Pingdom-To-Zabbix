import requests
import json
import time
import os
import logging
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed

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

def zabbix_login():
    payload = {
        "jsonrpc": "2.0",
        "method": "user.login",
        "params": {"user": zabbix_api_user, "password": zabbix_api_password},
        "id": 1
    }
    headers = {'Content-Type': 'application/json-rpc'}
    response = requests.post(zabbix_api_url, headers=headers, data=json.dumps(payload))
    response.raise_for_status()
    return response.json()['result']

def get_pingdom_checks():
    headers = {'Authorization': f'Bearer {pingdom_api_key}'}
    response = requests.get(pingdom_api_url, headers=headers)
    response.raise_for_status()
    return response.json()

def get_zabbix_host_id(auth_token, host_name):
    payload = {
        "jsonrpc": "2.0",
        "method": "host.get",
        "params": {"filter": {"host": [host_name]}},
        "auth": auth_token,
        "id": 1
    }
    headers = {'Content-Type': 'application/json-rpc'}
    response = requests.post(zabbix_api_url, headers=headers, data=json.dumps(payload))
    response.raise_for_status()
    result = response.json()['result']
    return result[0]['hostid'] if result else None

def create_zabbix_host(auth_token, host_name):
    payload = {
        "jsonrpc": "2.0",
        "method": "host.create",
        "params": {
            "host": host_name,
            "interfaces": [{"type": 1, "main": 1, "useip": 1, "ip": "127.0.0.1", "dns": "", "port": "10050"}],
            "groups": [{"groupid": zabbix_host_group_id}],
            "templates": [{"templateid": zabbix_template_id}]
        },
        "auth": auth_token,
        "id": 1
    }
    headers = {'Content-Type': 'application/json-rpc'}
    response = requests.post(zabbix_api_url, headers=headers, data=json.dumps(payload))
    response.raise_for_status()
    return response.json()['result']['hostids'][0]

def create_zabbix_item_batch(auth_token, host_ids, check_names):
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
    response = requests.post(zabbix_api_url, headers=headers, data=json.dumps(payload))
    response.raise_for_status()
    return response.json()

def create_zabbix_trigger_batch(auth_token, host_ids, check_names):
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
    response = requests.post(zabbix_api_url, headers=headers, data=json.dumps(payload))
    response.raise_for_status()
    return response.json()

def send_data_to_zabbix_batch(auth_token, host_ids, check_names, statuses):
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
    response = requests.post(zabbix_api_url, headers=headers, data=json.dumps(payload))
    response.raise_for_status()
    return response.json()

def process_check(auth_token, check):
    check_name = check['name']
    status = 1 if check['status'] == "up" else 0
    host_name = f"Pingdom_{check_name}"
    host_id = get_zabbix_host_id(auth_token, host_name)
    if not host_id:
        logging.info(f"Creating new host: {host_name}")
        host_id = create_zabbix_host(auth_token, host_name)
    return host_id, check_name, status

def main():
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
        create_zabbix_item_batch(auth_token, host_ids, check_names)
        
        # Create triggers in batch
        create_zabbix_trigger_batch(auth_token, host_ids, check_names)
        
        # Send data to Zabbix in batch
        send_data_to_zabbix_batch(auth_token, host_ids, check_names, statuses)

    except requests.exceptions.RequestException as e:
        logging.error(f"Request failed: {e}")
    except KeyError as e:
        logging.error(f"Key error: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()