import os
from flask import Flask, request, jsonify, send_from_directory
from openai import OpenAI # Import the OpenAI library
from dotenv import load_dotenv
from functools import wraps
import re # 日本語チェックのために正規表現ライブラリをインポート
import json # ファイルI/Oのために追加
import uuid # ユニークIDを生成するために追加

# .envファイルから環境変数を読み込む
load_dotenv()

# Flaskアプリケーションのインスタンスを作成
# static_folderのデフォルトは 'static' なので、
# このファイルと同じ階層に 'static' フォルダがあれば自動的にそこが使われます。
app = Flask(__name__)

# --- 履歴データのファイル永続化関連 ---
HISTORY_FILE = "history.json"

def load_history():
    """起動時にファイルから履歴を読み込む"""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_history(history_data):
    """履歴が更新されるたびにファイルに保存する"""
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history_data, f, ensure_ascii=False, indent=4)

# グローバル変数として履歴データを保持
history_log = load_history()

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


# --- OpenRouter APIクライアントの設定 ---

# 環境変数からAPIキーや設定情報を取得
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
SITE_URL = os.getenv("YOUR_SITE_URL", "http://localhost:5000") # 未設定の場合のデフォルト値
APP_NAME = os.getenv("YOUR_APP_NAME", "FlaskVueApp") # 未設定の場合のデフォルト値
CHAT_MODEL = os.getenv("CHAT_MODEL", "google/gemma-3-27b-it:free") # 未設定の場合のデフォルトモデル
client = None
# APIキーが設定されている場合のみ、OpenAIクライアントをインスタンス化
if OPENROUTER_API_KEY:
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
        default_headers={ # Recommended by OpenRouter
            "HTTP-Referer": SITE_URL,
            "X-Title": APP_NAME,
        }
    )

# --- Refactoring: Helper Functions and Decorators ---

def is_japanese(text):
    """文字列に日本語（ひらがな、カタカナ、漢字）が含まれているかチェックする"""
    # 日本語の文字、句読点、一般的な記号、英数字を許容する正規表現
    # これにより、完全に日本語以外の文字列（例: "hello world"）をブロックする
    return re.search(r'[ぁ-んァ-ン一-龠]', text)


def api_endpoint(f):
    """
    APIエンドポイントの共通処理をまとめたデコレータ。
    - APIクライアントのセットアップ確認
    - リクエストがJSON形式であることの確認
    - JSONデータに'text'フィールドが存在し、空でないことの検証
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not client:
            app.logger.error("OpenRouter API key not configured.")
            return jsonify({"error": "OpenRouter API key is not configured on the server."}), 500

        data = request.get_json()
        if not data or 'text' not in data:
            app.logger.error("Request JSON is missing or does not contain 'text' field.")
            return jsonify({"error": "Missing 'text' in request body"}), 400

        received_text = data.get('text', '').strip()
        if not received_text:
            app.logger.error("Received text is empty or whitespace.")
            return jsonify({"error": "Input text cannot be empty"}), 400
        
        received_text = data['text'].strip()
        # 日本語入力チェック
        if not is_japanese(received_text):
            return jsonify({"error": "日本語で入力してください。"}), 400
         
        # 元の関数にリクエストデータを渡して実行
        return f(data)
    return decorated_function

def call_openrouter_api(system_prompt, user_prompt, history_entry):
    """
    OpenRouter APIを呼び出し、レスポンスを処理する共通関数。
    """
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model=CHAT_MODEL,
        )

        if chat_completion.choices and chat_completion.choices[0].message:
            processed_text = chat_completion.choices[0].message.content
            # 正常に取得できたら履歴に追加
            history_log.append({
                "id": str(uuid.uuid4()), # ユニークなIDを生成
                "user": history_entry, 
                "ai": processed_text,
                "favorite": False # デフォルトはお気に入りではない
            })
            save_history(history_log) # 履歴をファイルに保存
            return jsonify({"message": "Success", "processed_text": processed_text})
        else:
            return jsonify({"error": "AIから有効な応答がありませんでした。"}), 500

    except Exception as e:
        app.logger.error(f"OpenRouter API call failed: {e}")
        return jsonify({"error": "AIサービスとの通信中にエラーが発生しました。"}), 500

# --- ページ表示用のルート定義 ---

@app.route('/')
def home():
    app.logger.info("Route '/' called.")
    return send_from_directory(app.static_folder, 'home.html')

# URL:/plot に対して、プロット生成画面(index.html)を表示
@app.route('/plot')
def plot_page():
    app.logger.info("Route '/plot' called.")
    return send_from_directory(app.static_folder, 'index.html')

# URL:/history に対して、履歴画面(history.html)を表示
@app.route('/history')
def history_page():
    app.logger.info("Route '/history' called.")
    return send_from_directory(app.static_folder, 'history.html')

# URL:/profread に対して、文章を豊かにする画面(profread.html)を表示
@app.route('/proofread')
def proofread_page():
    app.logger.info("Route '/proofread' called.")
    return send_from_directory(app.static_folder, 'proofread.html')

# --- APIエンドポイントのルート定義 ---

# 履歴データを全件取得するAPI
@app.route('/api/history', methods=['GET'])
def get_history():
    app.logger.info("API '/api/history' called.")
    return jsonify(history_log)

# URL:/api/history/toggle_favorite/<item_id> でお気に入り状態を切り替える
@app.route('/api/history/toggle_favorite/<item_id>', methods=['POST'])
def toggle_favorite(item_id):
    app.logger.info(f"API '/api/history/toggle_favorite/{item_id}' called.")
    item_found = False
    for item in history_log:
        if item.get('id') == item_id:
            item['favorite'] = not item.get('favorite', False)
            item_found = True
            save_history(history_log) # 変更をファイルに保存
            break
    if item_found:
        app.logger.info(f"Toggled favorite for item_id: {item_id}")
        return jsonify({"message": "Favorite status toggled successfully."})
    else:
        app.logger.warning(f"Item not found for item_id: {item_id}")
        return jsonify({"error": "Item not found."}), 404

# 全ての履歴を削除するAPI
@app.route('/api/history/clear', methods=['POST'])
def clear_history():
    app.logger.info("API '/api/history/clear' called.")
    global history_log
    history_log.clear() # メモリ上のリストをクリア
    save_history(history_log) # 空のリストをファイルに保存
    app.logger.info("History cleared successfully.")
    return jsonify({"message": "History cleared successfully."})

# 物語のプロットを生成するAPI
@app.route('/send_api', methods=['POST'])
@api_endpoint
def send_api(data):
    app.logger.info("API '/send_api' called.")
    received_text = data['text'].strip()
    # 入力がキーワード群か（長すぎる文章でないか）を簡易的にチェック
    word_count = len(received_text.replace('、', ' ').split())
    if word_count > 10: # 例えば10単語より多い場合はエラーとする
        app.logger.error(f"Input text is too long for keywords. Word count: {word_count}")
        return jsonify({"error": "キーワード( 『、』やスペースで区切ったもの)を10個以内で入力してください。"}), 400
    
    # フロントエンドから渡されたcontextをsystemプロンプトとして使用
    system_prompt = data.get('context', '').strip()
    result = call_openrouter_api(system_prompt, received_text, received_text)
    app.logger.info("API '/send_api' finished.")
    return result

# 登場人物の名前を生成するAPI
@app.route('/api/generate_name', methods=['POST'])
@api_endpoint
def generate_name_api(data):
    app.logger.info("API '/api/generate_name' called.")
    received_text = data['text'].strip()
    mode = data.get('mode', 'japanese') # デフォルトは日本人名

    if mode == 'japanese':
        # 日本人名生成用のプロンプト設定
        word_count = len(received_text.replace('、', ' ').split())
        if word_count > 3: 
            app.logger.error(f"Input text is too long for keywords. Word count: {word_count}")
            return jsonify({"error": "漢字( 『、』やスペースで区切ったもの)を3個以内で入力してください。"}), 400
        
        system_prompt = f"あなたはプロの作家です。指定された漢字「{received_text}」をフルネームのどこかに含んだ、日本のキャラクター名を5つ提案してください。\n\n# 制約条件:\n- 提案は箇条書き（-）で記述してください。\n- それぞれの名前の横に、その名前が持つ雰囲気や由来を20字程度で簡潔に添えてください。"
        history_user_text = f"「{received_text}」を含む日本人名"
        user_prompt = f"「{received_text}」を含む日本人名を提案してください。"

    elif mode == 'foreign':
        # 外国人名生成用のプロンプト設定
        word_count = len(received_text.replace('、', ' ').split())
        if word_count > 3: 
            app.logger.error(f"Input text is too long for keywords. Word count: {word_count}")
            return jsonify({"error": "キーワード( 『、』やスペースで区切ったもの)を3個以内で入力してください。"}), 400
        
        system_prompt = f"あなたはプロの作家です。指定されたキーワード「{received_text}」のイメージに合う、外国風のキャラクター名をカタカナで5つ提案してください。フルネームでもファーストネームのみでも構いません。\n\n# 制約条件:\n- 提案は箇条書き（-）で記述してください。\n- それぞれの名前の横に、その名前が持つ雰囲気や由来を20字程度で簡潔に添えてください。"
        history_user_text = f"「{received_text}」のイメージに合う外国人名"
        user_prompt = f"「{received_text}」のイメージに合う外国人名を提案してください。"
    else:
        return jsonify({"error": "無効なモードが指定されました。"}), 400

    result = call_openrouter_api(system_prompt, user_prompt, history_user_text)
    app.logger.info("API '/api/generate_name' finished.")
    return result

# 文章の描写を具体化するAPI
@app.route('/api/proofread', methods=['POST'])
@api_endpoint
def proofread_api(data):
    app.logger.info("API '/api/proofread' called.")
    received_text = data['text'].strip()
    # 文字数制限をチェック
    if len(received_text) > 100:
        app.logger.error(f"Input text for proofreading is too long: {len(received_text)} characters.")
        return jsonify({"error": "入力できる文字数は100文字までです。"}), 400

    system_prompt = "あなたはプロの小説家です。以下のユーザーが入力した短い文章を、情景が目に浮かぶような、豊かで具体的な小説の描写に書き換えてください。\n\n# 指示:\n- 変換後の文章のみを出力し、解説や前置きは一切含めないでください。\n- 300字以内で書いてください。"
    history_user_text = f"【描写の元文章】\n{received_text}" # 履歴のフォーマットを維持
    result = call_openrouter_api(system_prompt, received_text, history_user_text)
    app.logger.info("API '/api/proofread' finished.")
    return result

# 類語を検索するAPI
@app.route('/api/thesaurus', methods=['POST'])
@api_endpoint
def thesaurus_api(data):
    app.logger.info("API '/api/thesaurus' called.")
    received_text = data['text'].strip()
    # 入力が1つのキーワードであるかチェック
    word_count = len(received_text.replace('、', ' ').replace(',', ' ').split())
    if word_count > 1:
        return jsonify({"error": "キーワードを一つだけ入力してください。"}), 400

    system_prompt = f"あなたは語彙の専門家です。ユーザーから提供されたキーワード「{received_text}」について、類語や言い換え表現を3つ提案し、それぞれの違いが明確にわかるように解説してください。\n\n# 出力形式:\n- 提案する語彙ごとに見出しを付けてください。\n- それぞれの語彙について、「ニュアンス」と「使用例」を具体的に説明してください。\n- 全体を300字程度にまとめてください。\n- 類語や言い換え表現は日本語で提案してください。"
    user_prompt = f"「{received_text}」の類語を解説付きで教えてください。"
    history_user_text = f"「{received_text}」の類語検索"
    result = call_openrouter_api(system_prompt, user_prompt, history_user_text)
    app.logger.info("API '/api/thesaurus' finished.")
    return result


# スクリプトが直接実行された場合にのみ開発サーバーを起動
if __name__ == '__main__':
    if not OPENROUTER_API_KEY:
        print("警告: 環境変数 OPENROUTER_API_KEY が設定されていません。API呼び出しは失敗します。")
    app.run(debug=True, host='0.0.0.0', port=5000)