from curl_cffi import requests
import time
import random
import csv
import sys
import os

DISCORD_API_BASE = "https://discord.com/api/v9"
# curl_cffi handles user-agent and ja3 when impersonating
# We just need to ensure we set the content type correctly

# Configuration
CHANNEL_ID = "1423751569454661632" # Shardeum Faucet Channel

# ...

def check_channel_access(token, channel_id, proxy=None):
    url = f"{DISCORD_API_BASE}/channels/{channel_id}"
    headers = {"Authorization": token}
    proxies = get_proxy_dict(proxy)
    try:
        # Use chrome120 impersonation
        r = requests.get(url, headers=headers, proxies=proxies, impersonate="chrome120")
        if r.status_code == 200:
            print(f"[+] Channel Access OK: {r.json().get('name')}")
            return True
        else:
            print(f"[-] Channel Access Failed: {r.status_code} {r.text}")
            return False
    except Exception as e:
        print(f"[-] Channel Check Error: {e}")
        return False

def get_command_metadata(token, channel_id, query="faucet"):
    """
    Auto-discover the application_id and command_id for the slash command.
    This mimics the client searching for commands in the channel.
    """
    url = f"{DISCORD_API_BASE}/channels/{channel_id}/application-commands/search?type=1&query={query}&limit=7&include_applications=true"
    headers = {
        "Authorization": token
    }
    
    try:
        print(f"[*] Discovering slash command IDs for '/{query}'...")
        # Note: This endpoint might require a valid user token and might be sensitive.
        # If it fails, we might need fallback IDs or manual input.
        r = requests.get(url, headers=headers, impersonate="chrome120")
        if r.status_code == 200:
            data = r.json()
            commands = data.get('application_commands', [])
            for cmd in commands:
                if cmd['name'] == query:
                    print(f"[+] Found Command: {cmd['name']} (ID: {cmd['id']}) App ID: {cmd['application_id']}")
                    return {
                        "application_id": cmd['application_id'],
                        "command_id": cmd['id'],
                        "version": cmd['version'],
                        "name": cmd['name'],
                        "options": cmd.get('options', [])
                    }
            print("[-] Command not found in search results.")
        else:
            print(f"[-] Discovery failed: {r.status_code} {r.text}")
    except Exception as e:
        print(f"[-] Discovery Error: {e}")
    
    return None

def send_slash_command(token, proxy, meta, wallet_address):
    """
    Send the actual interaction payload.
    """
    url = f"{DISCORD_API_BASE}/interactions"
    
    # Construct the payload for /faucet address: <wallet>
    # Usually structure:
    # data: {
    #   id: command_id,
    #   name: "faucet",
    #   type: 1,
    #   options: [ { type: 3, name: "address", value: "0x..." } ]
    # }
    
    payload = {
        "type": 2, # Application Command
        "application_id": meta['application_id'],
        "guild_id": None, # DM or Guild? Assuming Guild if channel is in guild.
        # We need guild_id if it's a guild channel.
        # For Shardeum, it is a guild. We can try to fetch guild_id from channel or just omit if not strictly required (usually is).
        # Actually, let's fetch channel details first if possible, or just try without guild_id (might fail).
        # Better: User provided channel ID, we can assume it's a guild channel.
        # Let's try to get guild_id from channel info first.
        "channel_id": CHANNEL_ID,
        "session_id": "0", # Can often be mocked or 0 for scripts
        "data": {
            "version": meta['version'],
            "id": meta['command_id'],
            "name": meta['name'],
            "type": 1,
            "options": [
                {
                    "type": 3, # String
                    "name": "address",
                    "value": wallet_address
                }
            ],
            "application_command": {
                "id": meta['command_id'],
                "application_id": meta['application_id'],
                "version": meta['version'],
                "default_member_permissions": None,
                "type": 1,
                "nsfw": False,
                "name": meta['name'],
                "description": meta.get('description', 'Claim tokens'),
                "dm_permission": True,
                "options": meta['options']
            }
        },
        "nonce": str(int(time.time() * 1000000))
    }
    
    # Need to get Guild ID for the channel
    # Hack: If we don't have guild_id, some bots reject.
    # We can do a quick GET /channels/ID to find guild_id.
    
    headers = {
        "Authorization": token,
        "Content-Type": "application/json"
    }
    
    proxies = get_proxy_dict(proxy)
    
    try:
        # Step 0: Get Guild ID (Lazy fetch)
        r_chan = requests.get(f"{DISCORD_API_BASE}/channels/{CHANNEL_ID}", headers=headers, proxies=proxies, impersonate="chrome120")
        if r_chan.status_code == 200:
            guild_id = r_chan.json().get('guild_id')
            if guild_id:
                payload['guild_id'] = guild_id
        
        # Step 1: Send Interaction
        r = requests.post(url, json=payload, headers=headers, proxies=proxies, impersonate="chrome120")
        
        if r.status_code == 204:
            print(f"[+] Success: {wallet_address} (Proxy: {proxy.split('@')[-1] if proxy else 'Direct'})")
            return True
        else:
            print(f"[-] Failed: {r.status_code} {r.text[:100]}")
            return False

    except Exception as e:
        print(f"[-] Request Error: {e}")
        return False


def load_file(filename):
    if not os.path.exists(filename):
        print(f"Error: File {filename} not found.")
        return []
    with open(filename, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]

def load_wallets(filename):
    if not os.path.exists(filename):
        print(f"Error: File {filename} not found.")
        return []
    wallets = []
    with open(filename, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if row:
                wallets.append(row[0].strip())
    return wallets

def get_proxy_dict(proxy_str):
    """
    Convert proxy string (http://user:pass@ip:port) to requests dict
    """
    if not proxy_str: return None
    return {
        "http": proxy_str,
        "https": proxy_str
    }

def get_command_metadata(token, channel_id, query="faucet"):
    """
    Auto-discover the application_id and command_id for the slash command.
    This mimics the client searching for commands in the channel.
    """
    url = f"{DISCORD_API_BASE}/channels/{channel_id}/application-commands/search?type=1&query={query}&limit=7&include_applications=true"
    headers = {
        "Authorization": token,
        "User-Agent": USER_AGENT
    }
    
    try:
        print(f"[*] Discovering slash command IDs for '/{query}'...")
        # Note: This endpoint might require a valid user token and might be sensitive.
        # If it fails, we might need fallback IDs or manual input.
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            data = r.json()
            commands = data.get('application_commands', [])
            for cmd in commands:
                if cmd['name'] == query:
                    print(f"[+] Found Command: {cmd['name']} (ID: {cmd['id']}) App ID: {cmd['application_id']}")
                    return {
                        "application_id": cmd['application_id'],
                        "command_id": cmd['id'],
                        "version": cmd['version'],
                        "name": cmd['name'],
                        "options": cmd.get('options', [])
                    }
            print("[-] Command not found in search results.")
        else:
            print(f"[-] Discovery failed: {r.status_code} {r.text}")
    except Exception as e:
        print(f"[-] Discovery Error: {e}")
    
    return None

def send_slash_command(token, proxy, meta, wallet_address):
    """
    Send the actual interaction payload.
    """
    url = f"{DISCORD_API_BASE}/interactions"
    
    # Construct the payload for /faucet address: <wallet>
    # Usually structure:
    # data: {
    #   id: command_id,
    #   name: "faucet",
    #   type: 1,
    #   options: [ { type: 3, name: "address", value: "0x..." } ]
    # }
    
    payload = {
        "type": 2, # Application Command
        "application_id": meta['application_id'],
        "guild_id": None, # DM or Guild? Assuming Guild if channel is in guild.
        # We need guild_id if it's a guild channel.
        # For Shardeum, it is a guild. We can try to fetch guild_id from channel or just omit if not strictly required (usually is).
        # Actually, let's fetch channel details first if possible, or just try without guild_id (might fail).
        # Better: User provided channel ID, we can assume it's a guild channel.
        # Let's try to get guild_id from channel info first.
        "channel_id": CHANNEL_ID,
        "session_id": "0", # Can often be mocked or 0 for scripts
        "data": {
            "version": meta['version'],
            "id": meta['command_id'],
            "name": meta['name'],
            "type": 1,
            "options": [
                {
                    "type": 3, # String
                    "name": "address",
                    "value": wallet_address
                }
            ],
            "application_command": {
                "id": meta['command_id'],
                "application_id": meta['application_id'],
                "version": meta['version'],
                "default_member_permissions": None,
                "type": 1,
                "nsfw": False,
                "name": meta['name'],
                "description": meta.get('description', 'Claim tokens'),
                "dm_permission": True,
                "options": meta['options']
            }
        },
        "nonce": str(int(time.time() * 1000000))
    }
    
    # Need to get Guild ID for the channel
    # Hack: If we don't have guild_id, some bots reject.
    # We can do a quick GET /channels/ID to find guild_id.
    
    headers = {
        "Authorization": token,
        "User-Agent": USER_AGENT,
        "Content-Type": "application/json"
    }
    
    proxies = get_proxy_dict(proxy)
    
    try:
        # Step 0: Get Guild ID (Lazy fetch)
        r_chan = requests.get(f"{DISCORD_API_BASE}/channels/{CHANNEL_ID}", headers=headers, proxies=proxies)
        if r_chan.status_code == 200:
            guild_id = r_chan.json().get('guild_id')
            if guild_id:
                payload['guild_id'] = guild_id
        
        # Step 1: Send Interaction
        r = requests.post(url, json=payload, headers=headers, proxies=proxies)
        
        if r.status_code == 204:
            print(f"[+] Success: {wallet_address} (Proxy: {proxy.split('@')[-1] if proxy else 'Direct'})")
            return True
        else:
            print(f"[-] Failed: {r.status_code} {r.text[:100]}")
            return False

    except Exception as e:
        print(f"[-] Request Error: {e}")
        return False

def main():
    print("=== Shardeum Discord Faucet Bot ===")
    
    tokens = load_file("discord_tokens.txt")
    wallets = load_wallets("wallets.csv")
    proxies = load_file("proxies.txt")
    
    if not tokens or not wallets:
        print("Please provide discord_tokens.txt and wallets.csv")
        return

    print(f"Loaded {len(tokens)} tokens, {len(wallets)} wallets, {len(proxies)} proxies.")
    
    # 1. Discovery Phase (Use first token and first proxy)
    first_token = tokens[0]
    first_proxy = proxies[0] if proxies else None
    
    print("Initializing discovery...")
    
    # Check if channel is accessible
    if not check_channel_access(first_token, CHANNEL_ID, first_proxy):
        print("Fatal: Cannot access channel. Please check: 1. Token is valid 2. User is in the server 3. Channel ID is correct.")
        return

    # Note: Search endpoint usually requires no proxy or a clean one.
    meta = get_command_metadata(first_token, CHANNEL_ID)
    
    if not meta:
        print("Could not discover command ID. Aborting.")
        # Fallback manual IDs if you have them:
        # meta = {"application_id": "...", "command_id": "...", "version": "...", "name": "faucet", "options": [...]}
        return

    # 2. Execution Loop
    for i, token in enumerate(tokens):
        if i >= len(wallets):
            print("No more wallets.")
            break
            
        wallet = wallets[i]
        proxy = proxies[i % len(proxies)] if proxies else None
        
        print(f"\n[{i+1}/{len(tokens)}] Processing Token: {token[:10]}... Wallet: {wallet[:10]}...")
        
        success = send_slash_command(token, proxy, meta, wallet)
        
        if success:
            delay = random.randint(30, 60)
            print(f"Sleeping {delay}s...")
            time.sleep(delay)
        else:
            print("Retrying next...")
            time.sleep(5)

if __name__ == "__main__":
    main()
