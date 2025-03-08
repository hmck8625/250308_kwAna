import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
import os
import time
import json
import re
import base64
from openai import OpenAI
import difflib

# デバッグモード
DEBUG = True

# デバッグ関数
def debug_info(message, expanded=False):
    """通常のデバッグ情報表示"""
    if DEBUG:
        with st.expander("🔍 デバッグ情報", expanded=expanded):
            st.write(message)

def upload_debug_info(message):
    """ファイルアップロード時のデバッグ情報は常に表示"""
    if DEBUG:
        st.info("📋 アップロードファイル情報")
        st.json(message)

# 標準的なフィールド名と説明（日本語も追加）
STANDARD_FIELDS = {
    'Keyword': ['キーワード', 'keywords', 'search term', '検索語句', 'query', 'kw', 'キーワードテキスト'],
    'MatchType': ['マッチタイプ', 'match type', 'match', 'matching', 'タイプ', '一致タイプ', '一致キーワード', 'マッチングタイプ'],
    'Impressions': ['imp', 'imps', 'impression', 'インプレッション', '表示回数', '表示数', '露出数', 'インプレッション数'],
    'Clicks': ['click', 'クリック', 'クリック数', 'クリック回数', 'click count', 'clicks'],
    'Cost': ['コスト', 'cost', '費用', '金額', 'spend', '支出', '消化金額', '消化額'],
    'Conversions': ['conversion', 'conv', 'コンバージョン', '成約', 'cv', 'CVs', '獲得数', 'コンバージョン数', 'コンバ数', 'GACV'],
    'CampaignName': ['キャンペーン名', 'campaign', 'キャンペーン', 'campaign name', 'キャンペーンネーム', 'cp', 'campname'],
    'AdGroupName': ['広告グループ名', 'adgroup', 'ad group', '広告グループ', 'group name', 'グループ名', 'adgroupname', 'ag']
}

# 必須フィールド
REQUIRED_FIELDS = ['Keyword', 'MatchType', 'Impressions', 'Clicks', 'Cost', 'Conversions']

# 初期設定
st.set_page_config(page_title="リスティング広告キーワード分析", page_icon="📊", layout="wide")

# アプリケーションのスタイル
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1E88E5;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.8rem;
        font-weight: bold;
        color: #0D47A1;
        margin-top: 2rem;
        margin-bottom: 1rem;
    }
    .card {
        background-color: #f9f9f9;
        padding: 1.5rem;
        border-radius: 0.5rem;
        box-shadow: 0 0.15rem 0.5rem rgba(0, 0, 0, 0.1);
        margin-bottom: 1rem;
    }
    .warning {
        color: #FFA000;
        font-weight: bold;
    }
    .success {
        color: #4CAF50;
        font-weight: bold;
    }
    .info-box {
        background-color: #E3F2FD;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .progress-container {
        margin-top: 1rem;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# セッション状態の初期化
if 'data' not in st.session_state:
    st.session_state.data = None
if 'raw_data' not in st.session_state:
    st.session_state.raw_data = None
if 'column_mapping' not in st.session_state:
    st.session_state.column_mapping = None
if 'categorized_data' not in st.session_state:
    st.session_state.categorized_data = None
if 'is_categorized' not in st.session_state:
    st.session_state.is_categorized = False
if 'categories_master' not in st.session_state:
    st.session_state.categories_master = None
if 'category_stats' not in st.session_state:
    st.session_state.category_stats = None
if 'api_key' not in st.session_state:
    st.session_state.api_key = ""
if 'service_description' not in st.session_state:
    st.session_state.service_description = ""
if 'client' not in st.session_state:
    st.session_state.client = None

# ヘッダー表示
st.markdown('<div class="main-header">リスティング広告キーワード分析システム</div>', unsafe_allow_html=True)

# OpenAI関連の関数
def suggest_column_mapping_with_llm(df_columns, api_key):
    """LLMを使用して列名のマッピングを提案する"""
    if not api_key:
        return None, "APIキーが設定されていません"
    
    try:
        client = OpenAI(api_key=api_key)
        
        prompt = f"""
あなたはリスティング広告のデータ分析の専門家です。以下のExcelの列名を標準的な列名にマッピングしてください。

入力された列名:
{', '.join(df_columns)}

標準的な列名の候補:
- Keyword: キーワード（必須）
- MatchType: マッチタイプ（完全一致/フレーズ一致/部分一致など）（必須）
- Impressions: インプレッション数（必須）
- Clicks: クリック数（必須）
- Cost: コスト（必須）
- Conversions: コンバージョン数（必須）
- CampaignName: キャンペーン名（推奨）
- AdGroupName: 広告グループ名（推奨）

各列名に対して、最も適切な標準列名を選んでください。適切なマッピングがない場合は "unknown" としてください。
結果は以下のJSON形式で返してください:

```json
{
  "入力列名1": "標準列名1",
  "入力列名2": "標準列名2",
  ...
}
```

また、必須フィールドとなっている標準列名のいずれかに適切なマッピングがない場合は、その旨も教えてください。
"""
        
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant specializing in data analysis."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000,
            temperature=0.1
        )
        
        content = response.choices[0].message.content
        
        # JSONの部分を抽出
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', content)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = content
        
        # JSONをパース
        try:
            result = json.loads(json_str)
            return result, None
        except json.JSONDecodeError as e:
            return None, f"JSONパースエラー: {e}\n\nレスポンス: {content}"
        
    except Exception as e:
        return None, f"API呼び出しエラー: {e}"

def suggest_column_mapping_with_rules(df_columns):
    """ルールベースで列名のマッピングを提案する"""
    mapping = {}
    
    for col in df_columns:
        col_lower = col.lower()
        matched = False
        
        for std_field, alternatives in STANDARD_FIELDS.items():
            # 完全一致
            if col_lower == std_field.lower():
                mapping[col] = std_field
                matched = True
                break
            
            # 部分一致（大文字小文字を区別しない）
            for alt in alternatives:
                if alt.lower() in col_lower:
                    mapping[col] = std_field
                    matched = True
                    break
            
            if matched:
                break
        
        # 文字列類似度でマッチング
        if not matched:
            best_match = None
            best_score = 0.7  # 閾値
            
            for std_field, alternatives in STANDARD_FIELDS.items():
                score = difflib.SequenceMatcher(None, col_lower, std_field.lower()).ratio()
                if score > best_score:
                    best_match = std_field
                    best_score = score
                
                for alt in alternatives:
                    score = difflib.SequenceMatcher(None, col_lower, alt.lower()).ratio()
                    if score > best_score:
                        best_match = std_field
                        best_score = score
            
            if best_match:
                mapping[col] = best_match
            else:
                mapping[col] = "unknown"
    
    return mapping

def create_column_mapping_ui(df, api_key=None):
    """カラムマッピングのUI作成"""
    st.markdown("### 列名マッピング")
    st.write("Excelの列名を標準的な列名にマッピングします。必要に応じて修正してください。")
    
    # LLMとルールベースの両方で提案を取得
    llm_mapping = None
    if api_key:
        with st.spinner("AIによる列名分析中..."):
            llm_mapping, error = suggest_column_mapping_with_llm(df.columns.tolist(), api_key)
            if error:
                st.warning(f"AIによる分析でエラーが発生しました: {error}")
                st.write("ルールベースの分析を使用します。")
    
    # ルールベースによるマッピング（LLMが失敗した場合のバックアップ）
    rule_mapping = suggest_column_mapping_with_rules(df.columns.tolist())
    
    # 最終マッピング（LLMが成功した場合はそれを優先）
    final_mapping = llm_mapping if llm_mapping else rule_mapping
    
    # マッピング編集UI
    st.write("以下のマッピングを確認し、必要に応じて修正してください：")
    
    # 必須フィールドと推奨フィールドに分けて表示
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 必須フィールド")
        mapping_inputs_required = {}
        
        # 検出されていないフィールドを追跡
        missing_fields = []
        
        for field in REQUIRED_FIELDS:
            # このフィールドにマッピングされた列を検索
            mapped_columns = [col for col, mapped in final_mapping.items() if mapped == field]
            
            if mapped_columns:
                # デフォルトで最初にマッピングされた列を選択
                default_idx = df.columns.tolist().index(mapped_columns[0]) if mapped_columns[0] in df.columns else 0
                mapping_inputs_required[field] = st.selectbox(
                    f"{field} (必須)",
                    options=["--選択してください--"] + df.columns.tolist(),
                    index=default_idx + 1  # +1 because of the "--選択してください--" option
                )
            else:
                # マッピングされた列がない場合
                missing_fields.append(field)
                mapping_inputs_required[field] = st.selectbox(
                    f"{field} (必須・未検出)",
                    options=["--選択してください--"] + df.columns.tolist(),
                    index=0
                )
    
    with col2:
        st.markdown("#### 推奨フィールド")
        mapping_inputs_recommended = {}
        
        recommended_fields = [f for f in STANDARD_FIELDS.keys() if f not in REQUIRED_FIELDS]
        
        for field in recommended_fields:
            # このフィールドにマッピングされた列を検索
            mapped_columns = [col for col, mapped in final_mapping.items() if mapped == field]
            
            if mapped_columns:
                # デフォルトで最初にマッピングされた列を選択
                default_idx = df.columns.tolist().index(mapped_columns[0]) if mapped_columns[0] in df.columns else 0
                mapping_inputs_recommended[field] = st.selectbox(
                    f"{field} (推奨)",
                    options=["--なし--"] + df.columns.tolist(),
                    index=default_idx + 1  # +1 because of the "--なし--" option
                )
            else:
                # マッピングされた列がない場合
                mapping_inputs_recommended[field] = st.selectbox(
                    f"{field} (推奨)",
                    options=["--なし--"] + df.columns.tolist(),
                    index=0
                )
    
    # 未検出フィールドの警告
    if missing_fields:
        st.warning(f"以下の必須フィールドが自動検出されませんでした。適切な列を選択してください: {', '.join(missing_fields)}")
    
    # マッピングを適用するかどうか
    apply_mapping = st.button("このマッピングを適用する")
    
    if apply_mapping:
        # 選択された内容からマッピングを作成
        selected_mapping = {}
        
        for field, selected in mapping_inputs_required.items():
            if selected != "--選択してください--":
                selected_mapping[field] = selected
        
        for field, selected in mapping_inputs_recommended.items():
            if selected != "--なし--":
                selected_mapping[field] = selected
        
        # 必須フィールドの確認
        missing = [field for field in REQUIRED_FIELDS if field not in selected_mapping]
        
        if missing:
            st.error(f"以下の必須フィールドが選択されていません: {', '.join(missing)}")
            return None, None
        
        # 最終マッピングを反転（元の列名→標準列名）
        inverse_mapping = {selected_mapping[k]: k for k in selected_mapping}
        
        # DataFrameに適用
        mapped_df = df.copy()
        mapped_df = mapped_df.rename(columns=inverse_mapping)
        
        st.success("列名のマッピングが完了しました！")
        return mapped_df, selected_mapping
    
    return None, None

# LLMによるキーワード分析関数
def categorize_keywords_with_llm(keywords, service_description, api_key, batch_size=100):
    """LLMを使用してキーワードをカテゴライズする"""
    if not api_key:
        return None, "OpenAI API Keyが設定されていません。"
    
    try:
        # 全ての要素を文字列に変換し、無効な値を除外
        valid_keywords = []
        keyword_map = {}  # 元のキーワード型を保持するためのマップ
        
        for kw in keywords:
            # None、空文字列をフィルタリング
            if kw is not None and str(kw).strip() != '':
                kw_str = str(kw)
                valid_keywords.append(kw_str)
                keyword_map[kw_str] = kw  # 元のデータ型を保持
        
        # 有効なキーワードがない場合
        if not valid_keywords:
            return [], "有効なキーワードがありません。"
        
        client = OpenAI(api_key=api_key)
        
        prompt = f"""
あなたはリスティング広告の専門家です。以下のキーワードリストを分析し、2つの観点で分類してください。

サービス概要:
{service_description}

以下のキーワードを分析してください:
{', '.join(valid_keywords[:batch_size])}  # バッチサイズで制限

各キーワードを以下の2つの観点で分類し、JSONで返してください:
1. 軸キーワード: サービスの核となる主要概念・機能（5-8カテゴリ程度）
2. 掛け合わせキーワード: 検索意図、修飾語、ユーザーニーズなど（5-8カテゴリ程度）

レスポンスフォーマット:
```json
[
  {{
    "keyword": "キーワード1",
    "axis_category": "カテゴリA",
    "combination_category": "カテゴリX"
  }},
  {{
    "keyword": "キーワード2",
    "axis_category": "カテゴリB",
    "combination_category": "カテゴリY"
  }}
]
```

カテゴリ名は簡潔で分かりやすいものにしてください。
"""
        
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that specializes in keyword analysis for advertising."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=4000,
            temperature=0.3
        )
        
        content = response.choices[0].message.content
        
        # JSONの部分を抽出
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', content)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = content
        
        # JSONをパース
        try:
            result = json.loads(json_str)
            
            # 結果の各アイテムのキーワードを元の値に置き換え
            for item in result:
                if item['keyword'] in keyword_map:
                    # 元のデータ型（文字列または数値）のキーワードを使用
                    item['keyword'] = keyword_map[item['keyword']]
            
            return result, None
        except json.JSONDecodeError as e:
            return None, f"JSONパースエラー: {e}\n\nレスポンス: {content}"
        
    except Exception as e:
        return None, f"API呼び出しエラー: {e}"

# カテゴリ分類に失敗した場合のバックアップとしてのLLMクラスタリング
def cluster_keywords_with_llm(keywords, service_description, api_key, suggested_clusters=5):
    """LLMを使用してキーワードをクラスタリングする"""
    if not api_key:
        return None, None, "APIキーが設定されていません。"
    
    # 空や無効なキーワードをフィルタリング
    valid_keywords = []
    keyword_map = {}  # 元のキーワード型を保持するためのマップ
    
    for kw in keywords:
        if kw is not None and str(kw).strip() != '':
            kw_str = str(kw)
            valid_keywords.append(kw_str)
            keyword_map[kw_str] = kw  # 元のデータ型を保持
    
    # 有効なキーワードがない場合
    if not valid_keywords:
        dummy_result = []
        return dummy_result, "有効なキーワードがありません。"
    
    try:
        client = OpenAI(api_key=api_key)
        
        # クラスター数の自動調整（キーワード数に応じて）
        cluster_count = min(suggested_clusters, max(2, len(valid_keywords) // 5))
        
        prompt = f"""
あなたはキーワード分析の専門家です。以下のキーワードリストを分析し、意味的に関連するグループに分類してください。

サービス概要:
{service_description}

キーワードリスト:
{', '.join(valid_keywords)}

分析タスク:
1. 各キーワードを「軸カテゴリ」と「掛け合わせカテゴリ」の2つの観点で分類してください。
   - 軸カテゴリ: サービスの核となる主要概念・機能（{cluster_count}個程度）
   - 掛け合わせカテゴリ: ユーザーの検索意図や修飾語（{cluster_count}個程度）

2. 以下のJSON形式で結果を返してください:
```json
[
  {{
    "keyword": "キーワード1",
    "axis_category": "軸カテゴリA",
    "combination_category": "掛け合わせカテゴリX"
  }},
  {{
    "keyword": "キーワード2",
    "axis_category": "軸カテゴリB",
    "combination_category": "掛け合わせカテゴリY"
  }}
]
```

カテゴリ名は簡潔で分かりやすいものにしてください。
各キーワードは必ずいずれかの軸カテゴリと掛け合わせカテゴリに分類してください。
"""
        
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "You are a keyword analysis expert specializing in clustering and categorization."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=4000,
            temperature=0.3
        )
        
        content = response.choices[0].message.content
        
        # JSONの部分を抽出
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', content)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = content
        
        # JSONをパース
        try:
            result = json.loads(json_str)
            
            # 結果の各アイテムのキーワードを元の値に置き換え
            for item in result:
                if item['keyword'] in keyword_map:
                    item['keyword'] = keyword_map[item['keyword']]  # 元のデータ型を使用
            
            return result, None
        except json.JSONDecodeError as e:
            return None, f"JSONパースエラー: {e}\n\nレスポンス: {content}"
        
    except Exception as e:
        return None, f"LLMクラスタリングエラー: {e}"

# サイドバー
with st.sidebar:
    st.header("設定")
    api_key = st.text_input("OpenAI API Key", st.session_state.api_key, type="password")
    if api_key:
        st.session_state.api_key = api_key
        os.environ["OPENAI_API_KEY"] = api_key
        # OpenAIクライアントの初期化
        try:
            st.session_state.client = OpenAI(api_key=api_key)
            st.success("APIキーを設定しました")
        except Exception as e:
            st.error(f"APIクライアント初期化エラー: {str(e)}")
    
    st.markdown("### キーワード処理設定")
    cost_threshold = st.slider("コスト上位カバー率 (%)", 50, 100, 80)
    max_keywords_per_batch = st.slider("バッチあたり最大キーワード数", 50, 500, 100)
    
    st.markdown("### 分析設定")
    kw_min_cost = st.number_input("最小コスト閾値 (円)", 0, 1000000, 1000)
    min_clicks = st.number_input("最小クリック数", 0, 1000, 10)
    
    st.markdown("### サービス説明")
    st.session_state.service_description = st.text_area(
        "サービスの概要を記入してください（AIによるカテゴライズの精度向上に役立ちます）",
        st.session_state.service_description, 
        height=150
    )
    
    # API接続テスト
    if st.button("API接続テスト"):
        if not st.session_state.api_key:
            st.error("APIキーが設定されていません")
        else:
            try:
                client = OpenAI(api_key=st.session_state.api_key)
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": "こんにちは"}],
                    max_tokens=10
                )
                st.success(f"API接続成功！レスポンス: {response.choices[0].message.content}")
            except Exception as e:
                st.error(f"API接続エラー: {str(e)}")

# メイン処理
tab1, tab2, tab3, tab4 = st.tabs(["データアップロード", "キーワードカテゴライズ", "分析結果", "レポート"])

# タブ1: データアップロード
with tab1:
    st.markdown('<div class="sub-header">キーワードデータのアップロード</div>', unsafe_allow_html=True)
    
    with st.expander("📋 データフォーマット説明", expanded=False):
        st.markdown("""
        ### 必須フィールド
        アップロードするExcelには以下のフィールドが必要です：
        - **Keyword**: 分析対象のキーワード
        - **MatchType**: マッチタイプ（完全一致/フレーズ一致/部分一致など）
        - **Impressions**: インプレッション数
        - **Clicks**: クリック数
        - **Cost**: コスト
        - **Conversions**: コンバージョン数
        
        ### 推奨フィールド
        - **CampaignName**: キャンペーン名
        - **AdGroupName**: 広告グループ名
        
        ### フォーマット例
        | Keyword | MatchType | Impressions | Clicks | Cost | Conversions | CampaignName | AdGroupName |
        |---------|-----------|-------------|--------|------|-------------|--------------|-------------|
        | リスティング 広告 | フレーズ一致 | 1200 | 120 | 24000 | 5 | ブランド | メイン |
        
        ※ フィールド名が異なる場合でも、AIが自動的に識別・マッピングします。
        """)
    
    st.write("### エラーが出る場合の対処法")
    st.markdown("""
    ファイルアップロード時にエラーが出る場合：
    
    1. **ファイルサイズの確認**: ファイルが200MB以下であることを確認してください
    2. **別のブラウザで試す**: Chrome、Firefox、Edgeなど別のブラウザで試してみてください
    3. **シンプルなファイルで試す**: 少量のデータだけを含む新しいExcelファイルで試してください
    4. **ファイル形式**: .xlsx形式であることを確認してください
    """)
    
    # ファイルアップロードコンポーネント - エラーハンドリングを強化
    try:
        uploaded_file = st.file_uploader("Excelファイルをアップロード (.xlsx)", type=['xlsx'])
        
        if uploaded_file is not None:
            # デバッグ情報を常に表示
            file_info = {
                "ファイル名": uploaded_file.name,
                "ファイルサイズ": f"{len(uploaded_file.getvalue())} bytes",
                "ファイルタイプ": uploaded_file.type
            }
            upload_debug_info(file_info)
            
            try:
                # BytesIOを使ってメモリ上で処理
                bytes_data = uploaded_file.getvalue()
                with BytesIO(bytes_data) as data:
                    # エンジンを明示的に指定し、エラーを詳細に表示
                    raw_df = pd.read_excel(data, engine='openpyxl')
                
                # 列情報を常に表示
                st.write("検出された列:", list(raw_df.columns))
                
                # 元のデータをセッションに保存
                st.session_state.raw_data = raw_df
                
                # フィールドマッピングUI表示
                mapped_df, column_mapping = create_column_mapping_ui(raw_df, st.session_state.api_key)
                
                if mapped_df is not None and column_mapping is not None:
                    # マッピング情報をセッションに保存
                    st.session_state.column_mapping = column_mapping
                    
                    # 数値データの確認と変換
                    numeric_columns = ['Impressions', 'Clicks', 'Cost', 'Conversions']
                    for col in numeric_columns:
                        if mapped_df[col].dtype == 'object':
                            mapped_df[col] = pd.to_numeric(mapped_df[col].astype(str).str.replace(',', '').str.replace('¥', ''), errors='coerce')
                    
                    # 派生指標の計算
                    mapped_df['CTR'] = (mapped_df['Clicks'] / mapped_df['Impressions'] * 100).round(2)
                    mapped_df['CVR'] = (mapped_df['Conversions'] / mapped_df['Clicks'] * 100).round(2)
                    mapped_df['CPC'] = (mapped_df['Cost'] / mapped_df['Clicks']).round(0)
                    mapped_df['CPA'] = (mapped_df['Cost'] / mapped_df['Conversions']).round(0)
                    mapped_df['CPM'] = (mapped_df['Cost'] / mapped_df['Impressions'] * 1000).round(0)
                    
                    # 無限値をNaNに置き換え
                    mapped_df.replace([float('inf'), -float('inf')], np.nan, inplace=True)
                    
                    # データ保存
                    st.session_state.data = mapped_df
                    
                    # データプレビュー表示
                    st.markdown('<div class="sub-header">データプレビュー</div>', unsafe_allow_html=True)
                    st.dataframe(mapped_df.head(10))
                    
                    # 基本統計情報
                    st.markdown('<div class="sub-header">基本統計情報</div>', unsafe_allow_html=True)
                    
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("キーワード数", f"{len(mapped_df):,}")
                    
                    with col2:
                        st.metric("総コスト", f"¥{mapped_df['Cost'].sum():,.0f}")
                    
                    with col3:
                        st.metric("総クリック数", f"{mapped_df['Clicks'].sum():,.0f}")
                    
                    with col4:
                        st.metric("総コンバージョン数", f"{mapped_df['Conversions'].sum():,.0f}")
                    
                    st.success("データが正常に読み込まれました！「キーワードカテゴライズ」タブに進んでください。")
            
            except Exception as e:
                st.error(f"ファイル読み込み中にエラーが発生しました: {str(e)}")
                st.exception(e)  # より詳細なエラー情報を表示
                
                # 追加のヘルプを表示
                st.warning("""
                **トラブルシューティング：**
                - ファイルが壊れていないか確認してください
                - 別のExcelバージョンで保存し直してみてください
                - ファイル内に特殊なフォーマットや数式がある場合は単純な値に変換してください
                """)
    
    except Exception as e:
        st.error(f"ファイルアップロードコンポーネントでエラーが発生しました: {str(e)}")
        st.exception(e)
        
        # 代替アップロード方法の提案
        st.warning("""
        **代替アップロード方法:**
        1. ファイルをCSV形式で保存し直してみてください
        2. データ量を減らした簡易版ファイルでテストしてください
        """)
    else:
        st.info("Excelファイルをアップロードしてください。")

# タブ2: キーワードカテゴライズ
with tab2:
    st.markdown('<div class="sub-header">キーワードのカテゴライズ</div>', unsafe_allow_html=True)
    
    if st.session_state.data is None:
        st.warning("先に「データアップロード」タブでデータをアップロードしてください。")
    else:
        df = st.session_state.data
        
        if not st.session_state.is_categorized:
            with st.expander("カテゴライズ方法", expanded=True):
                st.markdown("""
                ### キーワードカテゴライズの仕組み
                
                このシステムは以下の方法でキーワードをカテゴライズします：
                
                1. **コストによる優先順位付け**：コスト順に上位のキーワードを優先的に処理
                2. **バッチ処理**：大量のキーワードを小さなバッチに分割して処理
                3. **AI分析**：OpenAIのGPTモデルを使用して意味ベースのカテゴリ分類
                
                カテゴリは2種類作成されます：
                - **軸キーワード**：サービスの核となる主要概念・機能
                - **掛け合わせキーワード**：検索意図、修飾語、ユーザーニーズなど
                """)
            
            categorize_button = st.button("キーワードのカテゴライズを開始")
            
            if categorize_button:
                if not st.session_state.api_key:
                    st.error("OpenAI API Keyが設定されていません。サイドバーで設定してください。")
                else:
                    # API接続テスト
                    try:
                        with st.spinner("API接続をテスト中..."):
                            client = OpenAI(api_key=st.session_state.api_key)
                            test_response = client.chat.completions.create(
                                model="gpt-3.5-turbo",
                                messages=[{"role": "user", "content": "テスト"}],
                                max_tokens=5
                            )
                            debug_info(f"API接続テスト成功: {test_response.choices[0].message.content}")
                    except Exception as e:
                        st.error(f"API接続テストに失敗しました: {str(e)}")
                        st.stop()
                    
                    # 前処理 - コスト順に並べる
                    sorted_df = df.sort_values('Cost', ascending=False)
                    total_cost = sorted_df['Cost'].sum()
                    
                    # コスト上位のキーワードを抽出（閾値までの累積コストで判断）
                    sorted_df['cumulative_cost'] = sorted_df['Cost'].cumsum()
                    sorted_df['cumulative_cost_percent'] = sorted_df['cumulative_cost'] / total_cost * 100
                    high_cost_df = sorted_df[sorted_df['cumulative_cost_percent'] <= cost_threshold]
                    
                    total_keywords = len(high_cost_df)
                    
                    if total_keywords > 5000:
                        st.warning(f"処理するキーワード数が多いため({total_keywords}件)、処理に時間がかかる場合があります。")
                    
                    st.info(f"コスト上位{cost_threshold}%をカバーするキーワード{total_keywords}件を処理します。")
                    
                    # 進捗バー
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    # 一意のキーワードを抽出
                    unique_keywords = []
                    for kw in high_cost_df['Keyword'].unique():
                        if kw is not None and str(kw).strip() != '':
                            unique_keywords.append(kw)
                    
                    total_unique = len(unique_keywords)
                    
                    debug_info(f"一意のキーワード数: {total_unique}")
                    
                    # 空のデータセットチェック
                    if not unique_keywords:
                        st.error("有効なキーワードが見つかりません。データを確認してください。")
                        st.stop()
                    
                    # バッチに分割
                    batch_size = min(max_keywords_per_batch, 100)  # 安全のために100件に制限
                    batches = [unique_keywords[i:i+batch_size] for i in range(0, len(unique_keywords), batch_size)]
                    
                    debug_info(f"バッチ数: {len(batches)}, バッチサイズ: {batch_size}")
                    
                    # 結果保存用
                    all_categorized = []
                    errors = []
                    
                    # バッチ処理
                    for i, batch in enumerate(batches):
                        status_text.text(f"バッチ {i+1}/{len(batches)} 処理中... ({len(batch)}キーワード)")
                        
                        # LLMでキーワードカテゴライズ
                        result, error = categorize_keywords_with_llm(
                            batch,
                            st.session_state.service_description,
                            st.session_state.api_key
                        )
                        
                        if error:
                            debug_info(f"バッチ {i+1} エラー: {error}")
                            
                            # バッチ処理失敗時は、代替LLMクラスタリングで処理
                            status_text.text(f"カテゴライズ失敗のため、代替AIクラスタリングを実行中...")
                            
                            # LLMクラスタリング実行
                            backup_result, backup_error = cluster_keywords_with_llm(
                                batch, 
                                st.session_state.service_description,
                                st.session_state.api_key
                            )
                            
                            if backup_error:
                                debug_info(f"代替AIクラスタリングでもエラー: {backup_error}")
                                # 最もシンプルな処理：全て同じカテゴリに
                                temp_categorized = []
                                for kw in batch:
                                    if kw is not None and str(kw).strip() != '':
                                        temp_categorized.append({
                                            "keyword": kw,
                                            "axis_category": "未分類グループ",
                                            "combination_category": "自動分類"
                                        })
                                all_categorized.extend(temp_categorized)
                                errors.append(f"バッチ {i+1} 処理エラー: {error}, バックアップ処理もエラー: {backup_error}")
                            else:
                                debug_info(f"バッチ {i+1} 代替クラスタリング成功: {len(backup_result)}件処理")
                                all_categorized.extend(backup_result)
                                errors.append(f"バッチ {i+1} 通常処理エラー: {error}、代替処理で回復")
                        else:
                            debug_info(f"バッチ {i+1} 成功: {len(result)}件のキーワードを処理")
                            all_categorized.extend(result)
                        
                        # 進捗更新
                        progress = min(1.0, (i + 1) / len(batches))
                        progress_bar.progress(progress)
                        
                        # APIレート制限に対応するための待機
                        time.sleep(0.5)
                    
                    # カテゴリマスタの作成
                    categories_df = pd.DataFrame(all_categorized)
                    
                    # 元のデータとマージ
                    categorized_data = df.copy()
                    category_map = {row['keyword']: {'axis': row['axis_category'], 'combination': row['combination_category']} 
                                    for _, row in categories_df.iterrows()}
                    
                    # カテゴリの適用関数
                    def apply_categories(keyword):
                        if keyword in category_map:
                            return category_map[keyword]['axis'], category_map[keyword]['combination']
                        else:
                            return "未分類", "未分類"
                    
                    # カテゴリの適用
                    categorized_data[['AxisCategory', 'CombinationCategory']] = categorized_data.apply(
                        lambda row: pd.Series(apply_categories(row['Keyword'])), axis=1
                    )
                    
                    # セッションに保存
                    st.session_state.categorized_data = categorized_data
                    st.session_state.categories_master = categories_df
                    st.session_state.is_categorized = True
                    
                    # カテゴリ基本統計
                    axis_categories = categorized_data['AxisCategory'].nunique()
                    combination_categories = categorized_data['CombinationCategory'].nunique()
                    
                    status_text.text(f"カテゴライズ完了！軸カテゴリ数: {axis_categories}, 掛け合わせカテゴリ数: {combination_categories}")
                    
                    if errors:
                        with st.expander("処理中に発生したエラー", expanded=False):
                            for error in errors:
                                st.error(error)
                    
                    st.success("カテゴライズが完了しました！「分析結果」タブに進んでください。")
        else:
            st.success("キーワードのカテゴライズは完了しています。")
            
            # カテゴリマスタの表示
            st.markdown('<div class="sub-header">カテゴリマスタ</div>', unsafe_allow_html=True)
            
            tab_master1, tab_master2 = st.tabs(["軸カテゴリ", "掛け合わせカテゴリ"])
            
            with tab_master1:
                axis_counts = st.session_state.categorized_data['AxisCategory'].value_counts().reset_index()
                axis_counts.columns = ['軸カテゴリ', 'キーワード数']
                st.dataframe(axis_counts)
                
                # 円グラフ
                fig = px.pie(axis_counts, values='キーワード数', names='軸カテゴリ', title='軸カテゴリの分布')
                st.plotly_chart(fig)
            
            with tab_master2:
                combination_counts = st.session_state.categorized_data['CombinationCategory'].value_counts().reset_index()
                combination_counts.columns = ['掛け合わせカテゴリ', 'キーワード数']
                st.dataframe(combination_counts)
                
                # 円グラフ
                fig = px.pie(combination_counts, values='キーワード数', names='掛け合わせカテゴリ', title='掛け合わせカテゴリの分布')
                st.plotly_chart(fig)
            
            # リセットオプション
            if st.button("カテゴライズをリセット"):
                st.session_state.is_categorized = False
                st.session_state.categorized_data = None
                st.session_state.categories_master = None
                st.session_state.category_stats = None
                st.success("カテゴライズデータがリセットされました。必要に応じて再実行してください。")
                st.experimental_rerun()

# タブ3: 分析結果
with tab3:
    st.markdown('<div class="sub-header">カテゴリ別パフォーマンス分析</div>', unsafe_allow_html=True)
    
    if not st.session_state.is_categorized:
        st.warning("先に「キーワードカテゴライズ」タブでカテゴライズを実行してください。")
    else:
        categorized_data = st.session_state.categorized_data
        
        if 'category_stats' not in st.session_state or st.session_state.category_stats is None:
            # カテゴリ別集計の初回計算
            with st.spinner("カテゴリ別パフォーマンスを集計中..."):
                # 1. 軸カテゴリ別集計
                axis_stats = categorized_data.groupby('AxisCategory').agg({
                    'Keyword': 'count',
                    'Impressions': 'sum',
                    'Clicks': 'sum',
                    'Cost': 'sum',
                    'Conversions': 'sum'
                }).reset_index()
                
                # 派生指標の計算
                axis_stats['CTR'] = (axis_stats['Clicks'] / axis_stats['Impressions'] * 100).round(2)
                axis_stats['CVR'] = (axis_stats['Conversions'] / axis_stats['Clicks'] * 100).round(2)
                axis_stats['CPC'] = (axis_stats['Cost'] / axis_stats['Clicks']).round(0)
                axis_stats['CPA'] = (axis_stats['Cost'] / axis_stats['Conversions']).round(0)
                
                # ラベル変更
                axis_stats.rename(columns={'Keyword': 'キーワード数'}, inplace=True)
                
                # 2. 掛け合わせカテゴリ別集計
                combination_stats = categorized_data.groupby('CombinationCategory').agg({
                    'Keyword': 'count',
                    'Impressions': 'sum',
                    'Clicks': 'sum',
                    'Cost': 'sum',
                    'Conversions': 'sum'
                }).reset_index()
                
                # 派生指標の計算
                combination_stats['CTR'] = (combination_stats['Clicks'] / combination_stats['Impressions'] * 100).round(2)
                combination_stats['CVR'] = (combination_stats['Conversions'] / combination_stats['Clicks'] * 100).round(2)
                combination_stats['CPC'] = (combination_stats['Cost'] / combination_stats['Clicks']).round(0)
                combination_stats['CPA'] = (combination_stats['Cost'] / combination_stats['Conversions']).round(0)
                
                # ラベル変更
                combination_stats.rename(columns={'Keyword': 'キーワード数'}, inplace=True)
                
                # 3. クロス集計（軸×掛け合わせ）
                cross_stats = categorized_data.groupby(['AxisCategory', 'CombinationCategory']).agg({
                    'Keyword': 'count',
                    'Impressions': 'sum',
                    'Clicks': 'sum',
                    'Cost': 'sum',
                    'Conversions': 'sum'
                }).reset_index()
                
                # 派生指標の計算
                cross_stats['CTR'] = (cross_stats['Clicks'] / cross_stats['Impressions'] * 100).round(2)
                cross_stats['CVR'] = (cross_stats['Conversions'] / cross_stats['Clicks'] * 100).round(2)
                cross_stats['CPC'] = (cross_stats['Cost'] / cross_stats['Clicks']).round(0)
                cross_stats['CPA'] = (cross_stats['Cost'] / cross_stats['Conversions']).round(0)
                
                # ラベル変更
                cross_stats.rename(columns={'Keyword': 'キーワード数'}, inplace=True)
                
                # 4. マッチタイプ別集計
                match_type_stats = categorized_data.groupby('MatchType').agg({
                    'Keyword': 'count',
                    'Impressions': 'sum',
                    'Clicks': 'sum',
                    'Cost': 'sum',
                    'Conversions': 'sum'
                }).reset_index()
                
                # 派生指標の計算
                match_type_stats['CTR'] = (match_type_stats['Clicks'] / match_type_stats['Impressions'] * 100).round(2)
                match_type_stats['CVR'] = (match_type_stats['Conversions'] / match_type_stats['Clicks'] * 100).round(2)
                match_type_stats['CPC'] = (match_type_stats['Cost'] / match_type_stats['Clicks']).round(0)
                match_type_stats['CPA'] = (match_type_stats['Cost'] / match_type_stats['Conversions']).round(0)
                
                # ラベル変更
                match_type_stats.rename(columns={'Keyword': 'キーワード数'}, inplace=True)
                
                # 5. 軸カテゴリ×マッチタイプのクロス集計
                axis_match_type_stats = categorized_data.groupby(['AxisCategory', 'MatchType']).agg({
                    'Keyword': 'count',
                    'Impressions': 'sum',
                    'Clicks': 'sum',
                    'Cost': 'sum',
                    'Conversions': 'sum'
                }).reset_index()
                
                # 派生指標の計算
                axis_match_type_stats['CTR'] = (axis_match_type_stats['Clicks'] / axis_match_type_stats['Impressions'] * 100).round(2)
                axis_match_type_stats['CVR'] = (axis_match_type_stats['Conversions'] / axis_match_type_stats['Clicks'] * 100).round(2)
                axis_match_type_stats['CPC'] = (axis_match_type_stats['Cost'] / axis_match_type_stats['Clicks']).round(0)
                axis_match_type_stats['CPA'] = (axis_match_type_stats['Cost'] / axis_match_type_stats['Conversions']).round(0)
                
                # ラベル変更
                axis_match_type_stats.rename(columns={'Keyword': 'キーワード数'}, inplace=True)
                
                # セッションに保存
                st.session_state.category_stats = {
                    'axis': axis_stats,
                    'combination': combination_stats,
                    'cross': cross_stats,
                    'match_type': match_type_stats,
                    'axis_match_type': axis_match_type_stats
                }
        
        # 分析結果の表示
        stats = st.session_state.category_stats
        
        analysis_tab1, analysis_tab2, analysis_tab3, analysis_tab4, analysis_tab5 = st.tabs([
            "軸カテゴリ分析", "掛け合わせカテゴリ分析", "クロス分析", "マッチタイプ分析", "詳細データ探索"
        ])
        
        with analysis_tab1:
            st.markdown("### 軸カテゴリ別パフォーマンス")
            
            # データ表示
            sort_column = st.selectbox("並び替え (軸カテゴリ)", ["Cost", "Conversions", "CPA", "CVR", "キーワード数"])
            sorted_axis_stats = stats['axis'].sort_values(sort_column, ascending=False)
            st.dataframe(sorted_axis_stats)
            
            # グラフ
            fig1 = px.bar(
                sorted_axis_stats, 
                x='AxisCategory', 
                y='Cost', 
                color='Conversions',
                labels={'AxisCategory': '軸カテゴリ', 'Cost': 'コスト', 'Conversions': 'コンバージョン'},
                title='軸カテゴリ別コストとコンバージョン'
            )
            st.plotly_chart(fig1, use_container_width=True)
            
            fig2 = px.scatter(
                sorted_axis_stats, 
                x='CPA', 
                y='CVR', 
                size='Cost',
                color='AxisCategory',
                hover_data=['キーワード数', 'Clicks', 'Conversions'],
                labels={'CPA': 'CPA (円)', 'CVR': 'CVR (%)', 'Cost': 'コスト'},
                title='軸カテゴリ別 CPA vs CVR'
            )
            st.plotly_chart(fig2, use_container_width=True)
        
        with analysis_tab2:
            st.markdown("### 掛け合わせカテゴリ別パフォーマンス")
            
            # データ表示
            sort_column = st.selectbox("並び替え (掛け合わせカテゴリ)", ["Cost", "Conversions", "CPA", "CVR", "キーワード数"])
            sorted_combination_stats = stats['combination'].sort_values(sort_column, ascending=False)
            st.dataframe(sorted_combination_stats)
            
            # グラフ
            fig1 = px.bar(
                sorted_combination_stats, 
                x='CombinationCategory', 
                y='Cost', 
                color='Conversions',
                labels={'CombinationCategory': '掛け合わせカテゴリ', 'Cost': 'コスト', 'Conversions': 'コンバージョン'},
                title='掛け合わせカテゴリ別コストとコンバージョン'
            )
            st.plotly_chart(fig1, use_container_width=True)
            
            fig2 = px.scatter(
                sorted_combination_stats, 
                x='CPA', 
                y='CVR', 
                size='Cost',
                color='CombinationCategory',
                hover_data=['キーワード数', 'Clicks', 'Conversions'],
                labels={'CPA': 'CPA (円)', 'CVR': 'CVR (%)', 'Cost': 'コスト'},
                title='掛け合わせカテゴリ別 CPA vs CVR'
            )
            st.plotly_chart(fig2, use_container_width=True)
        
        with analysis_tab3:
            st.markdown("### 軸×掛け合わせカテゴリのクロス分析")
            
            # 表示する指標の選択
            metric = st.selectbox(
                "表示する指標", 
                ["Cost", "Conversions", "CPA", "CVR", "CTR", "CPC", "キーワード数"]
            )
            
            # ピボットテーブルの作成
            pivot_df = stats['cross'].pivot_table(
                index='AxisCategory',
                columns='CombinationCategory',
                values=metric,
                aggfunc='sum'
            ).fillna(0)
            
            # ヒートマップ
            fig = px.imshow(
                pivot_df,
                labels=dict(x="掛け合わせカテゴリ", y="軸カテゴリ", color=metric),
                x=pivot_df.columns,
                y=pivot_df.index,
                aspect="auto",
                title=f'軸×掛け合わせカテゴリ別 {metric}'
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # データフレーム表示
            st.markdown("#### クロス分析データ")
            st.dataframe(pivot_df)
        
        with analysis_tab4:
            st.markdown("### マッチタイプ別パフォーマンス")
            
            # データ表示
            st.dataframe(stats['match_type'])
            
            # グラフ
            fig1 = px.bar(
                stats['match_type'], 
                x='MatchType', 
                y='Cost', 
                color='Conversions',
                labels={'MatchType': 'マッチタイプ', 'Cost': 'コスト', 'Conversions': 'コンバージョン'},
                title='マッチタイプ別コストとコンバージョン'
            )
            st.plotly_chart(fig1, use_container_width=True)
            
            # 軸カテゴリ×マッチタイプの分析
            st.markdown("### 軸カテゴリ×マッチタイプ")
            
            # 表示する指標の選択
            metric_match = st.selectbox(
                "表示する指標 (マッチタイプ)", 
                ["CPA", "CVR", "CTR", "CPC", "Cost", "Conversions", "キーワード数"]
            )
            
            # ピボットテーブルの作成
            pivot_match_df = stats['axis_match_type'].pivot_table(
                index='AxisCategory',
                columns='MatchType',
                values=metric_match,
                aggfunc='sum'
            ).fillna(0)
            
            # ヒートマップ
            fig_match = px.imshow(
                pivot_match_df,
                labels=dict(x="マッチタイプ", y="軸カテゴリ", color=metric_match),
                x=pivot_match_df.columns,
                y=pivot_match_df.index,
                aspect="auto",
                title=f'軸カテゴリ×マッチタイプ別 {metric_match}'
            )
            st.plotly_chart(fig_match, use_container_width=True)
        
        with analysis_tab5:
            st.markdown("### 詳細データ探索")
            
            # フィルタリングオプション
            col1, col2 = st.columns(2)
            
            with col1:
                selected_axis = st.multiselect(
                    "軸カテゴリ",
                    options=sorted(categorized_data['AxisCategory'].unique()),
                    default=[]
                )
            
            with col2:
                selected_combination = st.multiselect(
                    "掛け合わせカテゴリ",
                    options=sorted(categorized_data['CombinationCategory'].unique()),
                    default=[]
                )
            
            # フィルタリング
            filtered_data = categorized_data.copy()
            
            if selected_axis:
                filtered_data = filtered_data[filtered_data['AxisCategory'].isin(selected_axis)]
            
            if selected_combination:
                filtered_data = filtered_data[filtered_data['CombinationCategory'].isin(selected_combination)]
            
            # データ表示
            st.dataframe(filtered_data.sort_values('Cost', ascending=False))
            
            # CSV出力ボタン
            if st.button("フィルターしたデータをCSVでダウンロード"):
                csv = filtered_data.to_csv(index=False)
                b64 = base64.b64encode(csv.encode()).decode()
                href = f'<a href="data:file/csv;base64,{b64}" download="filtered_keywords.csv">フィルターしたデータをダウンロード</a>'
                st.markdown(href, unsafe_allow_html=True)

# タブ4: レポート
with tab4:
    st.markdown('<div class="sub-header">分析レポート</div>', unsafe_allow_html=True)
    
    if not st.session_state.is_categorized:
        st.warning("先に「キーワードカテゴライズ」タブでカテゴライズを実行してください。")
    elif 'category_stats' not in st.session_state or st.session_state.category_stats is None:
        st.warning("先に「分析結果」タブで分析を実行してください。")
    else:
        # レポート生成
        stats = st.session_state.category_stats
        categorized_data = st.session_state.categorized_data
        
        # レポート生成ボタン
        if st.button("AIを使って分析レポートを生成"):
            if not st.session_state.api_key:
                st.error("OpenAI API Keyが設定されていません。サイドバーで設定してください。")
            else:
                with st.spinner("レポートを生成中..."):
                    try:
                        # API接続テスト
                        try:
                            client = OpenAI(api_key=st.session_state.api_key)
                            test_response = client.chat.completions.create(
                                model="gpt-3.5-turbo",
                                messages=[{"role": "user", "content": "テスト"}],
                                max_tokens=5
                            )
                            debug_info(f"レポート生成前のAPI接続テスト成功: {test_response.choices[0].message.content}")
                        except Exception as e:
                            st.error(f"API接続エラー: {str(e)}")
                            st.stop()
                            
                        # 分析データを準備
                        axis_stats_str = stats['axis'].sort_values('Cost', ascending=False).head(10).to_string()
                        combination_stats_str = stats['combination'].sort_values('Cost', ascending=False).head(10).to_string()
                        match_type_stats_str = stats['match_type'].to_string()
                        
                        # 高効率カテゴリと低効率カテゴリの抽出
                        high_perf_axis = stats['axis'][stats['axis']['Conversions'] >= 5].sort_values('CPA').head(3)
                        low_perf_axis = stats['axis'][stats['axis']['Conversions'] >= 5].sort_values('CPA', ascending=False).head(3)
                        
                        high_perf_axis_str = high_perf_axis.to_string()
                        low_perf_axis_str = low_perf_axis.to_string()
                        
                        # OpenAI APIでレポート生成
                        client = OpenAI(api_key=st.session_state.api_key)
                        
                        prompt = f"""
あなたはリスティング広告の分析専門家です。以下のデータを基に、キーワード分析レポートを作成してください。

サービス概要:
{st.session_state.service_description}

===== 軸カテゴリ別パフォーマンス（コスト上位10カテゴリ） =====
{axis_stats_str}

===== 掛け合わせカテゴリ別パフォーマンス（コスト上位10カテゴリ） =====
{combination_stats_str}

===== マッチタイプ別パフォーマンス =====
{match_type_stats_str}

===== 高効率軸カテゴリ（CPA低順） =====
{high_perf_axis_str}

===== 低効率軸カテゴリ（CPA高順） =====
{low_perf_axis_str}

レポート形式:
1. 全体サマリー - 主要な傾向と発見点の概要
2. 軸カテゴリの分析 - 最も効果的なカテゴリと最適化が必要なカテゴリ
3. 掛け合わせカテゴリの分析 - ユーザー意図に関する洞察
4. マッチタイプの最適化 - マッチタイプ別パフォーマンスと提案
5. 最適化提案 - 具体的な改善アクション（3つ）

分析するポイント:
- コスト効率（CPA）の良いカテゴリと悪いカテゴリの傾向
- コンバージョン率（CVR）に影響を与えている要素
- 予算配分の最適化方法
- キーワードの追加や除外の提案
"""
                        
                        debug_info("レポート生成APIリクエスト実行")
                        
                        response = client.chat.completions.create(
                            model="gpt-4-turbo",
                            messages=[
                                {"role": "system", "content": "You are a PPC advertising specialist with deep expertise in keyword analysis."},
                                {"role": "user", "content": prompt}
                            ],
                            max_tokens=4000,
                            temperature=0.5
                        )
                        
                        report = response.choices[0].message.content
                        
                        debug_info(f"レポート生成完了: {len(report)}文字")
                        
                        # レポート表示
                        st.markdown("## キーワード分析レポート")
                        st.markdown(report)
                        
                        # レポート保存と共有リンク
                        csv = categorized_data.to_csv(index=False)
                        b64 = base64.b64encode(csv.encode()).decode()
                        download_link = f'<a href="data:file/csv;base64,{b64}" download="categorized_keywords.csv" class="download-button">カテゴライズ済みデータをダウンロード</a>'
                        st.markdown(download_link, unsafe_allow_html=True)
                        
                    except Exception as e:
                        st.error(f"レポート生成中にエラーが発生しました: {e}")
                        st.exception(e)
        else:
            st.info("「AIを使って分析レポートを生成」ボタンをクリックすると、データに基づいた詳細な分析レポートが生成されます。")
            
            # サンプル可視化の表示
            st.markdown("### キーワードパフォーマンスの可視化例")
            
            # パフォーマンスマップの表示
            col1, col2 = st.columns(2)
            
            with col1:
                # コスト分布、エラー処理を強化
                try:
                    # トリーマップ作成前にデータをフィルタリング
                    treemap_data = categorized_data.copy()
                    treemap_data = treemap_data[treemap_data['Keyword'].notna() & (treemap_data['Keyword'] != '')]
                    
                    # NaN値を持つ行や計算指標がNaNの行も除外
                    treemap_data = treemap_data.dropna(subset=['Cost', 'CVR'])
                    
                    # データが十分にあるか確認
                    if len(treemap_data) > 0:
                        fig = px.treemap(
                            treemap_data,
                            path=['AxisCategory', 'CombinationCategory', 'Keyword'],
                            values='Cost',
                            color='CVR',
                            color_continuous_scale='RdYlGn',
                            title='カテゴリ別コスト分布 (CVRでカラー表示)'
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.warning("ツリーマップを表示するための有効なデータが不足しています。")
                        
                        # 代替の可視化を表示
                        alt_fig = px.bar(
                            stats['axis'].sort_values('Cost', ascending=False).head(10),
                            x='AxisCategory',
                            y='Cost',
                            color='CVR',
                            title='カテゴリ別コスト分布（上位10カテゴリ）'
                        )
                        st.plotly_chart(alt_fig, use_container_width=True)
                
                except ValueError as ve:
                    st.error(f"ツリーマップの生成中にエラーが発生しました: {str(ve)}")
                    
                    # 代替の可視化を表示
                    st.info("代替の可視化を表示します")
                    
                    # 横棒グラフでカテゴリ別コスト表示
                    alt_fig = px.bar(
                        stats['axis'].sort_values('Cost', ascending=False).head(10),
                        x='Cost',
                        y='AxisCategory',
                        orientation='h',
                        color='CVR',
                        title='軸カテゴリ別コスト分布（上位10カテゴリ）'
                    )
                    st.plotly_chart(alt_fig, use_container_width=True)
                
                except Exception as e:
                    st.error(f"可視化中にエラーが発生しました: {str(e)}")
                    st.warning("個別の分析タブで詳細なデータをご確認ください。")
            
            with col2:
                # パフォーマンスマップ - こちらも念のためエラーハンドリング追加
                try:
                    # データをフィルタリング
                    scatter_data = categorized_data[categorized_data['Clicks'] > min_clicks].copy()
                    
                    # NaN値をドロップ
                    scatter_data = scatter_data.dropna(subset=['CPA', 'CVR', 'Cost', 'AxisCategory'])
                    
                    if len(scatter_data) > 0:
                        fig = px.scatter(
                            scatter_data,
                            x='CPA',
                            y='CVR',
                            size='Cost',
                            color='AxisCategory',
                            hover_name='Keyword',
                            log_x=True,
                            title='キーワードパフォーマンスマップ'
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.warning("散布図を表示するためのデータが不足しています。")
                        
                        # 代替の散布図を単純化して表示
                        simple_fig = px.scatter(
                            stats['axis'],
                            x='CPA',
                            y='CVR',
                            size='Cost',
                            color='AxisCategory',
                            title='カテゴリレベルのパフォーマンスマップ'
                        )
                        st.plotly_chart(simple_fig, use_container_width=True)
                        
                except Exception as e:
                    st.error(f"散布図生成中にエラーが発生しました: {str(e)}")
                    
                    # 代替の視覚化
                    try:
                        simple_fig = px.scatter(
                            stats['axis'],
                            x='CPA',
                            y='CVR',
                            size='Cost',
                            title='カテゴリレベルのパフォーマンスマップ'
                        )
                        st.plotly_chart(simple_fig, use_container_width=True)
                    except:
                        st.warning("データの視覚化ができませんでした。個別の分析タブで詳細な情報をご確認ください。")
            
            # クイック洞察
            st.markdown("### クイック洞察")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # 高効率カテゴリ
                try:
                    high_performing = stats['axis'][
                        (stats['axis']['Conversions'] > 0) & 
                        (stats['axis']['キーワード数'] >= 3)
                    ].nsmallest(5, 'CPA')
                    
                    st.markdown("#### 最も効率の良い軸カテゴリ (CPA順)")
                    st.dataframe(high_performing[['AxisCategory', 'Cost', 'Conversions', 'CPA', 'CVR']])
                except Exception as e:
                    st.warning(f"効率の良いカテゴリの表示中にエラーが発生しました: {e}")
            
            with col2:
                # 低効率カテゴリ
                try:
                    low_performing = stats['axis'][
                        (stats['axis']['Conversions'] > 0) & 
                        (stats['axis']['Cost'] > kw_min_cost) & 
                        (stats['axis']['キーワード数'] >= 3)
                    ].nlargest(5, 'CPA')
                    
                    st.markdown("#### 効率改善の余地がある軸カテゴリ (CPA降順)")
                    st.dataframe(low_performing[['AxisCategory', 'Cost', 'Conversions', 'CPA', 'CVR']])
                except Exception as e:
                    st.warning(f"改善候補カテゴリの表示中にエラーが発生しました: {e}")
            
            # 分析事例
            st.markdown("### 分析例")
            st.markdown("""
            #### キーワード最適化に向けた一般的なアプローチ
            1. **効率の良いカテゴリへの予算シフト**
               - 高CVR・低CPAのカテゴリを特定し、入札単価を調整
               - コンバージョンが見込めるカテゴリへの予算最適化
            
            2. **低効率キーワードの改善または除外**
               - 高コスト・低コンバージョンのキーワードを特定
               - マッチタイプの調整や除外キーワードの追加を検討
            
            3. **新規キーワードの発見**
               - 効率の良いカテゴリからのアイデア抽出
               - 競合分析による新規開拓
            """)

# マッピング情報のフッター（デバッグ用）
if DEBUG and st.session_state.column_mapping is not None:
    with st.expander("🔍 フィールドマッピング情報", expanded=False):
        st.json(st.session_state.column_mapping)

# フッター
st.markdown("---")
st.markdown("リスティング広告キーワード分析システム | Ver 1.0")