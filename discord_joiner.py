import requests
import time
import random
import sys
import os

DISCORD_API_BASE = "https://discord.com/api/v9"
# Common user agent to look like a browser
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Context properties to mimic the Discord client
# This helps avoid some basic bot detection
X_SUPER_PROPERTIES = "eyJvcyI6IldpbmRvd3MiLCJicm93c2VyIjoiQ2hyb21lIiwiZGV2aWNlIjoiIiwic3lzdGVtX2xvY2FsZSI6ImVuLVVTIHciLCJicm93c2VyX3VzZXJfYWdlbnQiOiJNb3ppbGxhLzUuMCAoV2luZG93cyBOVCAxMC4wOyBXaW42NDsgeDY0KSBBcHBsZVdlYktpdC81MzcuMzYgKEtIVE1MLCBsaWtlIEdlY2tvKSBDaHJvbWUvMTIwLjAuMC4wIFNhZmFyaS81MzcuMzYiLCJicm93c2VyX3ZlcnNpb24iOiIxMjAuMC4wLjAiLCJvcy92ZXJzaW9uIjoiMTAuMCIsInJlZmVycmVyIjoiaHR0cHM6Ly9kaXNjb3JkLmNvbS8iLCJyZWZlcnJpbmdfZG9tYWluIjoiZGlzY29yZC5jb20iLCJyZWZlcnJlcl9jdXJyZW50IjoiIiwicmVmZXJyaW5nX2RvbWFpbl9jdXJyZW50IjoiIiwicmVsZWFzZV9jaGFubmVsIjoic3RhYmxlIiwiY2xpZW50X2J1aWxkX251bWJlciI6MjU1NTY5LCJjbGllbnRfZXZlbnRfc291cmNlIjpudWxsfQ=="

def load_file(filename):
    if not os.path.exists(filename):
        return []
    with open(filename, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]

def get_proxy_dict(proxy_str):
    if not proxy_str: return None
    return {
        "http": proxy_str,
        "https": proxy_str
    }

def join_guild(token, invite_code, proxy):
    # Extract code if full URL is provided
    code = invite_code.split('/')[-1]
    
    url = f"{DISCORD_API_BASE}/invites/{code}"
    
    headers = {
        "Authorization": token,
        "User-Agent": USER_AGENT,
        "X-Super-Properties": X_SUPER_PROPERTIES,
        "Content-Type": "application/json"
    }
    
    proxies = get_proxy_dict(proxy)
    
    try:
        # POST to /invites/<code> to join
        # Sometimes an empty body {} is required, or specific context
        r = requests.post(url, headers=headers, json={}, proxies=proxies)
        
        if r.status_code == 200:
            guild_name = r.json().get('guild', {}).get('name', 'Unknown Guild')
            print(f"[+] Joined: {guild_name} (Proxy: {proxy.split('@')[-1] if proxy else 'Direct'})")
            return True
        elif r.status_code == 400:
            # Captcha or invalid invite
            resp = r.json()
            if 'captcha_key' in resp:
                print(f"[-] Failed: Captcha Required (Token: {token[:10]}...)")
            else:
                print(f"[-] Failed: {resp.get('message', 'Bad Request')}")
            return False
        elif r.status_code == 403:
             print(f"[-] Failed: 403 Forbidden (Verify Phone/Email might be required)")
             return False
        else:
            print(f"[-] Failed: {r.status_code} {r.text[:100]}")
            return False
            
    except Exception as e:
        print(f"[-] Request Error: {e}")
        return False

def main():
    if len(sys.argv) < 2:
        print("Usage: python discord_joiner.py <invite_code>")
        # Fallback interactive mode
        invite_code = input("Enter Invite Code (e.g. shardeum): ").strip()
    else:
        invite_code = sys.argv[1]

    if not invite_code:
        print("Error: No invite code provided.")
        return

    print(f"=== Discord Batch Joiner: {invite_code} ===")
    
    tokens = load_file("discord_tokens.txt")
    proxies = load_file("proxies.txt")
    
    if not tokens:
        print("Error: discord_tokens.txt not found or empty.")
        return
        
    print(f"Loaded {len(tokens)} tokens, {len(proxies)} proxies.")
    
    success_count = 0
    
    for i, token in enumerate(tokens):
        proxy = proxies[i % len(proxies)] if proxies else None
        
        print(f"\n[{i+1}/{len(tokens)}] Token: {token[:10]}...")
        
        if join_guild(token, invite_code, proxy):
            success_count += 1
            delay = random.randint(10, 30)
            print(f"Sleeping {delay}s...")
            time.sleep(delay)
        else:
            print("Retrying next...")
            time.sleep(5)
            
    print(f"\nDone. Success: {success_count}/{len(tokens)}")

if __name__ == "__main__":
    main()
