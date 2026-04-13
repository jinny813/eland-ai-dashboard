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
from datetime import datetime
import pandas as pd
import io
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
    """매번 최신 로직을 반영하도록 객체 새로 생성"""
    return GSheetManager()


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

    st.set_page_config(page_title="상품구색 진단 에이전트", layout="wide", initial_sidebar_state="expanded")

    check_mgr = get_gsheet_manager()

    st.markdown("<style>#MainMenu {visibility: hidden;} header {visibility: hidden;}</style>", unsafe_allow_html=True)
    st.title("🎯 신구로점 여성 카테고리 상품구색 진단 대시보드")
    st.markdown("---")

    tab1, tab2 = st.tabs(["📊 대시보드", "📤 데이터 통합 및 업로드"])

    # ────────────────────────────────────────────
    # Tab 2: 데이터 업로드 + 자동인식 UI
    # ────────────────────────────────────────────
    with tab2:
        st.subheader("RAW데이터 입력")
        st.info("안내에 따라 순서대로 [지점 → 카테고리 → 브랜드 → 월]을 선택하고 파이프라인을 활성화해주세요.")

        selected_store = selected_category = selected_brand = selected_type = selected_month = None

        col_store, col_cat = st.columns(2)
        with col_store:
            st.caption("🏬 1. 진단 지점")
            raw = st.selectbox("지점", ['NC신구로점', 'NC강서점', '동아쇼핑점'],
                               index=None, placeholder="진단할 지점을 선택하세요...", label_visibility="collapsed")
            if raw:
                selected_store = raw

        with col_cat:
            st.caption("👚 2. 카테고리")
            if selected_store:
                raw = st.selectbox("카테고리",
                                   ['여성', '잡화', '스포츠', '캐주얼', '아동', '신사', '골프웨어'],
                                   index=None, placeholder="진단할 카테고리를 선택하세요...", label_visibility="collapsed")
                if raw:
                    selected_category = raw
            else:
                st.selectbox("카테고리", ["👈 지점을 먼저 선택하세요"], disabled=True, label_visibility="collapsed")

        st.markdown("<br>", unsafe_allow_html=True)

        col_brand, col_month = st.columns(2)
        with col_brand:
            st.caption("🏷️ 3. 대상 브랜드(매장유형)")
            if selected_category:
                brand_list = [
                    "로엠 (정상)", "미쏘 (정상)",
                    "인동팩토리(리스트,쉬즈미스) (상설)",
                    "JJ지고트 (상설)", "바바팩토리 (상설)", "나이스클랍 (상설)"
                ]
                raw = st.selectbox("브랜드", brand_list, index=None,
                                   placeholder="브랜드를 선택하세요...", label_visibility="collapsed")
                if raw:
                    selected_brand = raw.split(' ')[0]
                    selected_type = "정상" if selected_brand in ["로엠", "미쏘"] else "상설"
            else:
                st.selectbox("브랜드", ["👈 카테고리를 먼저 선택하세요"], disabled=True, label_visibility="collapsed")

        with col_month:
            st.caption("📅 4. 대상 월(Month)")
            if selected_brand:
                month_list = [f"{m}월" for m in range(1, 13)]
                raw = st.selectbox("월", month_list, index=datetime.now().month - 1, label_visibility="collapsed")
                if raw:
                    selected_month = raw
            else:
                st.selectbox("월", ["👈 브랜드를 먼저 선택하세요"], disabled=True, label_visibility="collapsed")

        # ─── 4가지 조건 충족 시 업로드 영역 표시 ───
        if selected_store and selected_category and selected_brand and selected_type and selected_month:
            st.markdown("---")

            state_key = f"{selected_store}_{selected_brand}_{selected_month}"

            if check_mgr.is_connected:
                is_dup = check_mgr.check_existing_data(selected_store, selected_category, selected_brand, selected_month)
            else:
                is_dup = False

            if is_dup and not st.session_state.overwrite_approval.get(state_key, False):
                st.warning("⚠️ 이미 저장된 데이터 입니다. 수정/업데이트 하시겠습니까?")
                st.info(f"선택하신 '{selected_store} {selected_category} {selected_brand} - {selected_month}' 데이터는 구글 시트에 이미 존재합니다.")
                if st.button("수정하시겠습니까?", type="primary"):
                    st.session_state.overwrite_approval[state_key] = True
                    st.rerun()
            else:
                subtab_file, subtab_text, subtab_url = st.tabs(
                    ["📂 Excel 파일 업로드", "📋 데이터 직접 붙여넣기(Text)", "🔗 구글 시트 연동(URL)"]
                )
                inv_data = sales_data = None
                detector_result = None

                with subtab_file:
                    col_inv, col_sales = st.columns(2)
                    with col_inv:
                        uf_inv = st.file_uploader(
                            f"[{selected_brand}] 재고조회 엑셀 파일", type=['xls', 'xlsx'],
                            key=f"inv_{state_key}"
                        )
                    with col_sales:
                        uf_sales = st.file_uploader(
                            f"[{selected_brand}] 판매조회 엑셀 파일", type=['xls', 'xlsx'],
                            key=f"sales_{state_key}"
                        )

                    # ━━━ 法人 자동인식 (재고 파일 업로드 즉시 동작) ━━━
                    if uf_inv:
                        try:
                            from core.smart_brand_detector import SmartBrandDetector
                            detector = SmartBrandDetector()
                            detector_result = detector.detect(uf_inv, file_name=uf_inv.name)
                            _show_detector_result(detector_result)
                        except Exception as e:
                            st.warning(f"자동인식 실패 (수동 선택 계속 사용): {e}")

                    if uf_inv and uf_sales:
                        inv_data, sales_data = uf_inv, uf_sales

                with subtab_text:
                    text_inv = st.text_area(f"[{selected_brand}] 재고 텍스트", height=150)
                    text_sales = st.text_area(f"[{selected_brand}] 판매 텍스트", height=150)
                    if text_inv and text_sales:
                        inv_data = parse_text_to_df(text_inv)
                        sales_data = parse_text_to_df(text_sales)

                with subtab_url:
                    st.info("추후 개방 예정 기능입니다.")

                btn_type = "primary" if not is_dup else "secondary"

                if st.button("업로드", type=btn_type, use_container_width=True):
                    if inv_data is None or sales_data is None:
                        st.warning("재고 데이터와 판매 데이터를 모두 넣어주세요.")
                    elif not check_mgr.is_connected:
                        st.error("구글 시트 연동 오류를 서버 콘솔에서 확인해주세요.")
                    else:
                        try:
                            dm = DataManager()
                            with st.spinner(f"[{selected_store} / {selected_month}] '{selected_brand}' 엑셀 파일 RAW 데이터 병합 중..."):
                                final_df = dm.process_and_merge(
                                    selected_brand, selected_store, selected_category,
                                    selected_type, selected_month, inv_data, sales_data
                                )

                            if final_df is not None and not final_df.empty:
                                st.write("✅ **업로드 전 데이터 구조 확인 (Debug)**")
                                st.write(f"전체 컬럼: `{final_df.columns.tolist()}`")
                                st.dataframe(final_df.head(20)) # style_name 존재 여부 확인용

                                with st.spinner("구글 DB 업데이트 이관 중... (순수 RAW 데이터만 저장됨)"):
                                    if is_dup:
                                        is_saved = check_mgr.overwrite_record(final_df, selected_store, selected_brand, selected_month)
                                    else:
                                        is_saved = check_mgr.append_record(final_df)

                                if is_saved:
                                    st.success(f"🎊 완료! 총 {len(final_df)}개 모델의 데이터가 DB에 저장됐습니다.")
                                    st.info(f"작업 요약: {len(final_df.columns)}개 컬럼(v65.0 규격) 동기화 완료")
                                    # 업로드 승인 상태 초기화
                                    st.session_state.overwrite_approval.pop(state_key, None)
                                else:
                                    st.error("Google Sheets DB 반영에 실패했습니다.")
                            else:
                                st.warning("병합된 엑셀 데이터가 없습니다.")
                        except Exception as e:
                            st.error(f"내부 오류가 발생했습니다: {e}")

    # ────────────────────────────────────────────
    # Tab 1: 대시보드 (Claude HTML 렌더링)
    # ────────────────────────────────────────────
    with tab1:
        st.subheader("💡 하이브리드 실시간 대시보드 (Claude UI 연동)")
        st.write("안내: 파이썬 파이프라인에서 적재된 DB 원시 데이터를 바탕으로, 클로드 기반 고급 HTML 대시보드가 라이브 렌더링됩니다.")

        # 연결 상태 사전 표시
        if check_mgr.is_connected:
            st.success("✅ Google Sheets DB 연결됨")
        else:
            st.error(f"❌ Google Sheets 연결 실패: {check_mgr.error_msg}")
            st.info("credentials.json 파일과 시트 공유 설정을 확인해주세요.")

        if st.button("🚀 전체 뷰어 새로고침 및 동기화", type="primary"):
            if not check_mgr.is_connected:
                st.error("구글 시트 연동 오류입니다.")
            else:
                with st.spinner("구글 DB에서 최신 RAW 데이터를 읽어오는 중..."):
                    try:
                        sheet = check_mgr.spreadsheet.worksheet("Records")
                        all_recs = sheet.get_all_records()
                    except Exception as e:
                        st.error(f"데이터 조회 실패: {e}")
                        all_recs = []

                if all_recs:
                    st.success(f"✔️ 총 {len(all_recs)} 레코드 해석 완료. 렌더링 엔진 가동 중...")
                    with st.spinner("점수 계산 및 대시보드 데이터 빌드 중..."):
                        try:
                            from core.data_loader import load_dashboard_data
                            import streamlit.components.v1 as components

                            # 캐싱된 연결을 재사용해 DB를 두 번 읽지 않도록 전달
                            db_data = load_dashboard_data(mgr=check_mgr)

                            if "error" in db_data:
                                st.error(f"❌ 데이터 빌드 실패: {db_data['error']}")
                                if "traceback" in db_data:
                                    st.code(db_data["traceback"])
                            else:
                                template_path = "ui/dashboard_template.html"
                                with open(template_path, "r", encoding="utf-8") as f:
                                    html_template = f.read()

                                data_json = json.dumps(db_data, ensure_ascii=False)
                                script_inject = f"<script>window.__INITIAL_DATA__ = {data_json};</script>"
                                final_html = html_template.replace('<script>', script_inject + '<script>', 1)

                                components.html(final_html, height=1200, scrolling=True)
                        except Exception as e:
                            import traceback
                            st.error(f"대시보드 생성 실패: {e}")
                            with st.expander("상세 오류 보기"):
                                st.code(traceback.format_exc())
                else:
                    st.warning("구글 DB에 저장된 RAW 데이터가 없습니다. 업로드 탭(Tab 2)을 먼저 사용해주세요.")


if __name__ == "__main__":
    main()
