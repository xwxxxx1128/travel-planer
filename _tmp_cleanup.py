import sqlite3

UNUSED = ["aircrafts_data", "seats", "bookings"]
for db in ["travel_new.sqlite", "travel2.sqlite"]:
    c = sqlite3.connect(db)
    before = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    for t in UNUSED:
        c.execute(f"DROP TABLE IF EXISTS {t}")
    c.commit()
    after = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    c.close()
    print(f"[{db}] before={before}")
    print(f"[{db}] after ={after}")
    print()
