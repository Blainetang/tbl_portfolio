-- ============================================================
-- Portfolio Manager - Supabase 数据库初始化
-- 在 Supabase SQL Editor 中执行此文件（可重复执行）
-- ============================================================

CREATE TABLE IF NOT EXISTS groups (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  type TEXT NOT NULL CHECK (type IN ('asset', 'liability')),
  parent_id INTEGER REFERENCES groups(id) ON DELETE CASCADE,
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS items (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  group_id INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
  sort_order INTEGER NOT NULL DEFAULT 0,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS snapshots (
  id SERIAL PRIMARY KEY,
  item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
  snapshot_date DATE NOT NULL,
  value DECIMAL(15,2) NOT NULL DEFAULT 0,
  note TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(item_id, snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_groups_parent ON groups(parent_id);
CREATE INDEX IF NOT EXISTS idx_items_group ON items(group_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_date ON snapshots(snapshot_date);
CREATE INDEX IF NOT EXISTS idx_snapshots_item ON snapshots(item_id);

ALTER TABLE groups DISABLE ROW LEVEL SECURITY;
ALTER TABLE items DISABLE ROW LEVEL SECURITY;
ALTER TABLE snapshots DISABLE ROW LEVEL SECURITY;

INSERT INTO groups (id, name, type, parent_id, sort_order) VALUES
  (1, '资产', 'asset', NULL, 1),
  (2, '负债', 'liability', NULL, 2),
  (3, '金融资产', 'asset', 1, 1),
  (4, '流动现金', 'asset', 1, 2),
  (5, '信用卡', 'liability', 2, 1)
ON CONFLICT (id) DO NOTHING;

SELECT setval('groups_id_seq', (SELECT MAX(id) FROM groups));
