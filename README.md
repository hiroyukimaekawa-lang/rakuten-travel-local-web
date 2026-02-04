# Rakuten Travel CSV Exporter

楽天トラベルの公式APIを使用して、指定したキーワードの宿泊施設情報を検索し、CSVファイルとして一括ダウンロードするローカルWebアプリケーションです。

## 特徴
- **キーワード検索**: 「温泉」「貸し別荘」などのキーワードで検索可能
- **詳細情報取得**: 一覧検索(`KeywordHotelSearch`)に加え、詳細検索(`HotelDetailSearch`)で「総部屋数」なども自動補完
- **CSVダウンロード**: 検索結果をその場でCSVとしてダウンロード
- **API制限への配慮**: リクエスト間隔を調整可能

## 前提条件
- Python 3.8以上
- 楽天トラベルAPIの `applicationId` (必須)
- (任意) `affiliateId`

## セットアップ手順

1. **リポジトリのクローン**
   ```bash
   git clone <repository-url>
   cd rakuten-travel-local-web-1
   ```

2. **依存ライブラリのインストール**
   ```bash
   # 仮想環境の作成と有効化 (推奨)
   python3 -m venv .venv
   source .venv/bin/activate  # Windowsの場合は .venv\Scripts\activate

   # ライブラリのインストール
   pip install -r requirements.txt
   ```
   *※ `requirements.txt` がない場合は `pip install flask` を実行してください*

3. **環境変数の設定**
   実行前に必ず `RAKUTEN_APP_ID` を設定してください。

   ```bash
   export RAKUTEN_APP_ID="あなたのアプリID"
   # アフィリエイトIDがある場合（任意）
   export RAKUTEN_AFFILIATE_ID="あなたのアフィリエイトID"
   ```

4. **アプリの起動**
   ```bash
   python3 app.py
   ```
   起動後、ブラウザで [http://127.0.0.1:8000](http://127.0.0.1:8000) にアクセスしてください。

## 使い方
1. ブラウザで画面を開く。
2. 「検索キーワード」を入力（例: `箱根`）。
3. 必要に応じて「一覧取得数」「ページ数」を調整。
4. 「CSVをダウンロード」をクリック。
5. 数秒〜数分待つと、ダウンロードが開始されます。
   *※ 処理中はサーバーログに詳細な進捗が表示されます。*
