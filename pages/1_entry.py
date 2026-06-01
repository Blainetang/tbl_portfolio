"""
每周数据录入
"""

from datetime import date, timedelta

import streamlit as st

from db import get_db


st.set_page_config(page_title="数据录入", layout="wide")


def check_config():
    if "supabase_url" not in st.secrets or "supabase_key" not in st.secrets:
        st.error("请先配置 Supabase 连接。")
        st.stop()


check_config()
db = get_db()

st.title("每周数据录入")

# 默认日期：最近一个周日
today = date.today()
days_since_sunday = (today.weekday() + 1) % 7
default_date = today - timedelta(days=days_since_sunday)

snapshot_date = st.date_input("记录日期", value=default_date, max_value=today)
date_str = snapshot_date.isoformat()

# 加载数据
items_df = db.get_items_df(active_only=True)
groups_df = db.get_groups_df()

if items_df.empty:
    st.warning("还没有添加任何资产/负债项目，请先在「配置」页面添加。")
    st.stop()

# 获取上一次的值用于预填
previous_values = db.get_previous_values(date_str)

# 检查该日期是否已有记录
existing = db.get_snapshot_df(date_str)
existing_map: dict[int, float] = {}
if not existing.empty:
    for _, row in existing.iterrows():
        existing_map[row["item_id"]] = float(row["value"])

st.caption(f"共 {len(items_df)} 个项目，数值沿用上期，可只修改有变动的部分。")

# 按 group 分组展示
current_values: dict[int, float] = {}
group_order = groups_df[groups_df["parent_id"].notna()].sort_values("sort_order")

for _, group in group_order.iterrows():
    group_items = items_df[items_df["group_id"] == group["id"]]
    if group_items.empty:
        continue

    with st.expander(f"{group['name']}（{len(group_items)} 项）", expanded=True):
        group_total = 0.0
        for _, item in group_items.iterrows():
            item_id = int(item["id"])
            # 优先使用已保存的值，否则用上期值，最后用 0
            if item_id in existing_map:
                default_val = existing_map[item_id]
            else:
                default_val = previous_values.get(item_id, 0.0)

            val = st.number_input(
                f"{item['name']}",
                value=float(default_val),
                step=1000.0,
                format="%.2f",
                key=f"entry_{item_id}_{date_str}",
            )
            current_values[item_id] = val
            group_total += val
        st.caption(f"小计：¥{group_total:,.2f}")

st.divider()

if st.button("保存", type="primary", use_container_width=True):
    with st.spinner("保存中..."):
        db.save_snapshot(date_str, current_values)
    st.success(f"已保存 {date_str} 的数据，共 {len(current_values)} 项。")
    st.rerun()
