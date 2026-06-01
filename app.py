"""
资产总览 — 仪表盘主页
"""

from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from db import get_db


st.set_page_config(page_title="资产总览", layout="wide")


def check_config():
    if "supabase_url" not in st.secrets or "supabase_key" not in st.secrets:
        st.error("""
        ### 未配置 Supabase 连接

        1. 在 [supabase.com](https://supabase.com) 创建项目
        2. 在 SQL Editor 中执行 `setup.sql`
        3. 复制项目 URL 和 anon key 到 `.streamlit/secrets.toml`：
        ```toml
        supabase_url = "https://xxxxx.supabase.co"
        supabase_key = "eyJ..."
        ```
        """)
        st.stop()


check_config()
db = get_db()

st.title("资产总览")

# ---- 加载数据 ----
items_df = db.get_items_df(active_only=True)
groups_df = db.get_groups_df()
latest_date = db.get_latest_date()

if latest_date is None:
    st.info("暂无数据。请先在「录入」页面添加第一笔记录。")
    st.stop()

snapshot_df = db.get_snapshot_df(latest_date)

if snapshot_df.empty:
    st.info(f"最近日期 {latest_date} 无数据，请检查。")
    st.stop()

# 合并
df = snapshot_df[["item_id", "value"]].merge(
    items_df[["id", "name", "group_name", "group_type", "parent_id"]],
    left_on="item_id", right_on="id",
)

asset_df = df[df["group_type"] == "asset"]
liability_df = df[df["group_type"] == "liability"]
total_assets = asset_df["value"].sum()
total_liabilities = liability_df["value"].sum()
net_worth = total_assets - total_liabilities

# 周环比
all_dates = db.get_all_dates()
change = None
change_pct = None
if len(all_dates) >= 2:
    prev_df = db.get_snapshot_df(all_dates[1])
    if not prev_df.empty:
        prev = prev_df[["item_id", "value"]].merge(
            items_df[["id", "group_type"]], left_on="item_id", right_on="id"
        )
        prev_nw = (
            prev[prev["group_type"] == "asset"]["value"].sum()
            - prev[prev["group_type"] == "liability"]["value"].sum()
        )
        change = net_worth - prev_nw
        if prev_nw != 0:
            change_pct = change / prev_nw * 100

# ---- 指标卡片 ----
col1, col2, col3, col4 = st.columns(4)
col1.metric("总资产", f"¥{total_assets:,.0f}")
col2.metric("总负债", f"¥{total_liabilities:,.0f}")
col3.metric(
    "净资产",
    f"¥{net_worth:,.0f}",
    delta=f"¥{change:+,.0f}（{change_pct:+.1f}%）" if change is not None else None,
)
col4.metric("最近更新", str(latest_date))

st.divider()

# ---- 构成图 ----
left, right = st.columns(2)

with left:
    st.subheader("资产构成")
    if not asset_df.empty:
        pie_asset = asset_df.groupby("group_name")["value"].sum().reset_index()
        fig = px.pie(
            pie_asset, values="value", names="group_name", hole=0.4,
            color_discrete_sequence=px.colors.sequential.Greens_r,
        )
        fig.update_traces(textinfo="percent+label")
        fig.update_layout(height=380)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.write("暂无资产数据")

with right:
    st.subheader("负债构成")
    if not liability_df.empty:
        pie_lia = liability_df.groupby("group_name")["value"].sum().reset_index()
        fig = px.pie(
            pie_lia, values="value", names="group_name", hole=0.4,
            color_discrete_sequence=px.colors.sequential.Reds_r,
        )
        fig.update_traces(textinfo="percent+label")
        fig.update_layout(height=380)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.write("暂无负债数据")

# ---- 净资产趋势 ----
st.divider()
st.subheader("净资产趋势")

recent_dates = all_dates[:12]
if len(recent_dates) >= 2:
    trend_rows = []
    for d in recent_dates:
        snap = db.get_snapshot_df(d)
        if snap.empty:
            continue
        merged = snap[["item_id", "value"]].merge(
            items_df[["id", "group_type"]], left_on="item_id", right_on="id"
        )
        a = merged[merged["group_type"] == "asset"]["value"].sum()
        l = merged[merged["group_type"] == "liability"]["value"].sum()
        trend_rows.append({"date": d, "总资产": a, "总负债": l, "净资产": a - l})

    if trend_rows:
        trend_df = pd.DataFrame(trend_rows).sort_values("date")
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=trend_df["date"], y=trend_df["净资产"],
            mode="lines+markers", name="净资产",
            line=dict(color="#1f77b4", width=2.5),
        ))
        fig.add_trace(go.Scatter(
            x=trend_df["date"], y=trend_df["总资产"],
            mode="lines", name="总资产",
            line=dict(color="#2ca02c", width=1, dash="dot"),
        ))
        fig.add_trace(go.Scatter(
            x=trend_df["date"], y=trend_df["总负债"],
            mode="lines", name="总负债",
            line=dict(color="#d62728", width=1, dash="dot"),
        ))
        fig.update_layout(height=400, hovermode="x unified", margin=dict(l=20, r=20, t=10, b=20))
        st.plotly_chart(fig, use_container_width=True)
else:
    st.write("需要至少 2 条记录才能显示趋势。")

# ---- 资产明细表 ----
st.divider()
st.subheader("资产明细")
if not df.empty:
    detail = df[["group_name", "name", "value"]].copy()
    detail.columns = ["分类", "项目", "金额"]
    detail = detail.sort_values(["分类", "金额"], ascending=[True, False])
    detail["占比"] = detail["金额"] / detail["金额"].sum() * 100
    detail["金额"] = detail["金额"].apply(lambda x: f"¥{x:,.2f}")
    detail["占比"] = detail["占比"].apply(lambda x: f"{x:.1f}%")
    st.dataframe(detail, use_container_width=True, hide_index=True)
