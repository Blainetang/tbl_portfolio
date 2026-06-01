"""
项目配置 — 管理资产/负债项目和分类
"""

import streamlit as st

from db import get_db


st.set_page_config(page_title="项目配置", layout="wide")


def check_config():
    if "supabase_url" not in st.secrets or "supabase_key" not in st.secrets:
        st.error("请先配置 Supabase 连接。")
        st.stop()


check_config()
db = get_db()

st.title("项目配置")

groups_df = db.get_groups_df()
items_df = db.get_items_df(active_only=False)

# ---- 当前层级结构 ----
st.subheader("当前结构")

if groups_df.empty:
    st.warning("尚未初始化分类。请在 Supabase SQL Editor 中执行 setup.sql。")
    st.stop()

# 构建树形展示
top_groups = groups_df[groups_df["parent_id"].isna()].sort_values("sort_order")

for _, top in top_groups.iterrows():
    type_label = "资产" if top["type"] == "asset" else "负债"
    st.markdown(f"### {top['name']}（{type_label}）")

    children = groups_df[groups_df["parent_id"] == top["id"]].sort_values("sort_order")
    for _, child in children.iterrows():
        st.markdown(f"**{child['name']}**")
        if items_df.empty:
            st.write("　　*暂无项目*")
        else:
            child_items = items_df[items_df["group_id"] == child["id"]]
            if child_items.empty:
                st.write("　　*暂无项目*")
            else:
                for _, item in child_items.iterrows():
                    status = "" if item["active"] else " `已停用`"
                    st.write(f"　　• {item['name']}{status}")

st.divider()

# ---- 添加项目 ----
st.subheader("添加项目")

# 只显示叶子分类（有父级的分类）
leaf_groups = groups_df[groups_df["parent_id"].notna()].sort_values("sort_order")
group_options = leaf_groups[["id", "name"]].copy()
group_labels = group_options["name"].tolist()

with st.form("add_item_form", clear_on_submit=True):
    new_name = st.text_input("项目名称", placeholder="例：沪深300 ETF")
    selected_group = st.selectbox("所属分类", group_labels)
    submitted = st.form_submit_button("添加", use_container_width=True)

    if submitted and new_name.strip():
        group_id = int(group_options[group_options["name"] == selected_group]["id"].values[0])
        db.add_item(new_name.strip(), group_id)
        st.success(f"已添加「{new_name.strip()}」")
        st.rerun()
    elif submitted:
        st.error("项目名称不能为空")

# ---- 管理现有项目 ----
st.divider()
st.subheader("管理项目")

active_items = items_df[items_df["active"]]
if active_items.empty:
    st.write("暂无活跃项目。")
else:
    item_names = active_items[["id", "name", "group_name"]].copy()
    item_labels = item_names.apply(lambda r: f"{r['name']}（{r['group_name']}）", axis=1).tolist()

    selected_item_label = st.selectbox("选择要编辑的项目", item_labels)
    if selected_item_label:
        selected_idx = item_labels.index(selected_item_label)
        selected_item = item_names.iloc[selected_idx]
        item_id = int(selected_item["id"])

        col_a, col_b = st.columns([3, 1])
        with col_a:
            new_item_name = st.text_input("名称", value=selected_item["name"], key=f"edit_name_{item_id}")
        with col_b:
            new_group = st.selectbox(
                "分类",
                group_labels,
                index=group_labels.index(selected_item["group_name"])
                if selected_item["group_name"] in group_labels else 0,
                key=f"edit_group_{item_id}",
            )

        col_c, col_d, _ = st.columns([1, 1, 3])
        with col_c:
            if st.button("保存修改", key=f"save_{item_id}"):
                new_group_id = int(group_options[group_options["name"] == new_group]["id"].values[0])
                db.update_item(item_id, name=new_item_name, group_id=new_group_id)
                st.success("已更新")
                st.rerun()
        with col_d:
            if st.button("停用", key=f"deactivate_{item_id}", type="secondary"):
                db.update_item(item_id, active=False)
                st.success(f"已停用「{selected_item['name']}」")
                st.rerun()

# ---- 已停用项目 ----
inactive_items = items_df[~items_df["active"]]
if not inactive_items.empty:
    st.divider()
    st.subheader("已停用项目")
    for _, item in inactive_items.iterrows():
        col_a, col_b = st.columns([4, 1])
        with col_a:
            st.write(f"• {item['name']}（{item['group_name']}）")
        with col_b:
            if st.button("重新启用", key=f"reactivate_{item['id']}"):
                db.update_item(int(item["id"]), active=True)
                st.rerun()
