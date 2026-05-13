# core/data_processor.py

import pandas as pd
import json
import os
from core.scoring_logic import AssortmentScorer

class DataProcessor:
    def __init__(self):
        self.scorer = AssortmentScorer()
        self.config_path = os.path.join("core", "config", "target_ratios.json")
        self.target_ratios = self._load_config()
        self.item_ui_labels = {
            "Outer": "아우터",
            "Top": "상의",
            "Bottom": "하의",
            "Skirt": "스커트",
            "Dress": "원피스"
        }

    def _load_config(self):
        """JSON 설정 파일 로드"""
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def calculate_category_score(self, df: pd.DataFrame, category: str, zoning: str):
        """
        [v4.0] 조닝별 아이템 구성비 및 달성률 계산 로직
        - Target: target_ratios.json 기준값
        - Actual: 현재 DB 재고 금액(stock_amt) 기준 비중
        """
        if df is None or df.empty:
            return None

        # 1. 아이템 그룹 매핑
        df = df.copy()
        df['mapped_group'] = df.apply(
            lambda row: self.scorer._get_item_group(
                str(row.get('item_code', row.get('style_code', ''))).strip()
            ), axis=1
        )

        # 2. 유효 그룹 필터링 (기타 항목 제외)
        valid_groups = list(self.item_ui_labels.keys())
        filtered_df = df[df['mapped_group'].isin(valid_groups)].copy()
        
        if filtered_df.empty:
            return None

        # 3. 조닝별/아이템별 집계
        # 특정 조닝에 대한 가이드라인 가져오기 (하드코딩 지양)
        category_config = self.target_ratios.get(category, {})
        target_dict = category_config.get(zoning, {})
        
        if not target_dict:
            return None

        # 실제 비중 계산
        total_amt = filtered_df['stock_amt'].sum()
        grouped = filtered_df.groupby('mapped_group')['stock_amt'].sum().reset_index()
        grouped['actual_pct'] = (grouped['stock_amt'] / total_amt)
        
        # 목표 비중 매핑 및 달성률 계산
        analysis_rows = []
        for eng_name, kor_name in self.item_ui_labels.items():
            actual_row = grouped[grouped['mapped_group'] == eng_name]
            actual_val = actual_row['actual_pct'].values[0] if not actual_row.empty else 0.0
            actual_amt = actual_row['stock_amt'].values[0] if not actual_row.empty else 0
            target_val = target_dict.get(eng_name, 0.0)
            
            # 달성률: (실제/목표) * 100. 목표가 0인 경우 처리
            achievement = (actual_val / target_val * 100) if target_val > 0 else 0.0
            
            analysis_rows.append({
                "아이템명": kor_name,
                "재고금액": actual_amt,
                "현재비중": f"{actual_val*100:.1f}%",
                "목표비중": f"{target_val*100:.1f}%",
                "달성률": f"{achievement:.1f}%",
                "_achievement_raw": achievement, # 정렬용
                "_amt_raw": actual_amt
            })

        # 4. 상위 아이템 분석 (재고금액 순 정렬 및 순위 부여)
        result_df = pd.DataFrame(analysis_rows)
        result_df = result_df.sort_values("_amt_raw", ascending=False).reset_index(drop=True)
        result_df.insert(0, "순위", result_df.index + 1)

        return result_df.drop(columns=["_achievement_raw", "_amt_raw"])

    def get_item_analysis_data(self, df: pd.DataFrame, category: str, zoning: str):
        """기존 시각화 호환용 (필요시 유지)"""
        return self.calculate_category_score(df, category, zoning)
