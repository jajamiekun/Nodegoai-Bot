import os
import random
import time
import requests
from urllib.parse import urlparse
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from requests.exceptions import RequestException
from colorama import Fore, Back, Style, init
import pyfiglet

# Initialize colorama for terminal colors
init(autoreset=True)

def display_banner():
    """Display a colorful banner with the name KONTLIJO."""
    banner_text = pyfiglet.figlet_format("KONTLIJO", font="slant")
    print(Fore.CYAN + Style.BRIGHT + banner_text)

class NodeGoPinger:
    def __init__(self, token, proxy_urls=[]):
        self.api_base_url = 'https://nodego.ai/api'
        self.bearer_token = token
        self.proxy_urls = proxy_urls
        self.last_ping_timestamp = 0

    def create_proxy_session(self, proxy_url):
        """Create a session with the provided proxy."""
        session = requests.Session()
        parsed_url = urlparse(proxy_url)
        if parsed_url.scheme == 'socks5':
            session.proxies = {
                'http': proxy_url,
                'https': proxy_url
            }
        else:
            session.proxies = {
                'http': proxy_url,
                'https': proxy_url
            }

        retries = Retry(total=3, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504])
        session.mount('http://', HTTPAdapter(max_retries=retries))
        session.mount('https://', HTTPAdapter(max_retries=retries))

        return session

    def generate_node_id(self):
        """Generate a random node ID."""
        return f'node_{random.randint(0, 999999)}'

    def get_user_info(self, proxy_url):
        """Get user information using the provided proxy."""
        try:
            response = self.make_request('GET', '/user/me', proxy_url)
            metadata = response.json().get('metadata', {})
            return {
                'username': metadata.get('username'),
                'email': metadata.get('email'),
                'totalPoint': metadata.get('rewardPoint'),
                'nodes': [{'id': node['id'], 'totalPoint': node['totalPoint'], 
                           'todayPoint': node['todayPoint'], 'isActive': node['isActive']} 
                          for node in metadata.get('nodes', [])]
            }
        except RequestException as e:
            print(Fore.RED + f"Failed to fetch user info: {str(e)}")
            raise

    def make_request(self, method, endpoint, proxy_url, data=None):
        """Make a request to the API with retry logic."""
        url = f"{self.api_base_url}{endpoint}"
        headers = {
            'Authorization': f"Bearer {self.bearer_token}",
            'Content-Type': 'application/json',
            'Accept': '*/*'
        }

        session = self.create_proxy_session(proxy_url)
        retries = 3  # Retry count
        attempt = 0

        while attempt < retries:
            try:
                if method == 'GET':
                    response = session.get(url, headers=headers, timeout=30)
                elif method == 'POST':
                    response = session.post(url, headers=headers, json=data, timeout=30)

                # Check if the request was successful
                response.raise_for_status()

                # Return response if no errors
                return response
            except RequestException as e:
                attempt += 1
                print(Fore.YELLOW + f"Attempt {attempt}/{retries} failed: {str(e)}")
                if attempt == retries:
                    print(Fore.RED + f"Request failed after {retries} attempts: {str(e)}")
                    raise  # After retrying 3 times, raise the error
                # Wait before retrying the request
                time.sleep(5)  # Retry delay (5 seconds)

    def ping(self, proxy_url):
        """Send a ping to the NodeGo API."""
        try:
            current_time = int(time.time() * 1000)
            if current_time - self.last_ping_timestamp < 3000:
                time.sleep(3 - (current_time - self.last_ping_timestamp) / 1000)

            node_id = self.generate_node_id()

            response = self.make_request('POST', '/user/nodes/ping', proxy_url, {
                'type': 'extension',
                'nodeId': node_id
            })

            self.last_ping_timestamp = current_time

            return {
                'statusCode': response.json().get('statusCode'),
                'message': response.json().get('message'),
                'metadataId': response.json().get('metadata', {}).get('id'),
                'nodeId': node_id
            }
        except RequestException as e:
            print(Fore.RED + f"Ping failed: {str(e)}")
            raise

    def start_keep_alive_ping(self, proxy_url):
        """Start a loop to keep sending keep-alive pings every 5 seconds."""
        while True:
            try:
                print(Fore.BLUE + f"Sending keep-alive ping to proxy: {proxy_url}")
                ping_response = self.ping(proxy_url)
                print(Fore.GREEN + f"Keep-alive ping successful! Node ID: {ping_response['nodeId']}")
            except RequestException as e:
                print(Fore.RED + f"Keep-alive ping failed: {str(e)}")
                # Wait and retry in case of failure
                time.sleep(5)
            time.sleep(5)

class MultiAccountPinger:
    def __init__(self):
        self.accounts = self.load_accounts()
        self.is_running = True

    def load_accounts(self):
        """Load accounts and proxies from data files."""
        accounts = []
        try:
            with open('token.txt', 'r') as f:
                account_data = f.read().splitlines()

            proxy_data = []
            if os.path.exists('proxies.txt'):
                with open('proxies.txt', 'r') as f:
                    proxy_data = f.read().splitlines()

            for token in account_data:
                accounts.append({
                    'token': token.strip(),
                    'proxyUrls': proxy_data
                })
        except Exception as e:
            print(Fore.RED + f"Error reading accounts: {str(e)}")
            exit(1)

        return accounts

    def process_single_account(self, account):
        """Process a single account's information and pings."""
        pinger = NodeGoPinger(account['token'], account['proxyUrls'])
        
        try:
            for proxy_url in account['proxyUrls']:
                print(Fore.WHITE + f"\n⏰ Connecting to proxy: {proxy_url}")

                user_info = pinger.get_user_info(proxy_url)
                if not user_info:
                    return

                ping_response = pinger.ping(proxy_url)

                print(Fore.WHITE + "=" * 50)
                print(Fore.CYAN + f"Username: {user_info['username']}")
                print(Fore.YELLOW + f"Email: {user_info['email']}")

                for index, node in enumerate(user_info['nodes']):
                    print(Fore.MAGENTA + f"\nNode {index + 1}:")
                    print(Fore.WHITE + f"  ID: {node['id']}")
                    print(Fore.WHITE + f"  Total Points: {node['totalPoint']}")
                    print(Fore.WHITE + f"  Today's Points: {node['todayPoint']}")
                    print(Fore.WHITE + f"  Status: {'Active' if node['isActive'] else 'Inactive'}")
                
                print(Fore.GREEN + f"\nTotal Points: {user_info['totalPoint']}")
                print(Fore.GREEN + f"Status Code: {ping_response['statusCode']}")
                print(Fore.GREEN + f"Ping Message: {ping_response['message']}")
                print(Fore.GREEN + f"Generated Node ID: {ping_response['nodeId']}")
                print(Fore.WHITE + f"Metadata ID: {ping_response['metadataId']}")
                print(Fore.WHITE + "=" * 50)

                time.sleep(5)
        except RequestException as e:
            print(Fore.RED + f"Error processing account: {str(e)}")

    def run_pinger(self):
        """Run the pinger process for all accounts."""
        display_banner()
        while self.is_running:
            print(Fore.WHITE + f"\n⏰ Ping Cycle at {time.strftime('%Y-%m-%d %H:%M:%S')}")
            for account in self.accounts:
                if not self.is_running:
                    break
                self.process_single_account(account)

            if self.is_running:
                time.sleep(15)

if __name__ == '__main__':
    multi_pinger = MultiAccountPinger()
    multi_pinger.run_pinger()
