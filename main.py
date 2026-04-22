"""
main.py — Streamlit 메인 앱 v2
================================
[변경 내역]
- SmartBrandDetector 통합: 업로드 시 법인 자동 인식 결과 표시
- 브랜드 scoring config 키를 '카테고리_매장유형_브랜드명' 형식으로 통일
- 업로드 탭 UX 개선: 자동인식 → 확인 → 업로드 플로우
"""

import streamlit as st
import json
import sys
from datetime import datetime
import pandas as pd
import io

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


def parse_text_to_df(text_data: str) -> pd.DataFrame:
    """텍스트 붙여넣기(Tab 구분) → DataFrame 변환"""
    if not text_data.strip():
        return None
    try:
        return pd.read_csv(io.StringIO(text_data), sep='\t')
    except Exception as e:
        st.error(f"텍스트 파싱 오류: {e}")
        return None


# [v65.0] 캐시로 인한 로직 지연 방지를 위해 캐싱 해제
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
    if 'overwrite_approval' not in st.session_state:
        st.session_state.overwrite_approval = {}

    # [v112.0] 브랜드 맵핑 데이터를 최상단 전역 수준으로 이동하여 안정성 확보
    CATEGORY_BRAND_MAP = {
        "여성": [
            "로엠 (정상)", "미쏘 (정상)", "더아이잗 (정상)", "에잇컨셉 (정상)",
            "리스트 (상설)", "쉬즈미스 (상설)", "클라비스 (상설)", "나이스클랍 (상설)",
            "JJ지고트 (상설)", "바바팩토리 (상설)", "베네통 (상설)", "시슬리 (상설)",
            "비씨비지 (상설)", "발렌시아 (상설)", "베스띠벨리 (상설)", "올리비아로렌 (상설)",
            "제시뉴욕 (상설)", "샤틴 (상설)", "보니스팍스 (상설)", "안지크 (상설)",
            "플라스틱아일랜드 (상설)"
        ]
    }

    # [v90.0] 프리미엄 UI 설정: 사이드바 기본 축소 및 와이드 모드
    st.set_page_config(
        page_title="E·LAND AI 상품구색 진단 시스템",
        page_icon="🎯",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

    # ━━━ CSS Injection: Streamlit 기본 UI 강제 숨김 및 여백 제거 ━━━
    st.markdown("""
        <style>
        #MainMenu {visibility: hidden;}
        header {visibility: hidden;}
        footer {visibility: hidden;}
        /* 메인 내용 영역 여백 제거 */
        .block-container {
            padding-top: 0rem !important;
            padding-bottom: 0rem !important;
            padding-left: 0rem !important;
            padding-right: 0rem !important;
        }
        /* Iframe(대시보드)을 화면에 꽉 차게 설정 */
        iframe {
            width: 100vw !important;
            height: 100vh !important;
            border: none !important;
        }
        /* 사이드바 너비 조정 및 스타일 */
        [data-testid="stSidebar"] {
            background-color: #f8f9fa;
        }
        </style>
    """, unsafe_allow_html=True)

    check_mgr = get_gsheet_manager()

    # ━━━ 사이드바 네비게이션 ━━━
    with st.sidebar:
        st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/2/23/E-Land_Group_logo.svg/1024px-E-Land_Group_logo.svg.png", width=120)
        st.title("Admin Menu")
        menu = st.radio("이동", ["📊 실시간 대시보드", "📤 데이터 업로드"], label_visibility="collapsed")
        st.markdown("---")
        st.caption(f"DB Connected: {check_mgr.is_connected}")

    # ────────────────────────────────────────────
    # 뷰 1: 실시간 대시보드 (기본 화면)
    # ────────────────────────────────────────────
    if menu == "📊 실시간 대시보드":
        if not check_mgr.is_connected:
            st.error("구글 시트 연동 오류입니다.")
        else:
            # 데이터 로드 및 렌더링 (자동 실행)
            try:
                from core.data_loader import load_dashboard_data
                import streamlit.components.v1 as components
                
                db_data = load_dashboard_data(mgr=check_mgr)

                if "error" in db_data:
                    st.error(f"❌ 데이터 빌드 실패: {db_data['error']}")
                else:
                    template_path = "ui/dashboard_template.html"
                    with open(template_path, "r", encoding="utf-8") as f:
                        html_template = f.read()

                    data_json = json.dumps(db_data, ensure_ascii=False)
                    script_inject = f"<script>window.__INITIAL_DATA__ = {data_json};</script>"
                    final_html = html_template.replace('<script>', script_inject + '<script>', 1)

                    # 여백 없는 전체 화면 렌더링 (CSS Injection에서 100vh로 강제 제어됨)
                    components.html(final_html, height=1200, scrolling=True)
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
            store_list = [
                'NC신구로점', 'NC강서점', 'NC송파점', 'NC불광점', 'NC고잔점', 
                'NC평촌점', 'NC야탑점', 'NC청주점', '뉴코아강남점', '뉴코아부천점', 
                '뉴코아인천점', '2001중계점', '2001분당점', '동아쇼핑점', 
                '동아수성점', 'NC대전유성점'
            ]
            raw = st.selectbox("지점", store_list,
                               index=None, placeholder="진단할 지점을 선택하세요...", label_visibility="collapsed")
            if raw: selected_store = raw

        with col_cat:
            st.caption("👚 2. 카테고리")
            if selected_store:
                raw = st.selectbox("카테고리", ['여성', '잡화', '스포츠', '캐주얼', '아동', '신사', '골프웨어'],
                                   index=None, placeholder="진단할 카테고리를 선택하세요...", label_visibility="collapsed")
                if raw: selected_category = raw
            else:
                st.selectbox("카테고리", ["👈 지점을 먼저 선택하세요"], disabled=True, label_visibility="collapsed")

        col_brand, col_month = st.columns(2)
        with col_brand:
            st.caption("🏷️ 3. 대상 브랜드(매장유형)")
            if selected_category:
                # 해당 카테고리의 브랜드 목록 가져오기
                base_list = CATEGORY_BRAND_MAP.get(selected_category, [])
                brand_list = base_list + ["직접 입력(범용)"]
                
                raw = st.selectbox("브랜드", brand_list, index=None, placeholder="브랜드를 선택하세요...", label_visibility="collapsed")
                if raw:
                    if "(" in raw and "범용" not in raw:
                        selected_brand = raw.split(' ')[0]
                        selected_type = "정상" if "정상" in raw else "상설"
                    else:
                        selected_brand = raw
                        # 범용 입력의 경우 지점별 특성에 맞게 직접 선택
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
                    text_inv = st.text_area(f"[{selected_brand}] 재고 텍스트 (품번, 수량, 금액 등 포함)", height=150, help="엑셀의 '품번', '재고', '금액' 등이 포함된 영역을 복사해서 붙여넣으세요.")
                    text_sales = st.text_area(f"[{selected_brand}] 판매 텍스트 (품번, 수량, 금액 등 포함)", height=150, help="판매 데이터가 없다면 빈칸으로 두셔도 되지만, 품번별 판매금액 분석을 위해 입력을 권장합니다.")
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
                                        # [v2.5] 업로드 데이터 프리뷰 추가
                                        with st.expander("📊 업로드 데이터 미리보기 (상위 5행)", expanded=True):
                                            st.dataframe(final_df.head(5), use_container_width=True)
                                        st.session_state.overwrite_approval.pop(state_key, None)
                                    else: 
                                        st.error(f"DB 저장 실패: {check_mgr.error_msg}")
                        except Exception as e:
                            st.error(f"오류: {e}")
        st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
