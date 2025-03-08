# column_mapper.py - 列名マッピング機能

import streamlit as st
from openai import OpenAI
import pandas as pd
import json
import difflib

# 標準的なフィールド名と説明（日本語も追加）
STANDARD_FIELDS = {
    'Keyword': ['キーワード', 'keywords', 'search term', '検索語句', 'query'],
    'MatchType': ['マッチタイプ', 'match type', 'match', 'matching', 'タイプ', '一致タイプ'],
    'Impressions': ['imp', 'imps', 'impression', 'インプレッション', '表示回数', '表示数', '露出数'],
    'Clicks': ['click', 'クリック', 'クリック数', 'クリック回数', 'click count'],
    'Cost': ['コスト', 'cost', '費用', '金額', 'spend', '支出'],
    'Conversions': ['conversion', 'conv', 'コンバージョン', '成約', 'cv', 'CVs', 'GACV'],
    'CampaignName': ['キャンペーン名', 'campaign', 'キャンペーン', 'campaign name', 'キャンペーンネーム'],
    'AdGroupName': ['広告グループ名', 'adgroup', 'ad group', '広告グループ', 'group name', 'グループ名']
}

# 必須フィールド
REQUIRED_FIELDS = ['Keyword', 'MatchType', 'Impressions', 'Clicks', 'Cost', 'Conversions']

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
        import re
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
            return None
        
        # 最終マッピングを反転（元の列名→標準列名）してDataFrameに適用
        inverse_mapping = {v: k for k, v in selected_mapping.items()}
        mapped_df = df.rename(columns=inverse_mapping)
        
        # 必要な列だけを残す
        required_cols = list(selected_mapping.keys())
        mapped_df = mapped_df[required_cols]
        
        st.success("列名のマッピングが完了しました！")
        return mapped_df
    
    return None