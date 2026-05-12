#!/usr/bin/env python3
"""
Hotmail Live Check - Web Application
Flask app cho phép upload danh sách email, kiểm tra sống/chết tự động
"""
import os, uuid, threading, json, time
from flask import Flask, render_template, request, jsonify, send_file
from checker import HotmailChecker

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/tmp/hotmail_uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Store active checks
checks = {}

def parse_accounts(text):
    """Parse file content thành list (email, password)"""
    accounts = []
    for line in text.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        # Support both | and : as separator
        for sep in ['|', ':']:
            if sep in line:
                parts = line.split(sep, 1)
                email = parts[0].strip()
                password = parts[1].strip()
                if '@' in email and password:
                    accounts.append((email, password))
                break
    return accounts

def run_check(check_id, accounts):
    """Chạy check trong background thread"""
    checker = checks[check_id]['checker']
    
    def callback(status, email, reason, progress):
        status_icon = '✅' if status == 'ALIVE' else '❌'
        msg = f'{status_icon} {email} | {reason or "OK"}' if status != 'ALIVE' else f'✅ {email} | ALIVE'
        
        checks[check_id]['last_log'] = msg
        checks[check_id]['last_status'] = status
        
        # Keep last 100 entries
        if 'last_entries' not in checks[check_id]:
            checks[check_id]['last_entries'] = []
        checks[check_id]['last_entries'].append(msg)
        if len(checks[check_id]['last_entries']) > 100:
            checks[check_id]['last_entries'] = checks[check_id]['last_entries'][-100:]
    
    try:
        checker.check_batch(accounts, callback=callback)
    finally:
        alive_path = os.path.join(app.config['UPLOAD_FOLDER'], f'{check_id}_alive.txt')
        dead_path = os.path.join(app.config['UPLOAD_FOLDER'], f'{check_id}_dead.txt')
        checker.save_results(alive_path, dead_path)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start', methods=['POST'])
def start_check():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'No file selected'}), 400
    
    text = file.read().decode('utf-8', errors='ignore')
    accounts = parse_accounts(text)
    
    if not accounts:
        return jsonify({'error': 'No valid accounts found. Format: email@hotmail.com|password'}), 400
    
    check_id = str(uuid.uuid4())[:8]
    
    checker = HotmailChecker()
    checks[check_id] = {
        'checker': checker,
        'accounts': len(accounts),
        'started': time.time(),
        'last_log': '',
        'last_status': '',
        'last_entries': []
    }
    
    # Start in background thread
    t = threading.Thread(target=run_check, args=(check_id, accounts), daemon=True)
    t.start()
    
    return jsonify({
        'check_id': check_id,
        'total': len(accounts),
        'message': f'Started checking {len(accounts)} accounts'
    })

@app.route('/progress/<check_id>')
def get_progress(check_id):
    if check_id not in checks:
        return jsonify({'error': 'Check not found', 'running': False, 'processed': 0}), 404
    
    c = checks[check_id]
    results = c['checker'].get_results()
    
    return jsonify({
        'running': results['running'],
        'processed': results['processed'],
        'total': results['total'],
        'alive': len(results['alive']),
        'dead': len(results['dead']),
        'last_log': c.get('last_log', ''),
        'last_status': c.get('last_status', ''),
        'last_entries': c.get('last_entries', [])[-20:]  # Last 20 entries
    })

@app.route('/stop/<check_id>', methods=['POST'])
def stop_check(check_id):
    if check_id in checks:
        checks[check_id]['checker'].stop()
        return jsonify({'status': 'stopped'})
    return jsonify({'error': 'Not found'}), 404

@app.route('/download/<check_id>/<type>')
def download(check_id, type):
    if type not in ['alive', 'dead']:
        return 'Invalid type', 400
    
    path = os.path.join(app.config['UPLOAD_FOLDER'], f'{check_id}_{type}.txt')
    if not os.path.exists(path):
        return 'File not ready yet', 404
    
    name = f'hotmail_{type}.txt'
    return send_file(path, as_attachment=True, download_name=name)

@app.route('/results/<check_id>')
def get_results(check_id):
    if check_id not in checks:
        return jsonify({'error': 'Not found'}), 404
    
    c = checks[check_id]
    results = c['checker'].get_results()
    
    # Đọc từ file nếu có
    alive_path = os.path.join(app.config['UPLOAD_FOLDER'], f'{check_id}_alive.txt')
    dead_path = os.path.join(app.config['UPLOAD_FOLDER'], f'{check_id}_dead.txt')
    
    alive_list = []
    if os.path.exists(alive_path):
        with open(alive_path) as f:
            alive_list = [l.strip() for l in f if l.strip()]
    
    dead_list = []
    if os.path.exists(dead_path):
        with open(dead_path) as f:
            dead_list = [l.strip() for l in f if l.strip()]
    
    return jsonify({
        'running': results['running'],
        'alive': alive_list,
        'dead': dead_list,
        'alive_count': len(alive_list),
        'dead_count': len(dead_list),
        'total': results['total'],
        'processed': results['processed']
    })

@app.route('/cleanup', methods=['POST'])
def cleanup():
    """Dọn dẹp các check cũ (>30 phút)"""
    count = 0
    for check_id in list(checks.keys()):
        c = checks[check_id]
        if time.time() - c['started'] > 1800:  # 30 phút
            try:
                c['checker'].stop()
            except:
                pass
            del checks[check_id]
            count += 1
    return jsonify({'cleaned': count})

if __name__ == '__main__':
    print('🔥 Hotmail Live Check')
    print(f'Start: http://localhost:5000')
    print(f'Upload file .txt (email@hotmail.com|password) để kiểm tra')
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)
