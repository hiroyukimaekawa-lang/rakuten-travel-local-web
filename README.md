# Rakuten Travel CSV Exporter (Local Web)

公式APIを使って、キーワード検索結果をCSVでダウンロードするローカルWebアプリです。

## 使い方

### 1) 依存関係のインストール

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) 環境変数の設定

```bash
export RAKUTEN_APP_ID=YOUR_APP_ID
export RAKUTEN_AFFILIATE_ID=YOUR_AFFILIATE_ID
```

### 3) 起動

```bash
python app.py
```

ブラウザで `http://127.0.0.1:8000` にアクセスしてください。

## CSV列

- `hotel_name`
- `min_charge`
- `url`
- `address`
- `tel`
- `total_rooms`

## 注意点

- 楽天ウェブサービスの利用規約に従って利用してください。
- APIの制限や上限に注意してください。
