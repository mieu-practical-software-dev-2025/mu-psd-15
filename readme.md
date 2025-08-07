# 生成AI活用サンプルアプリ

# 概要

このアプリは Python とVue.jsを用いて作られた簡易的な生成AI活用アプリです。

- フロントエンドに、Vue.js CDN版を用いています。

- バックエンドに、Python,FlaskとOpenAI APIを用いて、OpenRouter APIを叩いています。

# 開発ツールインストール

- 管理者権限でコマンドプロンプトを起動します。

- 以下のコマンドを実行し、必要なソフトウェアを入手します。

```
winget install --id Git.Git -e --source winget
winget install --id Python.Python.3 -e --source winget
winget install --id Microsoft.VisualStudioCode -e --source winget
```

- vscodeを起動し、アクティビティバーの拡張機能から、以下のプラグインをインストールしてください。

  - Gemini Code Assist
  - Python
  - Vue.js Extension Pack

# 環境セットアップ

- [OpenRouter](https://openrouter.ai/)にアカウントを作成します。

- OpenRouterで、Keys → Create API Keys を選択、適当なキー名を付けて作成し、キー文字列をメモ帳等に保存しておきます。

- Python ライブラリインストール

  以下のコマンドでPythonの利用ライブラリをインストールします。

  ``` pip install -r requrements.txt ```

# 実行方法

- example.envを.envにリネームして、OpenRouterのキーを記載してください。

- 以下のコマンドでサーバを起動します。

  ``` python app.py ```

- ブラウザで以下のURLにアクセスしてみてください。

  ``` http://localhost:5000 ```

# 開発の参考資料

- vscodeのGemini Code Assist を起動して修正を依頼すると、コードを修正したり解説してくれます。

- フロントエンド担当者は、html/JavaScriptを追加／修正して画面を構築してください。

- バックエンド担当者は、app.py上にURLとAPIを作成してください。

# 参考リンク

- [Flask](https://flask.palletsprojects.com/en/stable/)

  - Python で書かれた Webアプリケーションサーバ

- [Vue.js](https://vuejs.org/)

  - JavaScript製製のWebフロントエンド フレームワーク

- [Vue.js Tutorial](https://ja.vuejs.org/tutorial/)

  - Vue.jsの入門用チュートリアル
  
- [OpenAI API](https://github.com/openai/openai-python)

  - Pythonから、OpenAI APIを呼び出すライブラリ

