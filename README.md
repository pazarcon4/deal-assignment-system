# Deal Assignment System

Solves one problem: sellers can't see how loaded up each sales ops person is,
so they can't tell who to ask for help with a new deal. This gives everyone a
shared workload board (grouped by sales ops person, sorted by how close each
deal is to its target client submission date) plus a simple assign / accept /
update flow.

## How it works

- **Sellers** create a deal (client name, optional Salesforce link/ID, target
  submission date to the client) and assign it directly to a sales ops person
  — using the workload board to see who has room.
- **Sales ops** see deals assigned to them and can **accept** or **decline**.
  Declining returns the deal to the seller as unassigned so it can be
  reassigned to someone else.
- Once accepted, sales ops moves the deal through **in progress → submitted**,
  updating the target submission date and notes as things change. Submitted
  deals drop off the active workload board.
- The Salesforce field is just a manually-entered link or opportunity ID for
  reference — there's no live Salesforce sync in this version.

## Setup

Requires Python 3. From this directory:

```bash
python3 -m pip install -r requirements.txt
```

Edit `seed.py` and replace the placeholder names/emails in `SEED_USERS` with
your actual 4 sellers and 3 sales ops people, then run:

```bash
python3 seed.py
```

This creates the database (`instance/deals.db`) and prints a generated
password for each person — share those out of band and have everyone change
their password after first login (top nav → Account).

Re-running `seed.py` later is safe — it only adds users with emails that
don't already exist, it won't duplicate or overwrite anyone.

## Running

```bash
python3 app.py
```

The app runs at http://127.0.0.1:5050 by default. Anyone on the same machine
or network (adjust host/port in `app.py` if you need it reachable from other
devices) can log in with their seeded email and password.

## Notes / limitations

- Built for a small trusted team (7 people) on a local network — there's no
  CSRF token, rate limiting, or HTTPS. Don't expose this directly to the
  public internet as-is.
- Data lives in `instance/deals.db` (SQLite). Back that file up if you care
  about the history.
- `instance/secret_key` is generated on first run and signs login sessions —
  don't delete it while people are logged in (it just logs everyone out, not
  destructive to data).
