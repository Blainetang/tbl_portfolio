"""
数据库操作层 — 封装 Supabase 查询。
所有跨表关联在 pandas 中完成，避免 supabase-py 嵌套 select 的兼容问题。
"""

import pandas as pd
import streamlit as st
from supabase import create_client, Client


class Database:
    def __init__(self, url: str, key: str):
        self.client: Client = create_client(url, key)

    def _data(self, query) -> list[dict]:
        result = query.execute()
        return result.data or []

    # ---- Groups ----

    def get_groups_df(self) -> pd.DataFrame:
        data = self._data(
            self.client.table("groups").select("*").order("sort_order")
        )
        return pd.DataFrame(data) if data else pd.DataFrame()

    def add_group(self, name: str, group_type: str, parent_id: int | None = None) -> dict:
        data = self._data(
            self.client.table("groups")
            .insert({"name": name, "type": group_type, "parent_id": parent_id})
            .select()
        )
        return data[0] if data else {}

    def update_group(self, group_id: int, **kwargs) -> None:
        self.client.table("groups").update(kwargs).eq("id", group_id).execute()

    def delete_group(self, group_id: int) -> None:
        self.client.table("groups").delete().eq("id", group_id).execute()

    # ---- Items ----

    def get_items_df(self, active_only: bool = True) -> pd.DataFrame:
        query = self.client.table("items").select("*").order("sort_order")
        if active_only:
            query = query.eq("active", True)
        items_data = self._data(query)
        groups_data = self._data(
            self.client.table("groups")
            .select("id, name, type, parent_id")
            .order("sort_order")
        )

        items_df = pd.DataFrame(items_data) if items_data else pd.DataFrame()
        groups_df = pd.DataFrame(groups_data) if groups_data else pd.DataFrame()

        if items_df.empty:
            return pd.DataFrame(columns=[
                "id", "name", "group_id", "sort_order", "active",
                "created_at", "group_name", "group_type", "parent_id",
            ])

        g = groups_df.rename(
            columns={"id": "gid", "name": "group_name", "type": "group_type"}
        )
        items_df = items_df.merge(g, left_on="group_id", right_on="gid")
        items_df.drop(columns=["gid"], inplace=True)
        return items_df

    def add_item(self, name: str, group_id: int) -> dict:
        data = self._data(
            self.client.table("items")
            .insert({"name": name, "group_id": group_id})
            .select()
        )
        return data[0] if data else {}

    def update_item(self, item_id: int, **kwargs) -> None:
        self.client.table("items").update(kwargs).eq("id", item_id).execute()

    # ---- Snapshots ----

    def get_latest_date(self) -> str | None:
        data = self._data(
            self.client.table("snapshots")
            .select("snapshot_date")
            .order("snapshot_date", desc=True)
            .limit(1)
        )
        return data[0]["snapshot_date"] if data else None

    def get_all_dates(self) -> list[str]:
        data = self._data(
            self.client.table("snapshots")
            .select("snapshot_date")
            .order("snapshot_date", desc=True)
        )
        seen = set()
        dates = []
        for d in data:
            dt = d["snapshot_date"]
            if dt not in seen:
                seen.add(dt)
                dates.append(dt)
        return dates

    def get_snapshot_df(self, date_str: str) -> pd.DataFrame:
        data = self._data(
            self.client.table("snapshots")
            .select("*")
            .eq("snapshot_date", date_str)
        )
        return pd.DataFrame(data) if data else pd.DataFrame()

    def get_history_df(self, start_date: str, end_date: str) -> pd.DataFrame:
        data = self._data(
            self.client.table("snapshots")
            .select("*")
            .gte("snapshot_date", start_date)
            .lte("snapshot_date", end_date)
            .order("snapshot_date")
        )
        return pd.DataFrame(data) if data else pd.DataFrame()

    def get_previous_values(self, before_date: str) -> dict[int, float]:
        """获取每个 item 在 before_date 之前的最新值，用于录入页预填。"""
        data = self._data(
            self.client.table("snapshots")
            .select("item_id, value, snapshot_date")
            .lt("snapshot_date", before_date)
            .order("snapshot_date", desc=True)
        )
        result: dict[int, float] = {}
        for d in data:
            if d["item_id"] not in result:
                result[d["item_id"]] = float(d["value"])
        return result

    def save_snapshot(self, date_str: str, values: dict[int, float]) -> None:
        self.client.table("snapshots").delete().eq("snapshot_date", date_str).execute()
        rows = [
            {"item_id": k, "snapshot_date": date_str, "value": v}
            for k, v in values.items()
        ]
        if rows:
            self.client.table("snapshots").insert(rows).execute()


@st.cache_resource
def get_db() -> Database:
    return Database(st.secrets["supabase_url"], st.secrets["supabase_key"])
