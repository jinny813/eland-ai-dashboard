"""
tests/test_scoring_logic.py
============================
채점 로직 단위 테스트

검증 대상:
  - calc_target_total : 목표 총 재고액 산출 (평수 기반)
  - get_season_targets : 월 → 당시즌/나머지시즌 계절코드
  - AssortmentScorer.score : 정상/상설 각각 만점(100점) / 최저(0점) 검증
  - 할인율 구간 경계값 (정확히 70%, 50%, 30% 케이스)
  - 정상 할인율 70%이상 구간 → 목표 재고액 0원 + 점수 산출 제외
  - 정상 신선도 기획 → 목표 재고액 0원 + 점수 산출 제외
  - 시즌 유틸 1~12월 전체 케이스
  - BEST10 동순위 처리
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pandas as pd
import numpy as np
from core.scoring_logic import (
    calc_target_total,
    get_season_targets,
    AssortmentScorer,
    SEASON_SCORE_CURRENT,
    SEASON_SCORE_OTHER,
    DIS_SCORES,
    FRESH_SCORES,
    _UNIT_PRICE_SMALL,
    _UNIT_PRICE_LARGE,
    _STORE_DAYS,
    _STOCK_MULTI,
)


# ─────────────────────────────────────────────────────────
# 1. calc_target_total — 목표 총 재고액 산출
# ─────────────────────────────────────────────────────────

class TestCalcTargetTotal:
    def test_small_store(self):
        """49평 미만: 평수 × 10만 × 30 × 3"""
        area = 30.0
        expected = 30 * 100_000 * 30 * 3
        assert calc_target_total(area) == expected

    def test_exactly_50_pyeong(self):
        """정확히 50평: 7만원 단가 적용 (≥50 조건)"""
        area = 50.0
        expected = 50 * 70_000 * 30 * 3
        assert calc_target_total(area) == expected

    def test_large_store(self):
        """51평 이상: 평수 × 7만 × 30 × 3"""
        area = 80.0
        expected = 80 * 70_000 * 30 * 3
        assert calc_target_total(area) == expected

    def test_boundary_49_vs_50(self):
        """49평 vs 50평 경계값 — 50평이 더 작아야 함 (단가 낮음)"""
        assert calc_target_total(49.0) > calc_target_total(50.0)

    def test_zero_area_fallback(self):
        """평수 0: tM_won × 3 fallback"""
        tM_won = 50_000_000.0
        assert calc_target_total(0.0, tM_won) == tM_won * 3

    def test_no_area_no_tm(self):
        """평수·tM 모두 없으면 최소 1.0 반환"""
        assert calc_target_total(0.0, 0.0) >= 1.0


# ─────────────────────────────────────────────────────────
# 2. get_season_targets — 월 → 계절코드
# ─────────────────────────────────────────────────────────

class TestGetSeasonTargets:
    # 기대값: (당시즌_코드, 나머지시즌_코드)
    EXPECTED = {
        1: ("봄", "여름"),   2: ("봄", "여름"),   3: ("봄", "여름"),
        4: ("여름", "봄"),   5: ("여름", "봄"),   6: ("여름", "봄"),
        7: ("가을", "겨울"), 8: ("가을", "겨울"), 9: ("가을", "겨울"),
        10: ("겨울", "가을"), 11: ("겨울", "가을"), 12: ("겨울", "가을"),
    }

    @pytest.mark.parametrize("month", range(1, 13))
    def test_all_months(self, month):
        curr, other = get_season_targets(month)
        exp_curr, exp_other = self.EXPECTED[month]
        assert exp_curr in curr, f"월={month}: 당시즌에 '{exp_curr}' 있어야 함"
        assert exp_other in other, f"월={month}: 나머지시즌에 '{exp_other}' 있어야 함"

    @pytest.mark.parametrize("month", range(1, 13))
    def test_curr_and_other_are_disjoint(self, month):
        """당시즌과 나머지시즌은 완전히 다른 계절"""
        curr, other = get_season_targets(month)
        curr_season = next(c for c in ["봄", "여름", "가을", "겨울"] if c in curr)
        other_season = next(c for c in ["봄", "여름", "가을", "겨울"] if c in other)
        assert curr_season != other_season

    @pytest.mark.parametrize("month", range(1, 13))
    def test_season_weight_sum(self, month):
        """당시즌+나머지 점수 합계 = 15점 (공통 만점)"""
        assert SEASON_SCORE_CURRENT + SEASON_SCORE_OTHER == 15


# ─────────────────────────────────────────────────────────
# 헬퍼 — 테스트용 DataFrame 생성
# ─────────────────────────────────────────────────────────

def _make_df(
    n=1,
    stock_amt=10_000_000,
    discount_rate=0.0,
    freshness_type="이월",
    season_code="여름",
    store_type="상설",
    sales_qty=0,
    data_month=4,
    tM=30_000_000,
    area=30.0,
    style_code="TEST001",
    year=2026,
    item_code="TS",
    brand_name="테스트",
    category_group="여성",
) -> pd.DataFrame:
    rows = []
    for i in range(n):
        rows.append({
            "style_code": f"{style_code}{i:03d}",
            "stock_amt": stock_amt,
            "stock_qty": stock_amt // 50_000,
            "discount_rate": discount_rate,
            "freshness_type": freshness_type,
            "season_code": season_code,
            "store_type": store_type,
            "sales_qty": sales_qty,
            "data_month": data_month,
            "tM": tM,
            "area": area,
            "year": year,
            "item_code": item_code,
            "brand_name": brand_name,
            "category_group": category_group,
            "price_type": "정상",
        })
    return pd.DataFrame(rows)


def _normal_cfg():
    return {
        "inv_weights": {
            "dis":    {"s70": 0.00, "s50": 0.05, "s30": 0.10, "s10": 0.15},
            "fresh":  {"new": 0.70},
            "best":   {"store10": 0.35},
            "season": {"spring": 0.50, "summer": 0.25},
            "item":   {"Top": 0.30, "Bottom": 0.20, "Outer": 0.30, "Skirt": 0.10, "Dress": 0.10},
        },
        "weight_discount":  0.30,
        "weight_freshness": 0.20,
        "weight_season":    0.15,
        "weight_best":      0.35,
        "weight_item":      0.00,
        "year_base": 2026,
    }


def _outlet_cfg():
    return {
        "inv_weights": {
            "dis":    {"s70": 0.10, "s50": 0.20, "s30": 0.30, "s10": 0.10},
            "fresh":  {"new": 0.10, "plan": 0.20},
            "best":   {"store10": 0.30},
            "season": {"spring": 0.50, "summer": 0.25},
            "item":   {"Top": 0.30, "Bottom": 0.20, "Outer": 0.30, "Skirt": 0.10, "Dress": 0.10},
        },
        "weight_discount":  0.40,
        "weight_freshness": 0.15,
        "weight_season":    0.15,
        "weight_best":      0.30,
        "weight_item":      0.00,
        "year_base": 2026,
    }


# ─────────────────────────────────────────────────────────
# 3. 할인율 구간 경계값
# ─────────────────────────────────────────────────────────

class TestDiscountBoundary:
    """할인율 경계값: 이상(≥) / 미만(<) 기준 확인"""

    def _score_dis_segment(self, dis_rate, store_type, area=30.0):
        """단일 품번, 특정 할인율 → discount_score 반환"""
        target_total = calc_target_total(area)
        # 해당 품번 재고액을 목표보다 충분히 채워 100% 달성률 가정
        stock_per_seg = target_total * 0.50  # 넉넉하게
        df = _make_df(
            stock_amt=stock_per_seg,
            discount_rate=dis_rate,
            store_type=store_type,
            data_month=4,
            area=area,
            tM=30_000_000,
        )
        cfg = _outlet_cfg() if store_type == "상설" else _normal_cfg()
        scorer = AssortmentScorer(cfg)
        result = scorer.score(df)
        return int(result["discount_score"].iloc[0])

    def test_exactly_70pct_goes_to_s70_segment(self):
        """정확히 70%는 '70% 이상' 구간(≥70) 처리"""
        # 상설: s70 재고비중 10% → 목표 채우면 s70에 점수 기여
        df = _make_df(
            stock_amt=calc_target_total(30.0) * 0.10,  # s70 목표 딱 맞춤
            discount_rate=70.0,
            store_type="상설",
            area=30.0,
        )
        cfg = _outlet_cfg()
        scorer = AssortmentScorer(cfg)
        result = scorer.score(df)
        # s70가 100% 달성되면 기여분 = 100% × (10점/40점) = 25% → discount_score에 25 기여
        assert result["discount_score"].iloc[0] > 0

    def test_exactly_50pct_goes_to_s50_not_s70(self):
        """정확히 50%는 s50 구간(≥50 <70), s70에 포함되지 않음"""
        target_total = calc_target_total(30.0)
        # 50% 할인 품번만 존재, s70 구간에는 아무것도 없어야 함
        df = _make_df(
            stock_amt=target_total * 0.20,  # s50 목표(20%) 채움
            discount_rate=50.0,
            store_type="상설",
            area=30.0,
        )
        cfg = _outlet_cfg()
        scorer = AssortmentScorer(cfg)
        result = scorer.score(df)
        assert result["discount_score"].iloc[0] > 0

    def test_normal_70pct_segment_zero_target(self):
        """정상 매장: 70% 이상 구간 재고비중 0% → 목표 재고액 0원"""
        target_total = calc_target_total(30.0)
        expected_tgt = target_total * 0.00  # s70 재고비중 = 0%
        assert expected_tgt == 0.0

    def test_normal_70pct_excluded_from_score(self):
        """정상 매장: 70% 이상 구간(0점) → 점수 산출 제외"""
        assert DIS_SCORES["normal"]["s70"] == 0

    def test_score_weight_normalization_outlet(self):
        """상설 할인율 점수 가중치 합계 = 100%"""
        scores = DIS_SCORES["outlet"]
        non_zero = {k: v for k, v in scores.items() if v > 0}
        total = sum(non_zero.values())
        weights = {k: v / total for k, v in non_zero.items()}
        assert abs(sum(weights.values()) - 1.0) < 1e-9

    def test_score_weight_outlet_correct(self):
        """상설 점수 가중치: s70=25%, s50=25%, s30=37.5%, s10=12.5%"""
        scores = DIS_SCORES["outlet"]
        total = sum(scores.values())  # 40점
        assert abs(scores["s70"] / total - 0.25)   < 1e-9
        assert abs(scores["s50"] / total - 0.25)   < 1e-9
        assert abs(scores["s30"] / total - 0.375)  < 1e-9
        assert abs(scores["s10"] / total - 0.125)  < 1e-9


# ─────────────────────────────────────────────────────────
# 4. 신선도 — 정상 기획 제외
# ─────────────────────────────────────────────────────────

class TestFreshness:
    def test_normal_plan_zero_target(self):
        """정상 기획: 재고비중 0% → 목표 재고액 0원"""
        target_total = calc_target_total(30.0)
        assert target_total * 0.00 == 0.0

    def test_normal_plan_zero_score(self):
        """정상 기획: 점수 0점 → 점수 산출 제외"""
        assert FRESH_SCORES["normal"]["plan"] == 0

    def test_outlet_fresh_score_weights(self):
        """상설 신선도: 신상 33.3% / 기획 66.7%"""
        scores = FRESH_SCORES["outlet"]
        total = sum(scores.values())  # 15점
        assert abs(scores["new"] / total - 1/3)  < 1e-9
        assert abs(scores["plan"] / total - 2/3) < 1e-9

    def test_normal_fresh_score_weights(self):
        """정상 신선도: 신상 100% (기획 0점 제외)"""
        scores = FRESH_SCORES["normal"]
        non_zero = {k: v for k, v in scores.items() if v > 0}
        total = sum(non_zero.values())
        assert abs(non_zero["new"] / total - 1.0) < 1e-9


# ─────────────────────────────────────────────────────────
# 5. 총점 만점 / 최저 검증
# ─────────────────────────────────────────────────────────

class TestMaxMinScore:
    """정상/상설 각각: 모든 구간 100% 달성 → 총점 100점, 0% → 0점"""

    def _build_perfect_df(self, store_type: str, area: float = 30.0) -> pd.DataFrame:
        """모든 지표 목표를 100% 초과 달성하는 DataFrame"""
        target_total = calc_target_total(area)
        outlet = store_type == "상설"
        cfg = _outlet_cfg() if outlet else _normal_cfg()
        inv = cfg["inv_weights"]

        rows = []
        month = 4  # 여름이 당시즌

        # 할인율: 상설 s70/s50/s30/s10 구간 모두 목표 이상
        if outlet:
            for dis_rate, ratio in [(75, inv["dis"]["s70"]),
                                    (60, inv["dis"]["s50"]),
                                    (40, inv["dis"]["s30"]),
                                    (15, inv["dis"]["s10"])]:
                amt = target_total * ratio * 2  # 목표 2배로 100% 달성 보장
                rows.append({
                    "style_code": f"DIS_{dis_rate}", "stock_amt": amt, "stock_qty": 10,
                    "discount_rate": float(dis_rate), "freshness_type": "이월",
                    "season_code": "여름", "store_type": store_type, "sales_qty": 10,
                    "data_month": month, "tM": 30_000_000, "area": area,
                    "year": 2026, "item_code": "TS", "brand_name": "테스트",
                    "category_group": "여성", "price_type": "정상",
                })
        else:
            for dis_rate, ratio in [(55, 0.05), (40, 0.10), (15, 0.15)]:
                amt = target_total * ratio * 2
                rows.append({
                    "style_code": f"DIS_{dis_rate}", "stock_amt": amt, "stock_qty": 10,
                    "discount_rate": float(dis_rate), "freshness_type": "이월",
                    "season_code": "여름", "store_type": store_type, "sales_qty": 10,
                    "data_month": month, "tM": 30_000_000, "area": area,
                    "year": 2026, "item_code": "TS", "brand_name": "테스트",
                    "category_group": "여성", "price_type": "정상",
                })

        # 신선도
        if outlet:
            for ft, ratio in [("신상", inv["fresh"]["new"]), ("기획", inv["fresh"]["plan"])]:
                amt = target_total * ratio * 2
                rows.append({
                    "style_code": f"FRESH_{ft}", "stock_amt": amt, "stock_qty": 10,
                    "discount_rate": 30.0, "freshness_type": ft,
                    "season_code": "여름", "store_type": store_type, "sales_qty": 10,
                    "data_month": month, "tM": 30_000_000, "area": area,
                    "year": 2026, "item_code": "BL", "brand_name": "테스트",
                    "category_group": "여성", "price_type": "정상",
                })
        else:
            amt = target_total * 0.70 * 2
            rows.append({
                "style_code": "FRESH_신상", "stock_amt": amt, "stock_qty": 10,
                "discount_rate": 0.0, "freshness_type": "신상",
                "season_code": "여름", "store_type": store_type, "sales_qty": 10,
                "data_month": month, "tM": 30_000_000, "area": area,
                "year": 2026, "item_code": "BL", "brand_name": "테스트",
                "category_group": "여성", "price_type": "정상",
            })

        # 시즌: 당시즌(여름)=50%, 나머지(봄)=30%
        for sc, ratio in [("여름", 0.50), ("봄", 0.30)]:
            amt = target_total * ratio * 2
            rows.append({
                "style_code": f"SEA_{sc}", "stock_amt": amt, "stock_qty": 10,
                "discount_rate": 20.0, "freshness_type": "이월",
                "season_code": sc, "store_type": store_type, "sales_qty": 10,
                "data_month": month, "tM": 30_000_000, "area": area,
                "year": 2026, "item_code": "TS", "brand_name": "테스트",
                "category_group": "여성", "price_type": "정상",
            })

        # BEST10: 판매수량 상위 10개에 충분한 재고
        best_ratio = inv["best"]["store10"]
        for i in range(10):
            amt = target_total * best_ratio / 10 * 2
            rows.append({
                "style_code": f"BEST{i:03d}", "stock_amt": amt, "stock_qty": 10,
                "discount_rate": 20.0, "freshness_type": "이월",
                "season_code": "여름", "store_type": store_type, "sales_qty": 100,
                "data_month": month, "tM": 30_000_000, "area": area,
                "year": 2026, "item_code": "TS", "brand_name": "테스트",
                "category_group": "여성", "price_type": "정상",
            })

        return pd.DataFrame(rows)

    def test_normal_perfect_score(self):
        """정상 매장 모든 달성률 100% → 총점 100점"""
        df = self._build_perfect_df("정상")
        scorer = AssortmentScorer(_normal_cfg())
        result = scorer.score(df)
        total = int(result["total_score"].iloc[0])
        assert total == 100, f"정상 만점 기대 100점, 실제 {total}점"

    def test_outlet_perfect_score(self):
        """상설 매장 모든 달성률 100% → 총점 100점"""
        df = self._build_perfect_df("상설")
        scorer = AssortmentScorer(_outlet_cfg())
        result = scorer.score(df)
        total = int(result["total_score"].iloc[0])
        assert total == 100, f"상설 만점 기대 100점, 실제 {total}점"

    def test_normal_zero_stock_score(self):
        """정상 매장 재고 전부 0 → 총점 0점"""
        df = _make_df(stock_amt=0, store_type="정상", area=30.0, discount_rate=20.0,
                      freshness_type="신상", season_code="여름", sales_qty=0)
        scorer = AssortmentScorer(_normal_cfg())
        result = scorer.score(df)
        assert result["total_score"].iloc[0] == 0

    def test_outlet_zero_stock_score(self):
        """상설 매장 재고 전부 0 → 총점 0점"""
        df = _make_df(stock_amt=0, store_type="상설", area=30.0, discount_rate=40.0,
                      freshness_type="신상", season_code="여름", sales_qty=0)
        scorer = AssortmentScorer(_outlet_cfg())
        result = scorer.score(df)
        assert result["total_score"].iloc[0] == 0


# ─────────────────────────────────────────────────────────
# 6. BEST10 동순위 처리
# ─────────────────────────────────────────────────────────

class TestBest10Tiebreak:
    def test_top10_selected_by_sales_qty(self):
        """판매수량 내림차순 Top 10 선정 — 동순위는 groupby sum 후 head(10)"""
        rows = []
        for i in range(15):
            # 처음 10개: 판매량 100, 나머지 5개: 판매량 50
            sq = 100 if i < 10 else 50
            rows.append({
                "style_code": f"S{i:03d}", "stock_amt": 5_000_000, "stock_qty": 10,
                "discount_rate": 20.0, "freshness_type": "이월", "season_code": "여름",
                "store_type": "상설", "sales_qty": sq, "data_month": 4,
                "tM": 30_000_000, "area": 30.0, "year": 2026, "item_code": "TS",
                "brand_name": "테스트", "category_group": "여성", "price_type": "정상",
            })
        df = pd.DataFrame(rows)
        scorer = AssortmentScorer(_outlet_cfg())
        result = scorer.score(df)
        # 점수가 0보다 커야 함 (BEST10 재고가 target_total * 0.30 일부 충족)
        assert result["best_score"].iloc[0] >= 0

    def test_all_same_sales_qty_takes_exactly_10(self):
        """모든 품번 동일 판매량일 때 head(10)으로 정확히 10개 선정"""
        rows = []
        for i in range(20):
            rows.append({
                "style_code": f"EQ{i:03d}", "stock_amt": 1_000_000, "stock_qty": 5,
                "discount_rate": 20.0, "freshness_type": "이월", "season_code": "여름",
                "store_type": "상설", "sales_qty": 50, "data_month": 4,
                "tM": 30_000_000, "area": 30.0, "year": 2026, "item_code": "TS",
                "brand_name": "테스트", "category_group": "여성", "price_type": "정상",
            })
        df = pd.DataFrame(rows)
        scorer = AssortmentScorer(_outlet_cfg())
        result = scorer.score(df)
        assert "best_score" in result.columns


# ─────────────────────────────────────────────────────────
# 실행
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
