"""Owner tool: create an unlock code for a customer who has paid.

    export UNLOCK_SECRET="your-long-random-secret"        # same value as in the app's Secrets
    python make_codes.py PACK ACME 30                      # complete pack, valid 30 days
    python make_codes.py SLD  JOHNS 7                      # single line diagram only, 7 days

Windows PowerShell:   $env:UNLOCK_SECRET="your-long-random-secret"

Never share UNLOCK_SECRET or commit it to GitHub. Anyone with it can make codes.
"""

import datetime as dt
import os
import sys

from paywall import TIERS, clean_customer, make_code


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print(__doc__)
        return 2
    tier, customer, days = argv[1].upper(), argv[2], argv[3]
    secret = os.environ.get("UNLOCK_SECRET", "")
    if not secret:
        print("Set the UNLOCK_SECRET environment variable first (see the top of this file).")
        return 1
    if tier not in TIERS:
        print(f"Tier must be one of: {', '.join(TIERS)}")
        return 1
    if not days.isdigit() or not (1 <= int(days) <= 3650):
        print("Days must be a whole number between 1 and 3650.")
        return 1
    expires = dt.date.today() + dt.timedelta(days=int(days))
    print(make_code(secret, tier, customer, expires))
    print(f"(tier {tier}, customer {clean_customer(customer)}, valid until {expires})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
