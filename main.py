"""
main.py — Streamlit 메인 앱 v2
================================
[변경 내역]
- SmartBrandDetector 통합: 업로드 시 법인 자동 인식 결과 표시
- 브랜드 scoring config 키를 '카테고리_매장유형_브랜드명' 형식으로 통일
- 업로드 탭 UX 개선: 자동인식 → 확인 → 업로드 플로우
- [v160] P1 뷰에 st.tabs() 적용: 대시보드 탭 / 노출/측정판 다운로드 탭 분리
"""

import streamlit as st
import json
import sys
import logging
from datetime import datetime
import pandas as pd
import io

import importlib

logger = logging.getLogger(__name__)
import core.report_generator
from core.report_generator import dashboard_fingerprint

# ── 엑셀 보고서 로직 버전 (코드 변경시 반드시 올릴 것 → 캐시 자동 무효화) ──
REPORT_VERSION = "v17.22"

# [v100.1] Windows 콘솔 인코딩 대응
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from core.data_manager import DataManager
from database.gsheet_manager import GSheetManager


def _json_default(o):
    if hasattr(o, "__float__") and type(o).__module__ == "numpy":
        return float(o)
    return str(o)


def serialize_dashboard_json(db_data: dict) -> str:
    """JSON 직렬화 — ensure_ascii=True로 비ASCII 문자를 유니코드 이스케이프 (atob 호환)"""
    return json.dumps(db_data, ensure_ascii=True, default=_json_default)




@st.cache_data(ttl=600, max_entries=2, show_spinner="노출판 엑셀 생성 중...")
def generate_optimized_excel(
    store_filter: str,
    cat_filter: str,
    metrics_key: str,
    data_fingerprint: str,
    dashboard_json: str,
    report_version: str = REPORT_VERSION,  # 버전 변경 시 캐시 자동 무효화
):
    del data_fingerprint, report_version  # 캐시 키로만 사용
    if not dashboard_json:
        return None
    
    # ── [v7] report_generator 모듈 강제 리로드하여 실시간 코드 수정 즉시 반영 ──
    importlib.reload(core.report_generator)
    
    data = json.loads(dashboard_json)
    metrics = [m.strip() for m in metrics_key.split(",") if m.strip()]
    return core.report_generator.export_to_excel_bytes(
        data=data,
        store_filter=store_filter,
        cat_filter=cat_filter,
        metrics_filter=metrics or None,
    )


@st.cache_data(ttl=600, max_entries=2, show_spinner="영업 실행판 엑셀 생성 중...")
def generate_sales_execution_excel(
    store_filter: str,
    cat_filter: str,
    metrics_key: str,
    data_fingerprint: str,
    dashboard_json: str,
    report_version: str = REPORT_VERSION,
):
    del data_fingerprint, report_version
    if not dashboard_json:
        return None
    importlib.reload(core.report_generator)
    data = json.loads(dashboard_json)
    metrics = [m.strip() for m in metrics_key.split(",") if m.strip()]
    return core.report_generator.export_sales_execution_excel_bytes(
        data=data,
        store_filter=store_filter,
        cat_filter=cat_filter,
        metrics_filter=metrics or None,
    )


@st.cache_data(ttl=3600, max_entries=2, show_spinner="구글 시트에서 데이터 로드 중...")
def _cached_get_raw_records(_mgr, max_no: int):
    try:
        sheet = _mgr.spreadsheet.worksheet("Records")
        return sheet.get_all_records()
    except Exception as e:
        logger.error(f"[Records] Fetch failed: {e}")
        return []


@st.cache_data(ttl=600, max_entries=2, show_spinner="데이터 전처리 중 (1회)...")
def _cached_preprocess(_mgr, max_no: int, report_version: str = REPORT_VERSION):
    """
    [Stage 1 캐시] 전처리.
    캐시 키: max_no, report_version. TTL 만료 시 자동 재실행.
    """
    import importlib, sys
    for _m in ['core.data_loader']:
        if _m in sys.modules:
            importlib.reload(sys.modules[_m])
    from core.data_loader import preprocess_raw_records
    raw_recs = _cached_get_raw_records(_mgr, max_no)
    return preprocess_raw_records(_mgr, raw_recs)


@st.cache_data(ttl=600, max_entries=3, show_spinner="월별 점수 산출 중...")
def _cached_build_month(_mgr, max_no: int, month: str, report_version: str = REPORT_VERSION):
    """
    [Stage 2 캐시] 월별 대시보드 빌드.
    캐시 키: (max_no, month, report_version). 월별 독립 엔트리 유지.
    """
    import importlib, sys
    for _m in ['core.data_loader']:
        if _m in sys.modules:
            importlib.reload(sys.modules[_m])
    from core.data_loader import load_dashboard_data
    preprocessed = _cached_preprocess(_mgr, max_no, report_version=report_version)
    return load_dashboard_data(
        mgr=_mgr,
        selected_month=month,
        _preprocessed=preprocessed,
    )


@st.cache_data(ttl=600, max_entries=2, show_spinner=False)
def _cached_get_max_no(_mgr):
    try:
        val = _mgr._get_max_no()
        return val if val and val > 0 else 1
    except Exception:
        return 1


@st.cache_data(ttl=600, max_entries=2, show_spinner=False)
def _cached_get_available_months(_mgr, max_no: int):
    """캐시 키: max_no."""
    try:
        import unicodedata
        months = set()
        raw_recs = _cached_get_raw_records(_mgr, max_no)
        if raw_recs:
            for r in raw_recs:
                m = str(r.get('data_month', '')).strip()
                if m:
                    m_nfc = unicodedata.normalize('NFC', m)
                    months.add(m_nfc)

        def _get_m_num(m_str):
            try:
                return int(str(m_str).replace('월', '').strip())
            except Exception:
                return 0

        return sorted(list(months), key=_get_m_num, reverse=True)
    except Exception as e:
        logger.error(f"[Months] Fetch failed: {e}")
        return []


def cached_load_all_dashboard_data(mgr, available_months):
    """모든 가용 월 데이터를 로드. GSheet 로드 실패 시 로컬 dashboard_backup.json 폴백 작동."""
    max_no = _cached_get_max_no(mgr)
    cache_key = f"last_valid_all_dashboard_data_{max_no}_{len(available_months)}_{REPORT_VERSION}"

    # [BUG-FIX] 이전에 저장된 에러 dict({"error": ...})가 truthy여서 재반환되던 문제 수정
    cached = st.session_state.get(cache_key)
    if cached and isinstance(cached, dict) and "error" not in cached:
        return cached

    all_data = {}
    try:
        if not available_months:
            raise ValueError("Empty available months from GSheet")
            
        for m in available_months:
            res = _cached_build_month(mgr, max_no, m, report_version=REPORT_VERSION)
            if res and isinstance(res, dict) and "error" not in res:
                all_data[m] = res

        if not all_data:
            raise ValueError("No valid dashboard data found for any month from GSheet")

        st.session_state[cache_key] = all_data
        return all_data
    except Exception as e:
        logger.warning(f"[Cache] GSheet 로드 실패 ({e}) — 로컬 백업 파일 폴백 시도")
        import os
        base_dir = os.path.dirname(os.path.abspath(__file__))
        backup_path = os.path.join(base_dir, "data", "dashboard_backup.json")
        if os.path.exists(backup_path):
            try:
                with open(backup_path, "r", encoding="utf-8") as f:
                    backup_data = json.load(f)
                if backup_data and isinstance(backup_data, dict) and "error" not in backup_data:
                    logger.info("✅ [Fallback] 로컬 dashboard_backup.json 복원 성공! (3배수 및 평수 연동 수동 보정 중...)")
                    # 동적 평수 갱신을 위해 storemaster load 시도
                    import config.area_config as _cfg_area
                    from core.data_loader import preprocess_raw_records
                    try:
                        preprocess_raw_records(mgr, [])
                    except Exception as _pe:
                        logger.error(f"[Fallback Patch] storemaster 로드 오류: {_pe}")
                    
                    # 데이터 보정 루프
                    from config.area_config import get_area
                    from config.brand_targets import get_tm
                    for m_key, m_val in backup_data.items():
                        if not isinstance(m_val, dict):
                            continue
                        brands_list = m_val.get("BRANDS", [])
                        for b_data in brands_list:
                            store = b_data.get("store")
                            b_name = b_data.get("name")
                            if not store or not b_name:
                                continue
                            area = get_area(store, b_name)
                            b_data["area"] = area
                            
                            tM_won = get_tm(brand_name=b_name, store_name=store, month=m_key)
                            b_data["tM"] = round(tM_won / 1_000_000, 1)
                            
                            if area > 0:
                                tM_inv_won = area * 100_000.0 * 30.0 * 3.0
                            else:
                                tM_inv_won = tM_won * 3.0
                            b_data["tM_inv"] = round(tM_inv_won / 1_000_000, 1)
                            
                            sM = b_data.get("sM", 0.0)
                            if b_data["tM_inv"] > 0:
                                b_data["inv_reached_pct"] = round((sM / b_data["tM_inv"]) * 100)
                            else:
                                b_data["inv_reached_pct"] = 0
                                
                    st.session_state[cache_key] = backup_data
                    return backup_data
                else:
                    logger.error("[Fallback] 백업 파일이 비었거나 에러 상태입니다.")
            except Exception as fe:
                logger.error(f"[Fallback] 로컬 백업 파일 로드 실패: {fe}")
                
        return {"error": f"전체 데이터 로드 실패 (상세: {e})"}




def parse_text_to_df(text_data: str) -> pd.DataFrame:
    """텍스트 붙여넣기(Tab 구분) → DataFrame 변환"""
    if not text_data.strip():
        return None
    try:
        return pd.read_csv(io.StringIO(text_data), sep='\t')
    except Exception as e:
        st.error(f"텍스트 파싱 오류: {e}")
        return None


def get_gsheet_manager():
    """[v100.4] 매번 최신 로직을 반영하도록 객체 생성 시 시트명을 명시적으로 지정"""
    return GSheetManager(sheet_name="Records")


def _show_detector_result(result: dict):
    """SmartBrandDetector 결과를 UI에 뱃지 형태로 표시"""
    company = result.get('company', 'Generic')
    confidence = result.get('confidence', 'low')
    reason = result.get('reason', '')

    badge_colors = {'high': '🟢', 'medium': '🟡', 'low': '🔴'}
    icon = badge_colors.get(confidence, '⚪')

    company_label = {
        'ElandWorld': '이랜드월드 (로엠·미쏘)',
        'IndongFN': '인동FN (리스트·쉬즈미스)',
        'BabaGroup': '바바그룹 (JJ지고트·바바팩토리)',
        'LotteGFR': '롯데GFR (나이스클랍)',
        'Generic': '법인 미상 (범용 파서 사용)',
    }.get(company, company)

    st.info(f"{icon} **법인 자동인식**: {company_label}\n\n📋 {reason}")


def main():
    # [v18.1] 긴급 패치: 사용자 환경의 고착화된 세션 캐시(빈 화면/에러) 완벽 해제
    if 'overwrite_approval' not in st.session_state:
        st.session_state.overwrite_approval = {}

    if "last_valid_dashboard_data" in st.session_state and not st.session_state["last_valid_dashboard_data"]:
        del st.session_state["last_valid_dashboard_data"]

    # [v112.0] 브랜드 맵핑 데이터
    CATEGORY_BRAND_MAP = {
        "여성": [
            "로엠 (정상)", "미쏘 (정상)", "더아이잗 (정상)", "에잇컨셉 (정상)",
            "리스트 (상설)", "쉬즈미스 (상설)", "클라비스 (상설)", "나이스클랍 (상설)",
            "JJ지고트 (상설)", "바바팩토리 (상설)", "베네통 (상설)", "시슬리 (상설)",
            "비씨비지 (상설)", "발렌시아 (상설)", "베스띠벨리 (상설)", "올리비아로렌 (상설)",
            "제시뉴욕 (상설)", "샤틴 (상설)", "보니스팍스 (상설)", "안지크 (상설)",
            "플라스틱아일랜드 (상설)"
        ],
        "스포츠": [
            "스케쳐스 (정상)", "아디다스 (정상)", "뉴발란스 (정상)", "나이키 (정상)"
        ]
    }

    # [v90.0] 프리미엄 UI 설정
    st.set_page_config(
        page_title="E·LAND AI 상품구색 진단 시스템",
        page_icon="🎯",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

    # ━━━ CSS Injection ━━━
    st.markdown("""
        <style>
        #MainMenu {visibility: hidden;}
        header {visibility: hidden;}
        footer {visibility: hidden;}
        .block-container {
            padding: 0rem !important;
            max-width: 100% !important;
            margin: 0 !important;
        }
        iframe {
            width: 100vw !important;
            min-height: 100vh !important;
            border: none !important;
        }
        [data-testid="stSidebar"] {
            background-color: #f8f9fa;
        }
        [data-testid="stAppViewContainer"] {
            overflow-y: auto !important;
        }
        .main {
            overflow: visible !important;
        }
        /* 탭 스타일 프리미엄 개선 */
        [data-testid="stTabs"] [data-baseweb="tab-list"] {
            gap: 8px;
            padding: 8px 16px 8px 16px;
            background: #ffffff;
            border-bottom: 2px solid #E30019; /* 이랜드 브랜드 레드 컬러 */
            border-radius: 4px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            margin-bottom: 20px;
        }
        [data-testid="stTabs"] [data-baseweb="tab"] {
            font-weight: 700;
            font-size: 14px;
            color: #4B5563;
            border-radius: 4px;
            padding: 8px 16px;
            transition: all 0.2s ease-in-out;
        }
        [data-testid="stTabs"] [data-baseweb="tab"]:hover {
            color: #E30019;
            background: #FEF2F2;
        }
        [data-testid="stTabs"] [aria-selected="true"] {
            color: #E30019 !important;
            background: #FEF2F2 !important;
        }
        </style>
    """, unsafe_allow_html=True)

    check_mgr = get_gsheet_manager()

    # ━━━ 사이드바 네비게이션 역할 분리 ━━━
    # 기본은 대시보드만 공개, URL에 ?role=admin이 있거나 비밀 패스코드를 입력하면 관리자 기능 활성화
    is_admin = st.query_params.get("role") == "admin"
    
    # 세션 상태로 관리자 모드 유지
    if "admin_mode" not in st.session_state:
        st.session_state.admin_mode = is_admin

    menu_options = ["📊 실시간 대시보드"]
    
    if st.session_state.admin_mode:
        menu_options += [
            "📤 데이터 업로드",
            "📂 RAW 데이터 업로드",
            "📄 노출/측정판 다운로드",
        ]

    with st.sidebar:
        st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/2/23/E-Land_Group_logo.svg/1024px-E-Land_Group_logo.svg.png", width=120)
        
        if st.session_state.admin_mode:
            st.title("Admin Menu")
        else:
            st.title("Dashboard Menu")

        menu = st.radio(
            "이동",
            menu_options,
            index=0,
            label_visibility="collapsed",
        )
        st.markdown("---")
        
        # 관리자 비밀 모드 진입용 패스워드 (비밀코드: elandkpi!)
        if not st.session_state.admin_mode:
            with st.expander("🔐 관리자 모드"):
                passkey = st.text_input("접속 비밀번호", type="password", key="admin_passkey")
                if passkey == "elandkpi!":
                    st.session_state.admin_mode = True
                    st.success("관리자 권한 획득!")
                    st.rerun()
        else:
            if st.button("🔒 관리자 로그아웃", use_container_width=True):
                st.session_state.admin_mode = False
                st.query_params.clear()
                st.rerun()

        # [v7.1] 캐시 강제 초기화 버튼 (모든 사용자에게 항시 노출)
        if st.button("\U0001f504 캐시 초기화 (신규 지점 반영)", use_container_width=True):
            st.cache_data.clear()
            # [BUG-FIX] last_valid_all_dashboard_data_* 포함 모든 캐시 키 삭제
            stale_keys = [k for k in list(st.session_state.keys()) if k.startswith('last_valid')]
            for _k in stale_keys:
                del st.session_state[_k]
            st.success("\u2705 캐시 초기화 완료! 페이지를 새로고침하세요.")
            st.rerun()

        st.caption(f"DB Connected: {check_mgr.is_connected}")



    # ────────────────────────────────────────────
    # 뷰 1: 실시간 대시보드 (기본 화면)
    # ────────────────────────────────────────────
    if menu == "📊 실시간 대시보드":
        if not check_mgr.is_connected:
            st.error("구글 시트 연동 오류입니다.")
        else:
            try:
                # [v183] 대시보드 로딩 속도를 SPA 급으로 개선하기 위해 모든 월 데이터를 한 번에 로드
                max_no = _cached_get_max_no(check_mgr)
                available_months = _cached_get_available_months(check_mgr, max_no)
                
                all_months_data = cached_load_all_dashboard_data(check_mgr, available_months)

                if "error" in all_months_data:
                    st.error(f"❌ 데이터 빌드 실패: {all_months_data['error']}")
                else:
                    # ── [역할 분리] 일반 사용자는 대시보드 탭 자체를 노출하지 않고 즉시 렌더링 ──
                    if st.session_state.admin_mode:
                        tab_dash, tab_dl = st.tabs(["📊 대시보드", "📄 노출/측정판 다운로드"])
                    else:
                        tab_dash = st.container()
                        tab_dl = None

                    # ── 탭 1: 대시보드 iframe (SPA 렌더링) ──
                    with tab_dash:
                        template_path = "ui/dashboard_template.html"
                        with open(template_path, "r", encoding="utf-8") as f:
                            html_template = f.read()

                        all_data_json = serialize_dashboard_json(all_months_data)
                        # [v201] Base64 인코딩으로 HTML 파서 </script> 오인식 작동 완전 차단
                        import base64
                        b64_data = base64.b64encode(all_data_json.encode('utf-8')).decode('ascii')
                        script_inject = (
                            f'<script id="__b64" type="text/plain">{b64_data}</script>\n'
                            f'<script>window.__ALL_DATA__ = JSON.parse(atob(document.getElementById("__b64").textContent));</script>\n'
                        )
                        final_html = html_template.replace("<script>", script_inject + "<script>", 1)
                        st.components.v1.html(final_html, height=1600, scrolling=True)
                        st.markdown('<div style="margin-bottom: 100px;"></div>', unsafe_allow_html=True)

                    # ── 탭 2: 노출/측정판 다운로드 (가장자리 여백 2.5rem 추가 확보) ──
                    if tab_dl is not None:
                        with tab_dl:
                            st.markdown('<div style="padding: 2.5rem 2rem 2rem 2rem;">', unsafe_allow_html=True)
                            st.markdown("#### 📄 노출/측정판 다운로드")
                            st.caption("지점·카테고리·지표를 선택한 후 엑셀을 다운로드하세요.")
                            
                            # 다운로드용 기준 월 분리 선택
                            dl_month = st.selectbox("📅 다운로드 기준 데이터 월", available_months, key="tab_dl_month_selector")
                            db_data = all_months_data.get(dl_month, {})
                            data_fp = dashboard_fingerprint(db_data)
                            dashboard_json = serialize_dashboard_json(db_data)
                            
                            st.markdown("---")
                            # [v172] 라디오 버튼 제거 및 공식 st.tabs 서브탭 레이아웃 적용
                            subtab_p1, subtab_p2, subtab_p3 = st.tabs([
                                "🏬 지점별 상품 구색 점수판 다운로드",
                                "👚 매장별 상세 현황판 다운로드",
                                "📊 상품구색 실행판(영업)"
                            ])

                            with subtab_p1:
                                st.markdown("<div style='padding: 1rem 0;'>", unsafe_allow_html=True)
                                st.info("💡 카테고리를 선택하시면 지점별 상세 노출/측정 지표가 브랜드 항목 없이 집계되어 다운로드됩니다.")
                                
                                cats = ["전체 카테고리"] + list(db_data.get("CATS", []))
                                p1_cat = st.selectbox("👚 카테고리 선택 (지점별 상품 구색 점수판)", cats, key="tab_dl_p1_cat")
                                
                                score_mode_sel = st.selectbox(
                                    "⚖️ 환산 기준 선택",
                                    ["지표별 가중치 반영", "지표별 100점 환산 기준"],
                                    key="tab_dl_p1_score_mode"
                                )
                                score_mode_param = "100_percent" if score_mode_sel == "지표별 100점 환산 기준" else "weighted"

                                sel_metrics_p1 = st.multiselect(
                                    "📊 포함할 지표 선택 (지점별 상품 구색 점수판)",
                                    ["할인율", "BEST상품", "신선도", "시즌", "아이템"],
                                    default=["할인율", "BEST상품", "신선도", "시즌", "아이템"],
                                    key="tab_dl_p1_metrics"
                                )
                                
                                col_p1_btn1, col_p1_btn2 = st.columns(2)
                                with col_p1_btn1:
                                    dl_p1_excel = st.button("🚀 요약 엑셀 파일 생성", key="tab_dl_p1_gen_excel", use_container_width=True)
                                with col_p1_btn2:
                                    dl_p1_ppt = st.button("🚀 요약 PPT 파일 생성", key="tab_dl_p1_gen_ppt", use_container_width=True)
                                
                                if dl_p1_excel:
                                    with st.spinner("지점별 카테고리 요약 엑셀 생성 중..."):
                                        import core.report_generator as rg
                                        if score_mode_param == "100_percent":
                                            excel_data = rg.export_p1_dashboard_excel_bytes(db_data, p1_cat, metrics_filter=sel_metrics_p1)
                                            dl_filename = f"지점별_카테고리_100점대시보드_{p1_cat}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
                                        else:
                                            excel_data = rg.export_p1_summary_excel_bytes(db_data, p1_cat, metrics_filter=sel_metrics_p1, score_mode=score_mode_param)
                                            dl_filename = f"지점별_카테고리_요약점수_현황_{p1_cat}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
                                        if excel_data:
                                            st.success(f"✅ {dl_filename} 생성 완료!")
                                            st.download_button(
                                                label="📄 요약 엑셀 다운로드",
                                                data=excel_data,
                                                file_name=dl_filename,
                                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                                use_container_width=True,
                                            )
                                        else:
                                            st.warning("데이터가 없습니다.")

                                if dl_p1_ppt:
                                    with st.spinner("지점별 카테고리 요약 PPT 생성 중..."):
                                        import core.ppt_generator as ptg
                                        if score_mode_param == "100_percent":
                                            ppt_data = ptg.export_p1_dashboard_ppt_bytes(db_data, p1_cat, metrics_filter=sel_metrics_p1)
                                            dl_filename = f"지점별_카테고리_100점대시보드_{p1_cat}_{datetime.now().strftime('%Y%m%d_%H%M')}.pptx"
                                        else:
                                            ppt_data = ptg.export_p1_summary_ppt_bytes(db_data, p1_cat, metrics_filter=sel_metrics_p1, score_mode=score_mode_param)
                                            dl_filename = f"지점별_카테고리_요약점수_현황_{p1_cat}_{datetime.now().strftime('%Y%m%d_%H%M')}.pptx"
                                        if ppt_data:
                                            st.success(f"✅ {dl_filename} 생성 완료!")
                                            st.download_button(
                                                label="📄 요약 PPT 다운로드",
                                                data=ppt_data,
                                                file_name=dl_filename,
                                                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                                                use_container_width=True,
                                            )
                                        else:
                                            st.warning("데이터가 없습니다.")
                                st.markdown("</div>", unsafe_allow_html=True)

                            with subtab_p2:
                                st.markdown("<div style='padding: 1rem 0;'>", unsafe_allow_html=True)
                                stores = ["전체 지점"] + list(db_data.get("STORES", []))
                                cats = ["전체 카테고리"] + list(db_data.get("CATS", []))

                                col1, col2 = st.columns(2)
                                with col1:
                                    sel_store = st.selectbox("🏬 지점 선택", stores, key="tab_dl_p2_store")
                                with col2:
                                    sel_cat = st.selectbox("👚 카테고리 선택", cats, key="tab_dl_p2_cat")

                                col_m, col_sc = st.columns([3, 2])
                                with col_m:
                                    sel_metrics = st.multiselect(
                                        "📊 지표 선택",
                                        ["할인율", "BEST상품", "신선도", "시즌", "아이템"],
                                        default=["할인율", "BEST상품", "신선도", "시즌", "아이템"],
                                        key="tab_dl_p2_metrics",
                                    )
                                with col_sc:
                                    p2_score_mode_sel = st.selectbox(
                                        "⚖️ 환산 기준",
                                        ["지표별 가중치 반영", "지표별 100점 환산"],
                                        key="tab_dl_p2_p2_score_mode",
                                    )
                                metrics_key = ",".join(sel_metrics) if sel_metrics else "할인율,BEST상품,신선도,시즌,아이템"

                                st.markdown("---")
                                if p2_score_mode_sel == "지표별 100점 환산":
                                    col_p2_e, col_p2_p = st.columns(2)
                                    with col_p2_e:
                                        dl_p2_excel = st.button("🚀 100점 엑셀 생성", key="tab_dl_p2_p2_dash_excel", use_container_width=True)
                                    with col_p2_p:
                                        dl_p2_ppt = st.button("🚀 100점 PPT 생성", key="tab_dl_p2_p2_dash_ppt", use_container_width=True)

                                    if dl_p2_excel:
                                        with st.spinner("브랜드 100점 대시보드 엑셀 생성 중..."):
                                            import core.report_generator as rg
                                            excel_data = rg.export_p2_dashboard_excel_bytes(db_data, sel_store, sel_cat, metrics_filter=sel_metrics)
                                            now_str = datetime.now().strftime("%Y%m%d_%H%M")
                                            dl_filename = f"브랜드_100점대시보드_{sel_store}_{sel_cat}_{now_str}.xlsx"
                                            if excel_data:
                                                st.success(f"✅ {dl_filename} 생성 완료!")
                                                st.download_button(
                                                    label="📄 100점 엑셀 다운로드",
                                                    data=excel_data,
                                                    file_name=dl_filename,
                                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                                    use_container_width=True,
                                                )
                                            else:
                                                st.warning("⚠️ 선택한 조건에 해당하는 데이터가 없습니다.")

                                    if dl_p2_ppt:
                                        with st.spinner("브랜드 100점 대시보드 PPT 생성 중..."):
                                            import core.ppt_generator as ptg
                                            ppt_data = ptg.export_p2_dashboard_ppt_bytes(db_data, sel_store, sel_cat, metrics_filter=sel_metrics)
                                            now_str = datetime.now().strftime("%Y%m%d_%H%M")
                                            dl_filename = f"브랜드_100점대시보드_{sel_store}_{sel_cat}_{now_str}.pptx"
                                            if ppt_data:
                                                st.success(f"✅ {dl_filename} 생성 완료!")
                                                st.download_button(
                                                    label="📄 100점 PPT 다운로드",
                                                    data=ppt_data,
                                                    file_name=dl_filename,
                                                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                                                    use_container_width=True,
                                                )
                                            else:
                                                st.warning("⚠️ 선택한 조건에 해당하는 데이터가 없습니다.")
                                else:
                                    if st.button("🚀 상세 엑셀 파일 생성", key="tab_dl_p2_gen", use_container_width=True):
                                        excel_data = generate_optimized_excel(
                                            sel_store, sel_cat, metrics_key, data_fp, dashboard_json, REPORT_VERSION
                                        )
                                        if excel_data:
                                            now_str = datetime.now().strftime("%Y%m%d_%H%M")
                                            dl_filename = f"상품구색_노출판_{sel_store}_{sel_cat}_{now_str}.xlsx"
                                            st.success(f"✅ {dl_filename} 생성 완료!")
                                            st.download_button(
                                                label="📄 노출/측정판 엑셀 다운로드",
                                                data=excel_data,
                                                file_name=dl_filename,
                                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                                use_container_width=True,
                                            )
                                        else:
                                            st.warning("⚠️ 선택한 조건에 해당하는 데이터가 없습니다.")
                                st.markdown("</div>", unsafe_allow_html=True)
                            st.markdown('</div>', unsafe_allow_html=True)



                            with subtab_p3:
                                st.markdown("<div style='padding: 1rem 0;'>", unsafe_allow_html=True)
                                stores = ["전체 지점"] + list(db_data.get("STORES", []))
                                cats = ["전체 카테고리"] + list(db_data.get("CATS", []))

                                col1, col2 = st.columns(2)
                                with col1:
                                    sel_store = st.selectbox("🏬 지점 선택", stores, key="tab_dl_p3_store")
                                with col2:
                                    sel_cat = st.selectbox("👚 카테고리 선택", cats, key="tab_dl_p3_cat")

                                col_m, col_sc = st.columns([3, 2])
                                with col_m:
                                    sel_metrics = st.multiselect(
                                        "📊 지표 선택",
                                        ["할인율", "BEST상품", "신선도", "시즌", "아이템"],
                                        default=["할인율", "BEST상품", "신선도", "시즌", "아이템"],
                                        key="tab_dl_p3_metrics",
                                    )
                                with col_sc:
                                    p2_score_mode_sel = st.selectbox(
                                        "⚖️ 환산 기준",
                                        ["지표별 가중치 반영", "지표별 100점 환산"],
                                        key="tab_dl_p3_p2_score_mode",
                                    )
                                metrics_key = ",".join(sel_metrics) if sel_metrics else "할인율,BEST상품,신선도,시즌,아이템"

                                st.markdown("---")
                                if p2_score_mode_sel == "지표별 100점 환산":
                                    col_p2_e, col_p2_p = st.columns(2)
                                    with col_p2_e:
                                        dl_p2_excel = st.button("🚀 100점 엑셀 생성", key="tab_dl_p3_p2_dash_excel", use_container_width=True)
                                    with col_p2_p:
                                        dl_p2_ppt = st.button("🚀 100점 PPT 생성", key="tab_dl_p3_p2_dash_ppt", use_container_width=True)

                                    if dl_p2_excel:
                                        with st.spinner("브랜드 100점 대시보드 엑셀 생성 중..."):
                                            import core.report_generator as rg
                                            excel_data = rg.export_p2_dashboard_excel_bytes(db_data, sel_store, sel_cat, metrics_filter=sel_metrics)
                                            now_str = datetime.now().strftime("%Y%m%d_%H%M")
                                            dl_filename = f"브랜드_100점대시보드_{sel_store}_{sel_cat}_{now_str}.xlsx"
                                            if excel_data:
                                                st.success(f"✅ {dl_filename} 생성 완료!")
                                                st.download_button(
                                                    label="📄 100점 엑셀 다운로드",
                                                    data=excel_data,
                                                    file_name=dl_filename,
                                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                                    use_container_width=True,
                                                )
                                            else:
                                                st.warning("⚠️ 선택한 조건에 해당하는 데이터가 없습니다.")

                                    if dl_p2_ppt:
                                        with st.spinner("브랜드 100점 대시보드 PPT 생성 중..."):
                                            import core.ppt_generator as ptg
                                            ppt_data = ptg.export_p2_dashboard_ppt_bytes(db_data, sel_store, sel_cat, metrics_filter=sel_metrics)
                                            now_str = datetime.now().strftime("%Y%m%d_%H%M")
                                            dl_filename = f"브랜드_100점대시보드_{sel_store}_{sel_cat}_{now_str}.pptx"
                                            if ppt_data:
                                                st.success(f"✅ {dl_filename} 생성 완료!")
                                                st.download_button(
                                                    label="📄 100점 PPT 다운로드",
                                                    data=ppt_data,
                                                    file_name=dl_filename,
                                                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                                                    use_container_width=True,
                                                )
                                            else:
                                                st.warning("⚠️ 선택한 조건에 해당하는 데이터가 없습니다.")
                                else:
                                    if st.button("🚀 상세 엑셀 파일 생성", key="tab_dl_p3_gen", use_container_width=True):
                                        excel_data = generate_sales_execution_excel(
                                            sel_store, sel_cat, metrics_key, data_fp, dashboard_json, REPORT_VERSION
                                        )
                                        if excel_data:
                                            now_str = datetime.now().strftime("%Y%m%d_%H%M")
                                            dl_filename = f"상품구색_실행판(영업)_{sel_store}_{sel_cat}_{now_str}.xlsx"
                                            st.success(f"✅ {dl_filename} 생성 완료!")
                                            st.download_button(
                                                label="📄 노출/측정판 엑셀 다운로드",
                                                data=excel_data,
                                                file_name=dl_filename,
                                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                                use_container_width=True,
                                            )
                                        else:
                                            st.warning("⚠️ 선택한 조건에 해당하는 데이터가 없습니다.")
                                st.markdown("</div>", unsafe_allow_html=True)
                            st.markdown('</div>', unsafe_allow_html=True)



                            st.markdown('</div>', unsafe_allow_html=True)
            except Exception as e:
                st.error(f"대시보드 생성 실패: {e}")

    # ────────────────────────────────────────────
    # 뷰 2: 데이터 통합 및 업로드 (관리자 전용)
    # ────────────────────────────────────────────
    elif menu == "📤 데이터 업로드":
        st.markdown("<div style='padding: 2rem;'>", unsafe_allow_html=True)
        st.title("📤 데이터 통합 및 업로드")
        st.info("안내에 따라 순서대로 [지점 → 카테고리 → 브랜드 → 월]을 선택하고 파이프라인을 활성화해주세요.")

        selected_store = selected_category = selected_brand = selected_type = selected_month = None

        col_store, col_cat = st.columns(2)
        with col_store:
            st.caption("🏬 1. 진단 지점")
            # [v162] clean_store_name 표준 유틸리티 로컬 정의
            def clean_store_name(name: str) -> str:
                """NC/뉴코아/동아/2001 수식어를 완벽하게 제거하고 지점명을 표준명(점포명)으로 정규화"""
                if not name:
                    return ""
                name = str(name).strip()
                name = name.replace("(진척중)", "").replace("[진척중]", "").replace("진척중", "").strip()
                for prefix in ["NC", "뉴코아", "동아", "2001"]:
                    if name.startswith(prefix):
                        name = name[len(prefix):].strip()
                        break
                if '분당' in name:
                    name = '분당점'
                elif '강남' in name:
                    name = '강남점'
                elif name == '불광':
                    name = '불광점'
                elif name == '쇼핑':
                    name = '쇼핑점'
                return name

            # [v162] officemaster 동적 연동 및 지점명 리스트 추출
            try:
                df_office = check_mgr.load_office_master()
                store_list_set = set(clean_store_name(s) for s in df_office['지점명'] if s)
            except Exception as e:
                _fallback_raw = [
                    'NC신구로점', 'NC강서점', 'NC송파점', 'NC불광점', 'NC고잔점',
                    'NC평촌점', 'NC야탑점', 'NC청주점', '뉴코아강남점', '뉴코아부천점',
                    '뉴코아인천점', '2001중계점', '2001분당점', '동아쇼핑점',
                    '동아수성점', 'NC대전유성점', 'NC광명점', 'NC산본점',
                    'NC일산점', 'NC부평점', '뉴코아동수원점', '뉴코아수원터미널점',
                    'NC평택점', 'NC천호점'
                ]
                store_list_set = set(clean_store_name(s) for s in _fallback_raw)

            # [v.xxx] Override 기반 로컬 추가 지점 반영 (ex. 인천점)
            try:
                from config.storemaster_override import STORE_AREA
                for s in STORE_AREA.keys():
                    store_list_set.add(clean_store_name(s))
            except Exception:
                pass
            
            store_list = sorted(list(store_list_set))

            raw = st.selectbox("지점", store_list,
                               index=None, placeholder="진단할 지점을 선택하세요...", label_visibility="collapsed")
            if raw: selected_store = raw

        with col_cat:
            st.caption("👚 2. 카테고리")
            if selected_store:
                raw = st.selectbox("카테고리", ['여성', '스포츠', '신사', '아동', '캐주얼', '잡화'],
                                   index=None, placeholder="진단할 카테고리를 선택하세요...", label_visibility="collapsed")
                if raw: selected_category = raw
            else:
                st.selectbox("카테고리", ["👈 지점을 먼저 선택하세요"], disabled=True, label_visibility="collapsed")

        col_brand, col_month = st.columns(2)
        with col_brand:
            st.caption("🏷️ 3. 대상 브랜드(매장유형)")
            if selected_category:
                base_list = CATEGORY_BRAND_MAP.get(selected_category, [])
                brand_list = base_list + ["직접 입력(범용)"]

                raw = st.selectbox("브랜드", brand_list, index=None, placeholder="브랜드를 선택하세요...", label_visibility="collapsed")
                if raw:
                    if "(" in raw and "범용" not in raw:
                        selected_brand = raw.split(' ')[0]
                        selected_type = "정상" if "정상" in raw else "상설"
                    else:
                        selected_brand = raw
                        selected_type = st.radio("매장 유형 선택", ["정상", "상설"], horizontal=True)
            else:
                st.selectbox("브랜드", ["👈 카테고리를 먼저 선택하세요"], disabled=True, label_visibility="collapsed")

        with col_month:
            st.caption("📅 4. 대상 월(Month)")
            if selected_brand:
                month_list = [f"{m}월" for m in range(1, 13)]
                raw = st.selectbox("월", month_list, index=datetime.now().month - 1, label_visibility="collapsed")
                if raw: selected_month = raw
            else:
                st.selectbox("월", ["👈 브랜드를 먼저 선택하세요"], disabled=True, label_visibility="collapsed")

        if selected_store and selected_category and selected_brand and selected_type and selected_month:
            st.markdown("---")
            state_key = f"{selected_store}_{selected_brand}_{selected_month}"

            if check_mgr.is_connected:
                is_dup = check_mgr.check_existing_data(selected_store, selected_category, selected_brand, selected_month)
            else:
                is_dup = False

            if is_dup and not st.session_state.overwrite_approval.get(state_key, False):
                st.warning("⚠️ 이미 저장된 데이터 입니다.")
                if st.button("기존 데이터 수정/업데이트 승인", type="primary"):
                    st.session_state.overwrite_approval[state_key] = True
                    st.rerun()
            else:
                subtab_file, subtab_text = st.tabs(["📂 Excel 파일 업로드", "📋 데이터 직접 붙여넣기(Text)"])
                inv_data = sales_data = None

                with subtab_file:
                    col_inv, col_sales = st.columns(2)
                    with col_inv:
                        uf_inv = st.file_uploader(f"[{selected_brand}] 재고조회 파일", type=['xls', 'xlsx'], key=f"inv_{state_key}")
                    with col_sales:
                        uf_sales = st.file_uploader(f"[{selected_brand}] 판매조회 파일", type=['xls', 'xlsx'], key=f"sales_{state_key}")

                    if uf_inv:
                        try:
                            from core.smart_brand_detector import SmartBrandDetector
                            detector = SmartBrandDetector()
                            detector_result = detector.detect(uf_inv, file_name=uf_inv.name)
                            _show_detector_result(detector_result)
                        except: pass

                    if uf_inv and uf_sales:
                        inv_data, sales_data = uf_inv, uf_sales

                with subtab_text:
                    st.caption("💡 엑셀에서 헤더(첫 줄)를 포함하여 전체 범위를 복사해서 아래에 붙여넣으세요.")
                    text_inv = st.text_area(f"[{selected_brand}] 재고 텍스트 (품번, 수량, 금액 등 포함)", height=150)
                    text_sales = st.text_area(f"[{selected_brand}] 판매 텍스트 (품번, 수량, 금액 등 포함)", height=150)
                    if text_inv:
                        inv_data = parse_text_to_df(text_inv)
                    if text_sales:
                        sales_data = parse_text_to_df(text_sales)

                if st.button("DB 업로드 실행", type="primary", use_container_width=True):
                    if inv_data is None or sales_data is None:
                        st.warning("데이터를 입력해주세요.")
                    else:
                        try:
                            dm = DataManager()
                            with st.spinner("데이터 병합 및 업로드 중..."):
                                final_df = dm.process_and_merge(selected_brand, selected_store, selected_category, selected_type, selected_month, inv_data, sales_data)
                                if final_df is not None and not final_df.empty:
                                    if is_dup: is_saved = check_mgr.overwrite_record(final_df, selected_store, selected_brand, selected_month)
                                    else: is_saved = check_mgr.append_record(final_df)

                                    if is_saved:
                                        st.success(f"🎊 {len(final_df)}행 저장 완료!")
                                        st.cache_data.clear()
                                        with st.expander("📊 업로드 데이터 미리보기 (상위 5행)", expanded=True):
                                            st.dataframe(final_df.head(5), use_container_width=True)
                                        st.session_state.overwrite_approval.pop(state_key, None)
                                    else:
                                        st.error(f"DB 저장 실패: {check_mgr.error_msg}")
                        except Exception as e:
                            st.error(f"오류: {e}")
        st.markdown("</div>", unsafe_allow_html=True)

    # ────────────────────────────────────────────
    # 뷰 3: RAW 데이터 업로드
    # ────────────────────────────────────────────
    elif menu == "📂 RAW 데이터 업로드":
        st.markdown("<div style='padding: 2rem;'>", unsafe_allow_html=True)
        st.title("📂 RAW 데이터 업로드")
        st.subheader("상품 정보 입력 RAW")
        st.info("스타일 마스터 및 상품 기준 정보를 업로드하여 시스템의 자동 인식 기능을 강화합니다.")
        st.markdown("---")

        subtab_file, subtab_text = st.tabs(["📂 마스터 파일 업로드", "📋 상품 정보 직접 입력"])

        with subtab_file:
            st.caption("💡 품번, 상품명, 복종, 소재 등이 포함된 엑셀 파일을 업로드하세요.")
            master_file = st.file_uploader("상품 마스터 엑셀 업로드", type=['xls', 'xlsx'], key="master_upload")

            if master_file:
                try:
                    df_master = pd.read_excel(master_file)
                    st.write("업로드 데이터 미리보기:")
                    st.dataframe(df_master.head(5), use_container_width=True)

                    if st.button("마스터 DB 반영 (Bulk)", type="primary"):
                        with st.spinner("상품 정보를 정규화하여 DB에 반영 중..."):
                            import sqlite3
                            db_path = "database/product_master.db"
                            conn = sqlite3.connect(db_path)
                            df_db = df_master.copy()
                            df_db.to_sql('products', conn, if_exists='append', index=False)
                            conn.close()
                            st.success(f"{len(df_db)}건의 상품 정보가 성공적으로 반영되었습니다.")
                except Exception as e:
                    st.error(f"파일 처리 오류: {e}")

        with subtab_text:
            st.caption("💡 특정 스타일의 정보를 개별적으로 수정하거나 입력할 때 사용합니다.")
            style_input = st.text_input("스타일 코드(품번)")
            name_input = st.text_input("상품명")
            cat_input = st.selectbox("카테고리", ["여성", "스포츠", "신사", "아동", "캐주얼", "잡화"])

            if st.button("개별 정보 업데이트"):
                if not style_input:
                    st.warning("스타일 코드를 입력하세요.")
                else:
                    try:
                        import sqlite3
                        conn = sqlite3.connect("database/product_master.db")
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT OR REPLACE INTO products (style_code, product_name, category, updated_at)
                            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                        """, (style_input, name_input, cat_input))
                        conn.commit()
                        conn.close()
                        st.success(f"[{style_input}] 정보가 업데이트 되었습니다.")
                    except Exception as e:
                        st.error(f"DB 업데이트 실패: {e}")
        st.markdown("</div>", unsafe_allow_html=True)

    # ────────────────────────────────────────────
    # 뷰 4: 노출/측정판 다운로드 (독립 화면)
    # ────────────────────────────────────────────
    elif menu == "📄 노출/측정판 다운로드":
        st.title("📄 노출/측정판 다운로드")
        st.caption("지점 카테고리 지표 요약을 선택하여 엑셀 보고서를 다운로드합니다.")
        st.markdown("---")

        if not check_mgr.is_connected:
            st.error("구글 시트 연동 오류입니다.")
        else:
            try:
                max_no = _cached_get_max_no(check_mgr)
                raw_recs = _cached_get_raw_records(check_mgr, max_no)
                available_months = _cached_get_available_months(check_mgr, max_no, raw_recs)
                all_months_data = cached_load_all_dashboard_data(check_mgr, available_months, raw_recs)

                if "error" in all_months_data:
                    st.error(f"데이터 로드 실패: {all_months_data['error']}")
                elif not available_months:
                    st.info("현재 데이터가 없습니다. 데이터를 업로드해 주세요.")
                else:
                    dl_month = st.selectbox("📅 다운로드 기준 데이터 월", available_months, key="p4_dl_month_selector")
                    db_data = all_months_data.get(dl_month, {})
                    data_fp = dashboard_fingerprint(db_data)
                    dashboard_json = serialize_dashboard_json(db_data)

                    # [v172] 라디오 버튼 제거 및 공식 st.tabs 서브탭 레이아웃 적용
                    subtab_p1, subtab_p2 = st.tabs([
                        "🏬 지점 요약 점수 다운로드 (P1 스타일)",
                        "👚 브랜드 상세 노출판 다운로드 (P2 상세)"
                    ])

                    with subtab_p1:
                        st.markdown("<div style='padding: 1rem 0;'>", unsafe_allow_html=True)
                        st.info("💡 카테고리를 선택하시면 지점별 상세 노출/측정 지표가 브랜드 항목 없이 집계되어 다운로드됩니다.")
                        
                        cats = ["전체 카테고리"] + list(db_data.get("CATS", []))
                        p1_cat = st.selectbox("👚 카테고리 선택 (P1)", cats, key="p4_tab_dl_p1_cat")
                        
                        score_mode_sel_p4 = st.selectbox(
                            "⚖️ 환산 기준 선택",
                            ["지표별 가중치 반영", "지표별 100점 환산 기준"],
                            key="p4_tab_dl_p1_score_mode"
                        )
                        score_mode_param_p4 = "100_percent" if score_mode_sel_p4 == "지표별 100점 환산 기준" else "weighted"

                        sel_metrics_p1_p4 = st.multiselect(
                            "📊 포함할 지표 선택 (P1)",
                            ["할인율", "BEST상품", "신선도", "시즌"],
                            default=["할인율", "BEST상품", "신선도", "시즌"],
                            key="p4_tab_dl_p1_metrics"
                        )
                        
                        col_p4_btn1, col_p4_btn2 = st.columns(2)
                        with col_p4_btn1:
                            dl_p4_excel = st.button("🚀 요약 엑셀 파일 생성", key="p4_gen_p1_tab", use_container_width=True)
                        with col_p4_btn2:
                            dl_p4_ppt = st.button("🚀 요약 PPT 파일 생성", key="p4_gen_p1_ppt", use_container_width=True)

                        if dl_p4_excel:
                            with st.spinner("지점별 카테고리 요약 엑셀 생성 중..."):
                                import core.report_generator as rg
                                if score_mode_param_p4 == "100_percent":
                                    excel_data = rg.export_p1_dashboard_excel_bytes(db_data, p1_cat, metrics_filter=sel_metrics_p1_p4)
                                    dl_filename = f"지점별_카테고리_100점대시보드_{p1_cat}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
                                else:
                                    excel_data = rg.export_p1_summary_excel_bytes(db_data, p1_cat, metrics_filter=sel_metrics_p1_p4, score_mode=score_mode_param_p4)
                                    dl_filename = f"지점별_카테고리_요약점수_현황_{p1_cat}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
                                if excel_data:
                                    st.success(f"✅ {dl_filename} 생성 완료!")
                                    st.download_button(
                                        label="📄 요약 엑셀 다운로드",
                                        data=excel_data,
                                        file_name=dl_filename,
                                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                        use_container_width=True,
                                    )
                                else:
                                    st.error("엑셀 파일 생성 실패")

                        if dl_p4_ppt:
                            with st.spinner("지점별 카테고리 요약 PPT 생성 중..."):
                                import core.ppt_generator as ptg
                                if score_mode_param_p4 == "100_percent":
                                    ppt_data = ptg.export_p1_dashboard_ppt_bytes(db_data, p1_cat, metrics_filter=sel_metrics_p1_p4)
                                    dl_filename = f"지점별_카테고리_100점대시보드_{p1_cat}_{datetime.now().strftime('%Y%m%d_%H%M')}.pptx"
                                else:
                                    ppt_data = ptg.export_p1_summary_ppt_bytes(db_data, p1_cat, metrics_filter=sel_metrics_p1_p4, score_mode=score_mode_param_p4)
                                    dl_filename = f"지점별_카테고리_요약점수_현황_{p1_cat}_{datetime.now().strftime('%Y%m%d_%H%M')}.pptx"
                                if ppt_data:
                                    st.success(f"✅ {dl_filename} 생성 완료!")
                                    st.download_button(
                                        label="📄 요약 PPT 다운로드",
                                        data=ppt_data,
                                        file_name=dl_filename,
                                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                                        use_container_width=True,
                                    )
                                else:
                                    st.warning("데이터가 없습니다.")
                        st.markdown("</div>", unsafe_allow_html=True)

                    with subtab_p2:
                        st.markdown("<div style='padding: 1rem 0;'>", unsafe_allow_html=True)
                        col1, col2 = st.columns(2)
                        stores = ["전체 지점"] + list(db_data.get("STORES", []))
                        cats = ["전체 카테고리"] + list(db_data.get("CATS", []))

                        with col1:
                            sel_store = st.selectbox("🏬 지점 선택", stores, key="p4_store")
                        with col2:
                            sel_cat = st.selectbox("👚 카테고리 선택", cats, key="p4_cat")

                        col_m, col_sc = st.columns([3, 2])
                        with col_m:
                            sel_metrics = st.multiselect(
                                "📊 지표 선택",
                                ["할인율", "BEST상품", "신선도", "시즌"],
                                default=["할인율", "BEST상품", "신선도", "시즌"],
                                key="p4_metrics",
                            )
                        with col_sc:
                            p4_score_mode_sel = st.selectbox(
                                "⚖️ 환산 기준",
                                ["지표별 가중치 반영", "지표별 100점 환산"],
                                key="p4_p2_score_mode",
                            )
                        metrics_key = ",".join(sel_metrics) if sel_metrics else "할인율,BEST상품,신선도,시즌"

                        st.markdown("---")
                        if p4_score_mode_sel == "지표별 100점 환산":
                            col_p4_e, col_p4_p = st.columns(2)
                            with col_p4_e:
                                dl_p4_excel = st.button("🚀 100점 엑셀 생성", key="p4_dash_excel", use_container_width=True)
                            with col_p4_p:
                                dl_p4_ppt = st.button("🚀 100점 PPT 생성", key="p4_dash_ppt", use_container_width=True)

                            if dl_p4_excel:
                                with st.spinner("브랜드 100점 대시보드 엑셀 생성 중..."):
                                    import core.report_generator as rg
                                    excel_data = rg.export_p2_dashboard_excel_bytes(db_data, sel_store, sel_cat, metrics_filter=sel_metrics)
                                    now_str = datetime.now().strftime("%Y%m%d_%H%M")
                                    dl_filename = f"브랜드_100점대시보드_{sel_store}_{sel_cat}_{now_str}.xlsx"
                                    if excel_data:
                                        st.success(f"✅ {dl_filename} 생성 완료!")
                                        st.download_button(
                                            label="📄 100점 엑셀 다운로드",
                                            data=excel_data,
                                            file_name=dl_filename,
                                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                            use_container_width=True,
                                        )
                                    else:
                                        st.warning("⚠️ 선택한 조건에 해당하는 데이터가 없습니다.")

                            if dl_p4_ppt:
                                with st.spinner("브랜드 100점 대시보드 PPT 생성 중..."):
                                    import core.ppt_generator as ptg
                                    ppt_data = ptg.export_p2_dashboard_ppt_bytes(db_data, sel_store, sel_cat, metrics_filter=sel_metrics)
                                    now_str = datetime.now().strftime("%Y%m%d_%H%M")
                                    dl_filename = f"브랜드_100점대시보드_{sel_store}_{sel_cat}_{now_str}.pptx"
                                    if ppt_data:
                                        st.success(f"✅ {dl_filename} 생성 완료!")
                                        st.download_button(
                                            label="📄 100점 PPT 다운로드",
                                            data=ppt_data,
                                            file_name=dl_filename,
                                            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                                            use_container_width=True,
                                        )
                                    else:
                                        st.warning("⚠️ 선택한 조건에 해당하는 데이터가 없습니다.")
                        else:
                            if st.button("🚀 상세 엑셀 파일 생성", key="p4_gen_detail_tab", use_container_width=True):
                                with st.spinner("브랜드 상세 노출판 엑셀 생성 중..."):
                                    excel_data = generate_optimized_excel(
                                        sel_store, sel_cat, metrics_key, data_fp, dashboard_json, REPORT_VERSION
                                    )
                                    now_str = datetime.now().strftime("%Y%m%d_%H%M")
                                    dl_filename = f"상품구색_노출판_{sel_store}_{sel_cat}_{now_str}.xlsx"
                                    if excel_data:
                                        st.success(f"✅ {dl_filename} 생성 완료!")
                                        st.download_button(
                                            label="📄 노출/측정판 엑셀 다운로드",
                                            data=excel_data,
                                            file_name=dl_filename,
                                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                            use_container_width=True,
                                        )
                                    else:
                                        st.warning("⚠️ 선택한 조건에 해당하는 데이터가 없습니다.")
                        st.markdown("</div>", unsafe_allow_html=True)
            except Exception as e:
                st.error(f"보고서 생성 오류: {e}")



if __name__ == "__main__":
    main()
