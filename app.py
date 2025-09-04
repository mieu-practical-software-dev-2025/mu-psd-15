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
#CHAT_MODEL = os.getenv("CHAT_MODEL", "google/gemma-3-27b-it:free") # Default model

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

# URL:/proofread に対して、校正画面(proofread.html)を表示
@app.route('/proofread')
def proofread_page():
    # staticフォルダに proofread.html を作成する必要があります
    return send_from_directory(app.static_folder, 'proofread.html')

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
    
    # フロントエンドから渡されたcontextをsystemプロンプトとして使用
    system_prompt = data.get('context', '').strip()
    app.logger.info(f"Using custom system prompt from context: {system_prompt}")

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
            model="google/gemma-2-9b-it:free", 
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

# URL:/api/generate_name に対するメソッドを定義
@app.route('/api/generate_name', methods=['POST'])
def generate_name_api():
    if not client:
        app.logger.error("OpenRouter API key not configured.")
        return jsonify({"error": "OpenRouter API key is not configured on the server."}), 500

    data = request.get_json()
    if not data or 'text' not in data:
        app.logger.error("Request JSON is missing or does not contain 'text' field.")
        return jsonify({"error": "Missing 'text' in request body"}), 400

    received_text = data['text']
    if not received_text.strip():
        app.logger.error("Received text for name generation is empty.")
        return jsonify({"error": "Input text cannot be empty"}), 400

    # 入力が1つのキーワードであるかチェック
    # スペースやカンマで分割し、単語数を数える
    word_count = len(received_text.replace('、', ' ').replace(',', ' ').split())
    if word_count > 1:
        return jsonify({"error": "キーワードを一つだけ入力してください。"}), 400

    # 'type'フィールド（'surname' or 'given_name'）を取得
    generation_type = data.get('type', 'surname') # デフォルトは 'surname'

    # 名前生成用のシステムプロンプト
    if generation_type == 'surname':
        system_prompt = f"あなたはプロの作家です。指定された漢字「{received_text}」を【苗字】に含んだ、創造的で記憶に残りやすいフルネームのキャラクター名を5つ提案してください。\n\n# 制約条件:\n- 提案は箇条書き（-）で記述してください。\n- それぞれの名前の横に、その名前が持つ雰囲気や由来を20字程度で簡潔に添えてください。\n- 一般的すぎない、物語の登場人物として魅力的な名前を重視してください。"
        history_user_text = f"「{received_text}」を苗字に含む名前"
    else: # 'given_name'
        system_prompt = f"あなたはプロの作家です。指定された漢字「{received_text}」を【名前】に含んだ、創造的で記憶に残りやすいフルネームのキャラクター名を5つ提案してください。\n\n# 制約条件:\n- 提案は箇条書き（-）で記述してください。\n- それぞれの名前の横に、その名前が持つ雰囲気や由来を20字程度で簡潔に添えてください。\n- 一般的すぎない、物語の登場人物として魅力的な名前を重視してください。"
        history_user_text = f"「{received_text}」を名前に含む名前"

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"「{received_text}」を含む名前を提案してください。"}
            ],
            model="mistralai/mistral-7b-instruct:free",
        )

        if chat_completion.choices and chat_completion.choices[0].message:
            processed_text = chat_completion.choices[0].message.content
        else:
            processed_text = "AIから有効な応答がありませんでした。"

        # 正常に取得できたら履歴に追加
        history_log.append({"user": history_user_text, "ai": processed_text})

        return jsonify({"message": "名前が生成されました。", "processed_text": processed_text})

    except Exception as e:
        app.logger.error(f"OpenRouter API call for name generation failed: {e}")
        return jsonify({"error": "AIサービスとの通信中にエラーが発生しました。"}), 500

# URL:/api/proofread に対するメソッドを定義
@app.route('/api/proofread', methods=['POST'])
def proofread_api():
    if not client:
        app.logger.error("OpenRouter API key not configured.")
        return jsonify({"error": "OpenRouter API key is not configured on the server."}), 500

    data = request.get_json()
    if not data or 'text' not in data:
        app.logger.error("Request JSON is missing or does not contain 'text' field.")
        return jsonify({"error": "Missing 'text' in request body"}), 400

    received_text = data['text']
    if not received_text.strip():
        app.logger.error("Received text for proofreading is empty.")
        return jsonify({"error": "校正する文章を入力してください。"}), 400

    # 文字数制限をチェック
    if len(received_text) > 500:
        app.logger.error(f"Input text for proofreading is too long: {len(received_text)} characters.")
        return jsonify({"error": "入力できる文字数は500文字までです。"}), 400

    # 校正用のシステムプロンプト
    system_prompt = "あなたは優秀な編集者です。以下の文章を、誤字脱字の修正、文法的な誤りの訂正、句読点の適切な使用、より自然で分かりやすい表現への改善など、総合的に校正してください。\n\n# 指示:\n- 元の文章の意図やニュアンスを最大限尊重してください。\n- 校正後の文章のみを出力し、解説や前置きは一切含めないでください。"

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": received_text}
            ],
            model="google/gemma-2-9b-it:free",
        )

        if chat_completion.choices and chat_completion.choices[0].message:
            processed_text = chat_completion.choices[0].message.content
            # 正常に取得できたら履歴に追加
            history_log.append({"user": f"【校正依頼】\n{received_text}", "ai": f"【校正結果】\n{processed_text}"})
        else:
            processed_text = "AIから有効な応答がありませんでした。"

        return jsonify({"message": "文章が校正されました。", "processed_text": processed_text})

    except Exception as e:
        app.logger.error(f"OpenRouter API call for proofreading failed: {e}")
        return jsonify({"error": "AIサービスとの通信中にエラーが発生しました。"}), 500

# URL:/api/thesaurus に対するメソッドを定義
@app.route('/api/thesaurus', methods=['POST'])
def thesaurus_api():
    if not client:
        app.logger.error("OpenRouter API key not configured.")
        return jsonify({"error": "OpenRouter API key is not configured on the server."}), 500

    data = request.get_json()
    if not data or 'text' not in data:
        app.logger.error("Request JSON is missing or does not contain 'text' field.")
        return jsonify({"error": "Missing 'text' in request body"}), 400

    received_text = data['text']
    if not received_text.strip():
        app.logger.error("Received text for thesaurus is empty.")
        return jsonify({"error": "キーワードを入力してください。"}), 400

    # 入力が1つのキーワードであるかチェック
    # スペースやカンマで分割し、単語数を数える
    word_count = len(received_text.replace('、', ' ').replace(',', ' ').split())
    if word_count > 1:
        return jsonify({"error": "キーワードを一つだけ入力してください。"}), 400

    # 類語提案用のシステムプロンプト
    system_prompt = f"あなたは語彙の専門家です。ユーザーから提供されたキーワード「{received_text}」について、類語や言い換え表現を3つ提案し、それぞれの違いが明確にわかるように解説してください。\n\n# 出力形式:\n- 提案する語彙ごとに見出しを付けてください。\n- それぞれの語彙について、「ニュアンス」と「使用例」を具体的に説明してください。\n- 全体を300字程度にまとめてください。"

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"「{received_text}」の類語を解説付きで教えてください。"}
            ],
            model="google/gemma-2-9b-it:free",
        )

        if chat_completion.choices and chat_completion.choices[0].message:
            processed_text = chat_completion.choices[0].message.content
            # 正常に取得できたら履歴に追加
            history_log.append({"user": f"【類語検索】\n{received_text}", "ai": f"【類語解説】\n{processed_text}"})
        else:
            processed_text = "AIから有効な応答がありませんでした。"

        return jsonify({"message": "類語が生成されました。", "processed_text": processed_text})

    except Exception as e:
        app.logger.error(f"OpenRouter API call for thesaurus failed: {e}")
        return jsonify({"error": "AIサービスとの通信中にエラーが発生しました。"}), 500


# スクリプトが直接実行された場合にのみ開発サーバーを起動
if __name__ == '__main__':
    if not OPENROUTER_API_KEY:
        print("警告: 環境変数 OPENROUTER_API_KEY が設定されていません。API呼び出しは失敗します。")
    app.run(debug=True, host='0.0.0.0', port=5000)