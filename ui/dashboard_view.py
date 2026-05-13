# ui/dashboard_view.py

import streamlit as st
import plotly.graph_objects as go

def render_item_analysis_section(analysis_result, category, zoning):
    """
    [v3.5] 아이템 점수 상세 분석 섹션 렌더링
    - 실제 재고 비중 vs 가이드라인 비중 비교 차트
    - 로직 검증 샘플 테이블
    """
    if not analysis_result:
        st.warning(f"⚠️ [{category} - {zoning}] 에 대한 아이템 분석 데이터가 부족합니다.")
        return

    st.markdown(f"### 📊 {category} - {zoning} 아이템 비중 현황 (Actual vs Guide)")
    
    chart_data = analysis_result['chart_data']
    
    # 1. Grouped Bar Chart 구현
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=chart_data['Group'],
        y=chart_data['Actual'],
        name='현재 재고 비중 (%)',
        marker_color='#1E40AF',
        text=[f"{v:.1f}%" for v in chart_data['Actual']],
        textposition='auto',
    ))
    
    fig.add_trace(go.Bar(
        x=chart_data['Group'],
        y=chart_data['Guide'],
        name='가이드라인 비중 (%)',
        marker_color='#94A3B8',
        text=[f"{v:.1f}%" for v in chart_data['Guide']],
        textposition='auto',
    ))

    fig.update_layout(
        barmode='group',
        template='plotly_white',
        height=400,
        margin=dict(l=20, r=20, t=40, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        yaxis=dict(title="비중 (%)", range=[0, max(chart_data['Actual'].max(), chart_data['Guide'].max()) + 10])
    )

    st.plotly_chart(fig, use_container_width=True)

    # 2. 로직 검증 테이블 (샘플 5행)
    with st.expander("🔍 아이템 매핑 로직 검증 (Sample 5 rows)"):
        st.caption("item_code가 정의된 5개 그룹(아우터, 상의, 하의, 스커트, 원피스)으로 정상 분류되었는지 확인하세요.")
        st.table(analysis_result['sample_data'])
