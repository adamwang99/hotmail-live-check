# 🔥 Hotmail Live Check

Kiểm tra danh sách tài khoản Hotmail sống/chết tự động.

## Tính năng

- 📤 Upload file danh sách email (email@hotmail.com|password)
- 🚀 Kiểm tra tự động qua Playwright + proxy
- 📊 Dashboard real-time progress
- ⬇ Download kết quả (alive.txt / dead.txt)
- 🔄 Hỗ trợ proxy PAC

## Cài đặt

```bash
# 1. Clone repo
git clone https://github.com/adamwang99/hotmail-live-check.git
cd hotmail-live-check

# 2. Cài dependencies
pip install -r requirements.txt

# 3. Cài Playwright browser
playwright install chromium

# 4. Chạy
python app.py
```

Mở trình duyệt: `http://localhost:5000`

## Định dạng file input

Mỗi dòng 1 tài khoản:
```
email@hotmail.com|password
```

Hỗ trợ cả `:` làm separator:
```
email@hotmail.com:password
```

## Cấu hình proxy (optional)

Set env `PROXY_PAC`:
```bash
export PROXY_PAC="http://ip.mproxy.vn/12313.pac"
python app.py
```

## Output

- `alive.txt`: danh sách tài khoản còn sống
- `dead.txt`: danh sách tài khoản chết + lý do

## Lưu ý

- Cần cài Playwright (`playwright install chromium`)
- Mỗi tài khoản mất ~10-15s để kiểm tra
- Proxy giúp tránh bị Microsoft chặn IP
