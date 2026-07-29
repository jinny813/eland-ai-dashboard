"""
scripts/generate_static_preview.py
====================================
dashboard_backup.json → 완전 독립 실행 가능한 스태틱 HTML 생성

생성된 파일은:
- 외부 CDN(Chart.js) 인라인 포함
- 모든 데이터 내장 (window.__ALL_DATA__)
- 로컬 더블클릭으로 바로 열림
- 인터넷 없어도 동작

사용법:
  python scripts/generate_static_preview.py
  python scripts/generate_static_preview.py --out preview_v2.html
"""

import sys
import os
import json
import argparse
import urllib.request
import urllib.error

# 프로젝트 루트를 경로에 추가
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

BACKUP_JSON   = os.path.join(_ROOT, "data", "dashboard_backup.json")
TEMPLATE_HTML = os.path.join(_ROOT, "ui", "dashboard_template.html")
DEFAULT_OUT   = os.path.join(_ROOT, "preview_dashboard.html")

CHART_JS_CDN  = "https://cdn.jsdelivr.net/npm/chart.js"
CHART_JS_CDN_FALLBACK = "https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"


def _fetch_url(url: str, timeout: int = 15) -> str | None:
    """URL에서 텍스트 가져오기 (실패 시 None)"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8")
    except Exception as e:
        print(f"  ⚠️  {url} 다운로드 실패: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="스태틱 대시보드 HTML 생성")
    parser.add_argument("--out", default=DEFAULT_OUT, help="출력 파일 경로")
    parser.add_argument("--no-inline-js", action="store_true", help="Chart.js 인라인 생략 (CDN 유지)")
    args = parser.parse_args()

    # ── 1. 백업 JSON 로드 ──────────────────────────────────────────────────────
    if not os.path.exists(BACKUP_JSON):
        print(f"❌ 백업 파일 없음: {BACKUP_JSON}")
        print("   먼저 Streamlit 앱에서 '⚡ 데이터 갱신' 버튼을 눌러 dashboard_backup.json을 생성하세요.")
        sys.exit(1)

    print(f"📂 백업 데이터 로드 중: {BACKUP_JSON}")
    with open(BACKUP_JSON, "r", encoding="utf-8") as f:
        backup_data = json.load(f)

    # __ts__ 메타키 분리
    cache_ts = backup_data.pop("__ts__", "백업 데이터")
    if not backup_data:
        print("❌ 백업 파일에 월별 데이터가 없습니다.")
        sys.exit(1)

    months = [k for k in backup_data.keys() if k != "error"]
    print(f"   → {len(months)}개 월 데이터 확인: {months}")

    # 각 월에 AVAILABLE_MONTHS / SELECTED_MONTH 주입 (main.py와 동일)
    def _m_sort(m):
        try:
            return int(str(m).replace("월", "").strip())
        except Exception:
            return 0

    available_months = sorted(months, key=_m_sort, reverse=True)
    for mi, di in backup_data.items():
        if isinstance(di, dict) and "error" not in di:
            di["AVAILABLE_MONTHS"] = available_months
            di["SELECTED_MONTH"]   = mi

    # ── 2. 템플릿 HTML 로드 ────────────────────────────────────────────────────
    if not os.path.exists(TEMPLATE_HTML):
        print(f"❌ 템플릿 파일 없음: {TEMPLATE_HTML}")
        sys.exit(1)

    print(f"📄 HTML 템플릿 로드 중: {TEMPLATE_HTML}")
    with open(TEMPLATE_HTML, "r", encoding="utf-8") as f:
        html = f.read()

    # ── 3. Chart.js 인라인 처리 ────────────────────────────────────────────────
    if not args.no_inline_js:
        print("📦 Chart.js 인라인 처리 중...")
        chart_js_code = _fetch_url(CHART_JS_CDN) or _fetch_url(CHART_JS_CDN_FALLBACK)
        if chart_js_code:
            # CDN <script> 태그를 인라인 코드로 교체
            cdn_tag = f'<script src="{CHART_JS_CDN}"></script>'
            inline_tag = f"<script>{chart_js_code}</script>"
            if cdn_tag in html:
                html = html.replace(cdn_tag, inline_tag)
                print(f"   → Chart.js 인라인 완료 ({len(chart_js_code)//1024}KB)")
            else:
                print("   → Chart.js CDN 태그를 찾지 못했습니다 (스킵)")
        else:
            print("   ⚠️  Chart.js 다운로드 실패 — CDN 링크 유지 (인터넷 필요)")

    # ── 4. 데이터 주입 (main.py와 동일 방식) ──────────────────────────────────
    print("💉 데이터 주입 중...")

    def _json_default(o):
        if hasattr(o, "__float__") and type(o).__module__ == "numpy":
            return float(o)
        return str(o)

    data_json = json.dumps(backup_data, ensure_ascii=True, default=_json_default)
    safe_json = data_json.replace("</script>", "<\\/script>")

    script_inject = (
        f'<!-- [Static Preview] Generated: {cache_ts} -->\n'
        f'<script id="__data" type="application/json">{safe_json}</script>\n'
        f'<script>window.__ALL_DATA__ = JSON.parse(document.getElementById("__data").textContent);</script>\n'
    )

    # 첫 번째 <script> 태그 바로 앞에 데이터 삽입
    if "<script>" in html:
        html = html.replace("<script>", script_inject + "<script>", 1)
    else:
        # <script> 태그가 없으면 </head> 앞에 삽입
        html = html.replace("</head>", script_inject + "</head>", 1)

    # ── 5. 파일 저장 ──────────────────────────────────────────────────────────
    out_path = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    size_kb = os.path.getsize(out_path) // 1024
    print(f"\n✅ 스태틱 HTML 생성 완료!")
    print(f"   파일: {out_path}")
    print(f"   크기: {size_kb}KB")
    print(f"   데이터 기준: {cache_ts}")
    print(f"\n👉 브라우저에서 바로 열거나 GitHub에 커밋해서 공유하세요.")
    print(f"   (이 파일은 인터넷 없이도 완전히 동작합니다)")


if __name__ == "__main__":
    main()
