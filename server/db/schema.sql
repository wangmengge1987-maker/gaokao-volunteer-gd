-- 广东省本科普通批 — 数据库 Schema

CREATE TABLE IF NOT EXISTS score_rank (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year INTEGER NOT NULL,
    province TEXT NOT NULL DEFAULT '广东',
    subject_track TEXT NOT NULL,  -- 物理 / 历史
    score INTEGER NOT NULL,
    rank INTEGER NOT NULL,
    cumulative_count INTEGER,
    UNIQUE(year, province, subject_track, score)
);

CREATE TABLE IF NOT EXISTS enrollment_plan (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year INTEGER NOT NULL,
    province TEXT NOT NULL DEFAULT '广东',
    batch TEXT NOT NULL DEFAULT '本科普通批',
    school_code TEXT NOT NULL,
    school_name TEXT NOT NULL,
    group_code TEXT NOT NULL,
    group_name TEXT,
    major_code TEXT,
    major_name TEXT,
    subject_requirement TEXT,  -- 如: 化学,地理
    subject_track TEXT NOT NULL DEFAULT '物理',  -- 物理 / 历史（3+1+2 首选科目）
    plan_count INTEGER NOT NULL DEFAULT 0,
    school_level TEXT,       -- 985/211/双一流/普通本科
    city TEXT,
    UNIQUE(year, school_code, group_code, major_code)
);

CREATE TABLE IF NOT EXISTS admission_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year INTEGER NOT NULL,
    province TEXT NOT NULL DEFAULT '广东',
    batch TEXT NOT NULL DEFAULT '本科普通批',
    school_code TEXT NOT NULL,
    school_name TEXT NOT NULL,
    group_code TEXT NOT NULL,
    group_name TEXT,
    subject_track TEXT NOT NULL DEFAULT '物理',  -- 物理 / 历史
    min_score INTEGER,
    min_rank INTEGER,
    plan_count INTEGER,
    UNIQUE(year, school_code, group_code)
);

CREATE INDEX IF NOT EXISTS idx_score_rank_lookup
    ON score_rank(year, subject_track, score DESC);

CREATE INDEX IF NOT EXISTS idx_admission_group
    ON admission_history(school_code, group_code, year DESC);

CREATE INDEX IF NOT EXISTS idx_plan_batch
    ON enrollment_plan(year, batch, subject_requirement);
