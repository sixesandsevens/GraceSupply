# GraceSupply

Small internal supply inventory app for tracking cleaning supplies, resident supplies, paper goods, hygiene items, and other non-maintenance consumables.

## Local dev

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
flask --app run run --debug
```

Open: http://127.0.0.1:5000

## Current features

- Dashboard
- Add items
- Edit items
- Archive items
- Adjust inventory quantity
- Low-stock list
- Transaction history

## Notes

The SQLite database lives in `instance/gracesupply.db` and should not be committed to git.
