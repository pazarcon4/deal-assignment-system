CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('seller', 'sales_ops', 'admin')),
    password_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS deals (
    id SERIAL PRIMARY KEY,
    client_name TEXT NOT NULL,
    salesforce_ref TEXT,
    seller_id INTEGER NOT NULL REFERENCES users(id),
    assigned_to INTEGER REFERENCES users(id),
    stage TEXT NOT NULL DEFAULT 'unassigned'
        CHECK(stage IN ('unassigned', 'pending_acceptance', 'accepted', 'in_progress', 'submitted')),
    target_submission_date TEXT,
    actual_submission_date TEXT,
    notes TEXT,
    tcv_usd NUMERIC(14, 2),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

ALTER TABLE deals ADD COLUMN IF NOT EXISTS tcv_usd NUMERIC(14, 2);
