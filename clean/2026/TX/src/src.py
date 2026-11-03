import pandas as pd
import re

def read_tbl():
    df = pd.read_csv("../data/input/post_data_texas.csv")  # need to update this 
    # what is PUBLIC ID?
    # unnamed 7 is a fully null column that should be dropped (artifact of this table previously existing as xlsx)
    df = df.drop(columns=["Unnamed: 7"])
    df = df.rename(columns={"PUBLIC ID": "uid",   # stable per-person id
                            "FULL NAME": "full_name",
                            "DOB": "birth_date",
                            "DEPARTMENT NAME": "agency_name",
                            "SERVICE": "status_type",
                            "START DATE": "hire_date",
                            "END DATE": "end_date"})

    df = df.fillna("")

    ## many rows are missing agency_name, hire_date, and end_date which is weird. drop all of these. flagging as a data production issue.
    ## notified team of data quality. another request is out 

    df = df[~((df.hire_date == ""))]
    return df

def clean_agency_name(df):
    _ACRONYMS = [
        (r"\bc\.\s*i\.\s*s\.\s*d\.", "consolidated independent school district"),
        (r"\bi\.\s*s\.\s*d\.", "independent school district"),
        (r"\bd\.\s*p\.\s*s\.", "department of public safety"),
        (r"\bp\.\s*d\.", "police department"),
        (r"\bd\.\s*a\.", "district attorney"),
        (r"\bs\.\s*d\.", "school district"),
        (r"\bu\.\s*s\.", "us"),
    ]

    _ABBREVS = [
        (r"\bco\.", "county"),
        (r"\bdist\.", "district"),
        (r"\bdept\.", "department"),
        (r"\bdeten\.", "detention"),
        (r"\bconst\.", "constable"),
        (r"\bpct\.", "precinct"),        
        (r"\buniv\.", "university"),
        (r"\bmunic\.", "municipal"),
        (r"\bmun\.", "municipal"),
        (r"\butil\.", "utility"),
        (r"\breg\.", "regional"),
        (r"\bintl\.", "international"),
        (r"\bcrim\.", "criminal"),
        (r"\bauth\.", "authority"),
        (r"\binvest\.", "investigation"),
        (r"\bivest\.", "investigation"),  
        (r"\binv\.", "investigation"),
        (r"\bprev\.", "prevention"),
        (r"\bvolun\.", "volunteer"),
        (r"\bhosp\.", "hospital"),
        (r"\bsupp\.", "supply"),
        (r"\bcont\.", "control"),
        (r"\batty\.'s", "attorney's"),
        (r"\batty\.", "attorney"),
        (r"\batt\.", "attorney"),
        (r"\bdiv\.", "division"),
        (r"\btech\.", "technical"),
        (r"\btex\.", "texas"),
        (r"\bjr\.", "junior"),
        (r"\boff\.", "office"),
        (r"\bst\.", "saint"),             
        (r"\bcomm\. college", "community college"), 
    ]

    s = df.agency_name.str.lower().str.strip()

    for pat, repl in _ACRONYMS:
        s = s.str.replace(pat, repl, regex=True)
    for pat, repl in _ABBREVS:
        s = s.str.replace(pat, repl, regex=True)

    # spelling fix in source data
    s = s.str.replace(r"\bwest virgina\b", "west virginia", regex=True)

    # strip trailing dept-id codes, e.g. "reno police department (367204) - 367204"
    s = s.str.replace(r"\s*\(\d+\)\s*(-\s*\d+)?\s*$", "", regex=True)
    s = s.str.replace(r"\s*-\s*\d+\s*$", "", regex=True)
    # drop trailing "(inactive)" marker and any trailing comma/period/whitespace
    s = s.str.replace(r"\s*\(inactive\)\s*$", "", regex=True)
    s = s.str.replace(r"[,.\s]+$", "", regex=True)
    # normalize "# 1" / "no. 1" spacing and collapse repeated whitespace
    s = s.str.replace(r"#\s*(\d+)", r"#\1", regex=True)
    s = s.str.replace(r"\s{2,}", " ", regex=True)

    df.loc[:, "agency_name"] = s
    return df


def _is_initial(tok):
    return re.fullmatch(r"[A-Za-z]\.?", tok) is not None


def _key(tok):
    return tok.replace(".", "").lower()


def _split_one(raw):

    _SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix"}

    _PARTICLES = {
        "de", "del", "dela", "della", "dello", "delos", "dellos", "la", "las", "los",
        "le", "van", "von", "der", "den", "di", "da", "du", "dos", "das", "des",
        "san", "santa", "saint", "st", "ste", "y",
    }
    name = re.sub(r"\s+", " ", str(raw)).strip()
    # a hyphen spaced on BOTH sides ("Jeannine - Langley", "Farmer - Hassan") is a
    # separator → space; a hyphen attached on either side ("Choice -Farkasdi",
    # "Williams- Turner") is a real hyphenated name → join.
    name = re.sub(r"\s+-\s+", " ", name)
    name = re.sub(r"\s*-\s*", "-", name)
    name = name.replace(",", " ")         
    name = re.sub(r"\s+", " ", name).strip()
    toks = name.split(" ") if name else []

    # collapse consecutive identical single-initials, e.g. "D D" → "D"
    collapsed = []
    for t in toks:
        if (collapsed and _is_initial(t) and _is_initial(collapsed[-1])
                and _key(t) == _key(collapsed[-1])):
            continue
        collapsed.append(t)
    toks = collapsed

    # pull generational suffix(es) off the end (keep ≥2 tokens for first + last)
    suffix = ""
    while len(toks) >= 3 and _key(toks[-1]) in _SUFFIXES:
        tok = toks[-1].rstrip(".")
        suffix = tok if not suffix else tok + " " + suffix
        toks = toks[:-1]

    first = middle = last = ""
    n = len(toks)
    if n == 1:
        first = toks[0]
    elif n == 2:
        first, last = toks
    elif n >= 3:
        # pivot on the first single-initial in positions 1..n-2 (the middle)
        pivot = next((i for i in range(1, n - 1) if _is_initial(toks[i])), None)
        if pivot is not None:
            first = " ".join(toks[:pivot])
            middle = toks[pivot]
            last = " ".join(toks[pivot + 1:])
        else:
            # no middle initial: last = trailing surname + any leading particles.
            j = n - 1
            while j - 1 >= 1 and _key(toks[j - 1]) in _PARTICLES:
                j -= 1
            rest = toks[:j]                    # everything before the surname block
            first = rest[0]
            # a single leftover bare word is treated as a middle name (the
            # deliberate choice for the ambiguous compound-first vs double-surname
            # case). If MORE than one word is left, only the first is the middle;
            # the rest are additional surname components ("Iris Ann Gutierrez
            # Perez" → middle "Ann", last "Gutierrez Perez"), since a middle is
            # never more than one word here.

            middle = rest[1] if len(rest) >= 2 else ""
            last = " ".join(rest[2:] + toks[j:])

    return pd.Series({"first_name": first, "middle_name": middle,
                      "last_name": last, "suffix": suffix})


def split_full_name(df):
    """Split `full_name` (First [Middle] Last [Suffix]) into components.
    """
    # parse each distinct name once, then map back (306k unique of 752k rows)
    uniq = df.full_name.astype(str).drop_duplicates()
    parsed = uniq.apply(_split_one)
    parsed.index = uniq.values
    lookup = parsed.to_dict("index")

    for col in ["first_name", "middle_name", "last_name", "suffix"]:
        df[col] = df.full_name.astype(str).map(lambda n: lookup[n][col])
    return df


if __name__ == "__main__":
    df = (read_tbl()
          .pipe(clean_agency_name)
          .pipe(split_full_name))

    df.to_csv("../data/output/tx_data_cleaned_2026.csv", index=False)

    ## remove this piece of code for prroduction
    empty_last = (df.last_name.str.strip() == "").sum()
    print("rows:", len(df), " missing last_name:", empty_last)
    print(df[["full_name", "first_name", "middle_name", "last_name", "suffix"]]
          .drop_duplicates().head(15).to_string(index=False))

    # validation: how many trailing-period abbreviations remain? we should remove this piece of code for production
    ag = sorted(df.agency_name.unique().tolist())
    remaining = {}
    for a in ag:
        for m in re.findall(r"\b[a-z]+\.", a):
            remaining[m] = remaining.get(m, 0) + 1
    print("unique agencies:", len(ag))
    print("remaining trailing-period tokens:", sum(remaining.values()))
    for k, v in sorted(remaining.items(), key=lambda x: -x[1]):
        print(f"  {k:12} {v}")
