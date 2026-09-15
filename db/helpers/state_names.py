"""Map two-letter state codes to the full names Firebase is keyed on.

Codes (``ca``) are used for Dropbox paths, ``states/`` dirs and the registry;
full hyphenated names (``california``, ``new-mexico``) are the Firestore
document prefix, ``state`` field, and front-end script argument.

``STATE_NAMES`` mirrors ``constants/states.ts`` in the front-end repo.
"""

STATE_NAMES = {
    "al": "alabama",
    "ak": "alaska",
    "az": "arizona",
    "ar": "arkansas",
    "ca": "california",
    "co": "colorado",
    "ct": "connecticut",
    "de": "delaware",
    # The front-end uses "columbia" (not "district-of-columbia") for DC.
    "dc": "columbia",
    "fl": "florida",
    "ga": "georgia",
    "hi": "hawaii",
    "id": "idaho",
    "il": "illinois",
    "in": "indiana",
    "ia": "iowa",
    "ks": "kansas",
    "ky": "kentucky",
    "la": "louisiana",
    "me": "maine",
    "md": "maryland",
    "ma": "massachusetts",
    "mi": "michigan",
    "mn": "minnesota",
    "ms": "mississippi",
    "mo": "missouri",
    "mt": "montana",
    "ne": "nebraska",
    "nv": "nevada",
    "nh": "new-hampshire",
    "nj": "new-jersey",
    "nm": "new-mexico",
    "ny": "new-york",
    "nc": "north-carolina",
    "nd": "north-dakota",
    "oh": "ohio",
    "ok": "oklahoma",
    "or": "oregon",
    "pa": "pennsylvania",
    "pr": "puerto-rico",
    "ri": "rhode-island",
    "sc": "south-carolina",
    "sd": "south-dakota",
    "tn": "tennessee",
    "tx": "texas",
    "ut": "utah",
    "vt": "vermont",
    "va": "virginia",
    "wa": "washington",
    "wv": "west-virginia",
    "wi": "wisconsin",
    "wy": "wyoming",
}

FULL_NAMES = frozenset(STATE_NAMES.values())


def resolve_state_name(state):
    """Return the full state name for a code or full name; raise if unknown.

    resolve_state_name("ca")          -> "california"
    resolve_state_name("california")  -> "california"
    resolve_state_name("new_mexico")  -> "new-mexico"
    """
    key = str(state).strip().lower().replace("_", "-").replace(" ", "-")
    if key in STATE_NAMES:
        return STATE_NAMES[key]
    if key in FULL_NAMES:
        return key
    raise ValueError(
        f"Unknown state {state!r}. Expected a lowercase two-letter code "
        f"(e.g. 'ca') or a full hyphenated name (e.g. 'california'). "
        f"Add it to STATE_NAMES in db/state_names.py if it is new."
    )
