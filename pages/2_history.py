"""
历史趋势与项目明细
"""

from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from db import get_db


st.set_page_config(page_title="历史趋势", layout="wide")


def check_config():
    if "supabase_url" not in st.secrets or "supabase_key" not in st.secrets:
        st.error("请先配置 Supabase 连接。")
        st.stop()


check_config()
db = get_db()

st.title("历史趋势")

# ---- 日期范围 ----
all_dates = db.get_all_dates()
if not all_dates:
    st.info("暂无数据。")
    st.stop()

min_date = date.fromisoformat(all_dates[-1])
max_date = date.fromisoformat(all_dates[0])

# 默认显示最近 12 周
default_start = max_date - timedelta(weeks=12)
if default_start < min_date:
    default_start = min_date

col1, col2 = st.columns(2)
with col1:
    start = st.date_input("开始日期", value=default_start, min_value=min_date, max_value=max_date)
with col2:
    end = st.date_input("结束日期", value=max_date, min_value=min_date, max_value=max_date)

start_str = start.isoformat()
end_str = end.isoformat()

if start > end:
    st.error("开始日期不能晚于结束日期")
    st.stop()

# ---- 加载数据 ----
history = db.get_history_df(start_str, end_str)
items_df = db.get_items_df(active_only=False)

if history.empty:
    st.info("所选日期范围内没有数据。")
    st.stop()

df = history[["item_id", "snapshot_date", "value"]].merge(
    items_df[["id", "name", "group_name", "group_type", "active"]],
    left_on="item_id", right_on="id",
)
df["snapshot_date"] = pd.to_datetime(df["snapshot_date"])

# ---- 净资产趋势 ----
daily = df.groupby(["snapshot_date", "group_type"])["value"].sum().unstack(fill_value=0)
daily["净资产"] = daily.get("asset", 0) - daily.get("liability", 0)
daily = daily.reset_index()

st.subheader("净资产走势")
fig_nw = go.Figure()
fig_nw.add_trace(go.Scatter(
    x=daily["snapshot_date"], y=daily["净资产"],
    mode="lines+markers", name="净资产",
    line=dict(color="#1f77b4", width=2.5),
    fill="tozeroy", fillcolor="rgba(31,119,180,0.1)",
))
fig_nw.update_layout(height=380, hovermode="x unified", margin=dict(l=20, r=20, t=10, b=20))
st.plotly_chart(fig_nw, use_container_width=True)

# ---- 分类构成趋势 ----
st.subheader("分类构成变化")
cat_data = df.groupby(["snapshot_date", "group_name", "group_type"])["value"].sum().reset_index()

fig_cat = go.Figure()
asset_cats = cat_data[cat_data["group_type"] == "asset"]["group_name"].unique()
liability_cats = cat_data[cat_data["group_type"] == "liability"]["group_name"].unique()

asset_colors = ["#2ca02c", "#98df8a", "#c5e0b4", "#aec7e8"]
liability_colors = ["#d62728", "#ff9896", "#c5b0d5"]

for i, cat in enumerate(asset_cats):
    subset = cat_data[cat_data["group_name"] == cat]
    fig_cat.add_trace(go.Scatter(
        x=subset["snapshot_date"], y=subset["value"],
        mode="lines", name=cat, stackgroup="assets",
        line=dict(width=0.5, color=asset_colors[i % len(asset_colors)]),
    ))

for i, cat in enumerate(liability_cats):
    subset = cat_data[cat_data["group_name"] == cat]
    fig_cat.add_trace(go.Scatter(
        x=subset["snapshot_date"], y=subset["value"],
        mode="lines", name=cat, stackgroup="liabilities",
        line=dict(width=0.5, color=liability_colors[i % len(liability_colors)]),
    ))

fig_cat.update_layout(height=400, hovermode="x unified", margin=dict(l=20, r=20, t=10, b=20))
st.plotly_chart(fig_cat, use_container_width=True)

# ---- 单项明细 ----
st.divider()
st.subheader("单项明细")

active_items = items_df[items_df["active"]].sort_values(["group_name", "name"])
item_options = active_items[["id", "name", "group_name"]].copy()
item_options["label"] = item_options["group_name"] + " → " + item_options["name"]

selected_label = st.selectbox(
    "选择项目查看历史",
    item_options["label"].tolist(),
)

if selected_label:
    selected_row = item_options[item_options["label"] == selected_label].iloc[0]
    selected_id = int(selected_row["id"])

    item_history = df[df["item_id"] == selected_id].sort_values("snapshot_date")

    if item_history.empty:
        st.write("该项目暂无记录。")
    else:
        col_a, col_b = st.columns([3, 2])

        with col_a:
            fig_item = go.Figure()
            fig_item.add_trace(go.Scatter(
                x=item_history["snapshot_date"], y=item_history["value"],
                mode="lines+markers", name=selected_row["name"],
                line=dict(color="#1f77b4", width=2),
                fill="tozeroy", fillcolor="rgba(31,119,180,0.1)",
            ))
            fig_item.update_layout(
                title=f"{selected_row['name']} 历史变化",
                height=380, hovermode="x unified",
                margin=dict(l=20, r=20, t=40, b=20),
            )
            st.plotly_chart(fig_item, use_container_width=True)

        with col_b:
            table_rows = []
            prev_val = None
            for _, row in item_history.sort_values("snapshot_date", ascending=False).iterrows():
                cur_val = float(row["value"])
                if prev_val is not None:
                    change_str = f"¥{cur_val - prev_val:+,.2f}"
                else:
                    change_str = "-"
                table_rows.append({
                    "日期": row["snapshot_date"].strftime("%Y-%m-%d"),
                    "金额": f"¥{cur_val:,.2f}",
                    "较上期": change_str,
                })
                prev_val = cur_val

            st.dataframe(
                table_rows,
                use_container_width=True, hide_index=True,
            )
            st.caption(f"最新值：¥{item_history['value'].iloc[-1]:,.2f}")
