-- 001: users, prediction history and the evaluation table of every training run.
-- Timestamps are UTC, ISO 8601 with a trailing Z.

CREATE TABLE users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT    NOT NULL,
    created_at    TEXT    NOT NULL
);

CREATE TABLE predictions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at      TEXT    NOT NULL,
    task            TEXT    NOT NULL CHECK (task IN ('regression', 'classification')),
    model           TEXT    NOT NULL,
    input_json      TEXT    NOT NULL,
    predicted_value REAL,
    predicted_label TEXT,
    actual_value    REAL,
    runtime_ms      REAL,
    batch_id        TEXT
);
CREATE INDEX idx_predictions_user_time ON predictions (user_id, created_at);

CREATE TABLE training_runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at    TEXT    NOT NULL,
    trained_at    TEXT,
    target        TEXT,
    train_size    INTEGER,
    test_size     INTEGER,
    best_model    TEXT,
    total_seconds REAL
);

CREATE TABLE model_runs (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id                INTEGER NOT NULL REFERENCES training_runs(id) ON DELETE CASCADE,
    model                 TEXT    NOT NULL,
    label                 TEXT,
    r2                    REAL,
    mae                   REAL,
    mse                   REAL,
    rmse                  REAL,
    cv_r2_mean            REAL,
    cv_r2_std             REAL,
    train_seconds         REAL,
    predict_ms_per_sample REAL,
    n_nonzero_coef        INTEGER,
    n_coefficients        INTEGER,
    best_params_json      TEXT,
    is_best               INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_model_runs_run ON model_runs (run_id);
