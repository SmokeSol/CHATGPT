#!/usr/bin/env python3
import goal75_local_closure_v2 as closure

# TAFRA labels this constituency Salé-Al Jadida; without the explicit alias,
# fuzzy matching can incorrectly select the six-seat El-Jadida constituency.
closure.CONFIG_TO_TAFRA["sale el jadida"] = "sale al jadida"

if __name__ == "__main__":
    raise SystemExit(closure.main())
