"""Dashboard page: Geopolitical Risk Analysis."""
from __future__ import annotations

import json
import streamlit as st
from dashboard.components.charts import (
    create_risk_gauge, create_sector_impact_chart, create_conflict_heatmap,
)
from dashboard.components.widgets import risk_badge, term_label
from dashboard.components.glossary import tip


def render(agent, engine, autopilot=None):
    st.header("Geopolitical Risk Analysis")

    if st.button("Run Full Geopolitical Analysis", type="primary", key="full_geo"):
        with st.spinner("Analyzing global geopolitical conditions..."):
            try:
                from mcp_servers.geopolitical_server import (
                    get_geopolitical_risk_score, get_conflict_monitor,
                    get_sector_impact, get_global_news,
                )

                risk_data = json.loads(get_geopolitical_risk_score())
                conflict_data = json.loads(get_conflict_monitor())
                news_data = json.loads(get_global_news("geopolitical crisis conflict", 15))

                sector_impacts = {}
                for sector in ["energy", "defense", "technology", "finance", "healthcare", "consumer"]:
                    impact = json.loads(get_sector_impact(sector))
                    sector_impacts[sector] = impact

                st.session_state["geo_risk"] = risk_data
                st.session_state["geo_conflicts"] = conflict_data
                st.session_state["geo_sectors"] = sector_impacts
                st.session_state["geo_news"] = news_data

            except Exception as e:
                st.error(f"Analysis failed: {e}")

    # Risk Score
    risk_data = st.session_state.get("geo_risk")
    if risk_data:
        col1, col2 = st.columns([1, 1])
        with col1:
            fig = create_risk_gauge(risk_data.get("composite_score", 0))
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.subheader("Risk Breakdown")
            risk_badge(risk_data.get("risk_level", "unknown"))
            st.write("")
            st.info(risk_data.get("advice", ""))

            breakdown = risk_data.get("category_breakdown", {})
            for category, info in breakdown.items():
                score = info.get("score", 0)
                articles = info.get("article_count", 0)
                bar_color = "#00d4aa" if score < 30 else "#ffa500" if score < 70 else "#ff4444"
                neg_ratio = info.get("negative_ratio", 0)
                neg_tip = tip("Negative Ratio").replace('"', "&quot;")
                st.markdown(
                    f"**{category.title()}**: {score:.0f}/100 ({articles} articles) "
                    f'<span title="{neg_tip}" style="cursor:help; border-bottom:1px dotted #666;">'
                    f"neg: {neg_ratio:.0%}</span> "
                    f"<span style='color:{bar_color}'>{'|' * int(score / 5)}</span>",
                    unsafe_allow_html=True,
                )

        st.divider()

    # Conflict Monitor
    conflict_data = st.session_state.get("geo_conflicts")
    if conflict_data and conflict_data.get("conflicts"):
        st.markdown(
            f"### {term_label('Conflict Monitor')}",
            unsafe_allow_html=True,
        )
        fig = create_conflict_heatmap(conflict_data["conflicts"])
        st.plotly_chart(fig, use_container_width=True)

        for conflict in conflict_data["conflicts"]:
            with st.expander(f"{conflict['conflict']} - {conflict['activity_level'].upper()}"):
                st.text(f"Region: {conflict['region']}")
                st.text(f"Risk Score: {conflict['risk_score']}")
                st.text(f"Articles: {conflict['article_count']}")
                if conflict.get("avg_sentiment") is not None:
                    st.markdown(
                        f"{term_label('Sentiment')}: {conflict['avg_sentiment']:.3f}",
                        unsafe_allow_html=True,
                    )
                if conflict.get("top_headlines"):
                    st.markdown("**Top Headlines:**")
                    for h in conflict["top_headlines"]:
                        st.markdown(f"- {h}")

        st.divider()

    # Sector Impact
    sector_impacts = st.session_state.get("geo_sectors")
    if sector_impacts:
        st.markdown(
            f"### {term_label('Sector Impact')}",
            unsafe_allow_html=True,
        )
        impact_scores = {}
        for sector, data in sector_impacts.items():
            impact_scores[sector] = data.get("category_impacts", {})

        simple_impacts = {s: {"impact_score": d.get("impact_score", 0)} for s, d in sector_impacts.items()}
        fig = create_sector_impact_chart(simple_impacts)
        st.plotly_chart(fig, use_container_width=True)

        for sector, data in sector_impacts.items():
            outlook = data.get("outlook", "unknown")
            color = "#00d4aa" if "low" in outlook else "#ffa500" if "moderate" in outlook else "#ff4444"
            st.markdown(
                f"**{sector.title()}**: <span style='color:{color}'>{outlook.replace('_', ' ').upper()}</span> - "
                f"{data.get('recommendation', '')}",
                unsafe_allow_html=True,
            )

        st.divider()

    # Latest News
    news_data = st.session_state.get("geo_news")
    if news_data and news_data.get("articles"):
        st.subheader("Latest Geopolitical News")
        for article in news_data["articles"]:
            sentiment = article.get("sentiment", {})
            compound = sentiment.get("compound", 0)
            s_color = "#00d4aa" if compound > 0.05 else "#ff4444" if compound < -0.05 else "#888"
            compound_tip = tip("Compound Score").replace('"', "&quot;")

            st.markdown(
                f"**{article['title']}** "
                f'<span title="{compound_tip}" style="color:{s_color}; cursor:help; '
                f'border-bottom:1px dotted {s_color};">[{compound:+.2f}]</span>',
                unsafe_allow_html=True,
            )
            st.caption(f"{article.get('source', 'Unknown')} | {article.get('published_at', '')[:10]} | "
                       f"Categories: {', '.join(article.get('categories', []))} | "
                       f"Regions: {', '.join(article.get('regions', []))}")
            if article.get("description"):
                st.text(article["description"][:200])
            st.write("")
    elif not risk_data:
        st.info("Click 'Run Full Geopolitical Analysis' to start.")

    # Region Risk
    st.divider()
    st.subheader("Region Risk Lookup")
    region = st.selectbox(
        "Select Region",
        ["middle_east", "east_asia", "europe", "south_asia", "americas"],
        key="region_select",
    )
    if st.button("Check Region Risk", key="region_risk_btn"):
        with st.spinner(f"Analyzing {region} region..."):
            try:
                from mcp_servers.geopolitical_server import get_region_risk
                result = json.loads(get_region_risk(region))
                risk_badge(result.get("risk_level", "unknown"))
                st.metric("Risk Score", f"{result.get('risk_score', 0):.0f}/100",
                          help=tip("Geopolitical Risk Score"))
                st.markdown(
                    f"{term_label('Negative Ratio')}: {result.get('negative_ratio', 0):.0%}",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"{term_label('Sentiment')}: {result.get('avg_sentiment', 0):.3f}",
                    unsafe_allow_html=True,
                )
                st.text(f"Articles analyzed: {result.get('article_count', 0)}")
                if result.get("key_headlines"):
                    st.markdown("**Key Headlines:**")
                    for h in result["key_headlines"]:
                        st.markdown(f"- {h}")
            except Exception as e:
                st.error(f"Failed: {e}")
