import os
from flask import Flask, request, jsonify, send_from_directory
from openai import OpenAI # Import the OpenAI library
from dotenv import load_dotenv

# .envファイルから環境変数を読み込む
load_dotenv()

# Flaskアプリケーションのインスタンスを作成
# static_folderのデフォルトは 'static' なので、
# このファイルと同じ階層に 'static' フォルダがあれば自動的にそこが使われます。
app = Flask(__name__)

# 履歴を保存するためのリスト（サーバーのメモリ上に保存）
# 注: サーバーを再起動すると履歴は失われます。
history_log = []


# 開発モード時に静的ファイルのキャッシュを無効にする
if app.debug:
    @app.after_request
    def add_header(response):
        # /static/ 以下のファイルに対するリクエストの場合
        if request.endpoint == 'static':
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache' # HTTP/1.0 backward compatibility
            response.headers['Expires'] = '0' # Proxies
        return response


# OpenRouter APIキーと関連情報を環境変数から取得
# このキーはサーバーサイドで安全に管理してください
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
SITE_URL = os.getenv("YOUR_SITE_URL", "http://localhost:5000") # Default if not set
APP_NAME = os.getenv("YOUR_APP_NAME", "FlaskVueApp") # Default if not set
CHAT_MODEL = os.getenv("CHAT_MODEL", "google/gemma-3-27b-it:free") # Default model

# OpenAI Clientのインスタンス化
# アプリケーション起動時に一度だけ実行する
client = None
if OPENROUTER_API_KEY:
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
        default_headers={ # Recommended by OpenRouter
            "HTTP-Referer": SITE_URL,
            "X-Title": APP_NAME,
        }
    )

# URL:/ に対して、ホーム画面(home.html)を表示
@app.route('/')
def home():
    # staticフォルダに home.html を作成する必要があります
    return send_from_directory(app.static_folder, 'home.html')

# URL:/plot に対して、プロット生成画面(index.html)を表示
@app.route('/plot')
def plot_page():
    return send_from_directory(app.static_folder, 'index.html')

# URL:/history に対して、履歴画面(history.html)を表示
@app.route('/history')
def history_page():
    # staticフォルダに history.html を作成する必要があります
    return send_from_directory(app.static_folder, 'history.html')

# URL:/api/history で履歴データをJSONとして返す
@app.route('/api/history', methods=['GET'])
def get_history():
    return jsonify(history_log)
    
# URL:/send_api に対するメソッドを定義
@app.route('/send_api', methods=['POST'])
def send_api():
    if not client:
        app.logger.error("OpenRouter API key not configured.")
        return jsonify({"error": "OpenRouter API key is not configured on the server."}), 500

  
    # POSTリクエストからJSONデータを取得
    data = request.get_json()

    # 'text'フィールドがリクエストのJSONボディに存在するか確認
    if not data or 'text' not in data:
        app.logger.error("Request JSON is missing or does not contain 'text' field.")
        return jsonify({"error": "Missing 'text' in request body"}), 400

    received_text = data['text']
    if not received_text.strip(): # 空文字列や空白のみの文字列でないか確認
        app.logger.error("Received text is empty or whitespace.")
        return jsonify({"error": "Input text cannot be empty"}), 400

    # 入力がキーワード群か（長すぎる文章でないか）を簡易的にチェック
    # スペースとカンマで分割し、単語数を数える
    word_count = len(received_text.replace('、', ' ').split())
    if word_count > 10: # 例えば10単語より多い場合はエラーとする
        app.logger.error(f"Input text is too long for keywords. Word count: {word_count}")
        return jsonify({"error": "キーワード（『、』やスペースで区切ったもの）を10個以内で入力してください。"}), 400
    
    # contextがあればsystemプロンプトに設定、なければデフォルト値
    system_prompt = "あなたは素晴らしい小説家です。ユーザーからの入力に対して、それらに関連する物語のプロットを短く作ってください。また、300字以内で書いてください。" # デフォルトのシステムプロンプト
    if 'context' in data and data['context'] and data['context'].strip():
        system_prompt = data['context'].strip()
        app.logger.info(f"Using custom system prompt from context: {system_prompt}")
    else:
        app.logger.info(f"Using default system prompt: {system_prompt}")

    try:
        # OpenRouter APIを呼び出し
        # モデル名はOpenRouterで利用可能なモデルを指定してください。
        # 例: "mistralai/mistral-7b-instruct", "google/gemini-pro", "openai/gpt-3.5-turbo"
        # 詳細はOpenRouterのドキュメントを参照してください。
        chat_completion = client.chat.completions.create(
            messages=[ # type: ignore
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": received_text}
            ], # type: ignore
            model=CHAT_MODEL, 
        )
        
        # APIからのレスポンスを取得
        if chat_completion.choices and chat_completion.choices[0].message:
            processed_text = chat_completion.choices[0].message.content
            # 正常に取得できたら履歴に追加
            history_log.append({"user": received_text, "ai": processed_text})
        else:
            processed_text = "AIから有効な応答がありませんでした。"
            
        return jsonify({"message": "AIによってデータが処理されました。", "processed_text": processed_text})

    except Exception as e:
        app.logger.error(f"OpenRouter API call failed: {e}")
        # クライアントには具体的なエラー詳細を返しすぎないように注意
        return jsonify({"error": f"AIサービスとの通信中にエラーが発生しました。"}), 500

# スクリプトが直接実行された場合にのみ開発サーバーを起動
if __name__ == '__main__':
    if not OPENROUTER_API_KEY:
        print("警告: 環境変数 OPENROUTER_API_KEY が設定されていません。API呼び出しは失敗します。")
    app.run(debug=True, host='0.0.0.0', port=5000)