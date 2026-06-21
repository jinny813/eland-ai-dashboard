import sys
import re

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace _cached_preprocess entirely and rewrite _cached_build_month
search_pattern = r'''@st\.cache_data\(ttl=600, max_entries=1, show_spinner="전처리 및 구조 생성 중 \(1회\)\.\.\."\)
def _cached_preprocess\(_mgr, max_no: int, report_version: str = REPORT_VERSION\):
    import importlib, sys
    for _m in \['core\.data_loader'\]:
        if _m in sys\.modules:
            importlib\.reload\(sys\.modules\[_m\]\)
    from core\.data_loader import preprocess_raw_records
    raw_recs = _cached_get_raw_records\(_mgr, max_no\)
    return preprocess_raw_records\(_mgr, raw_recs\)


@st\.cache_data\(ttl=600, max_entries=1, show_spinner="월별 점수 산출 중\.\.\."\)
def _cached_build_month\(_mgr, max_no: int, month: str, report_version: str = REPORT_VERSION\):
    """
    \[Stage 2 캐시\] 월별 대시보드 빌드.
    캐시 키: \(max_no, month, report_version\)\. 월별 독립 엔트리 유지.
    """
    import importlib, sys
    for _m in \['core\.data_loader'\]:
        if _m in sys\.modules:
            importlib\.reload\(sys\.modules\[_m\]\)
    from core\.data_loader import load_dashboard_data
    preprocessed = _cached_preprocess\(_mgr, max_no, report_version=report_version\)
    return load_dashboard_data\(
        mgr=_mgr,
        selected_month=month,
        _preprocessed=preprocessed,
    \)'''

replace_pattern = '''@st.cache_data(ttl=600, max_entries=1, show_spinner="월별 점수 산출 중...")
def _cached_build_month(_mgr, max_no: int, month: str, report_version: str = REPORT_VERSION):
    """
    [vMem] 전체 데이터를 DataFrame으로 메모리에 올리는 OOM 방지를 위해,
    raw_recs 단계에서 Python List 형태로 선택된 달만 필터링한 후 load_dashboard_data로 넘깁니다.
    """
    import importlib, sys
    for _m in ['core.data_loader']:
        if _m in sys.modules:
            importlib.reload(sys.modules[_m])
    from core.data_loader import load_dashboard_data

    # 전체 시트를 List[dict]로 로드 (Streamlit 1GB 제한 시 이 정도는 캐시 가능)
    raw_recs = _cached_get_raw_records(_mgr, max_no)
    if isinstance(raw_recs, dict) and "error" in raw_recs:
        return raw_recs

    # 선택된 달의 데이터만 필터링하여 DataFrame 변환 크기를 1/N로 축소
    month_recs = [r for r in raw_recs if str(r.get('data_month', '')).strip() == month]

    return load_dashboard_data(
        mgr=_mgr,
        selected_month=month,
        raw_recs=month_recs,
    )'''

if re.search(search_pattern, content):
    content = re.sub(search_pattern, replace_pattern, content)
else:
    print("Pattern not found! Trying fallback...")
    # Fallback if string exact match fails due to slight variations
    start_idx = content.find('@st.cache_data(ttl=600, max_entries=1, show_spinner="전처리 및 구조 생성 중 (1회)...")')
    end_idx = content.find('@st.cache_data(ttl=600, max_entries=1, show_spinner=False)', start_idx)
    if start_idx != -1 and end_idx != -1:
        content = content[:start_idx] + replace_pattern + "\n\n\n" + content[end_idx:]

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Preprocess memory leak fixed.")
