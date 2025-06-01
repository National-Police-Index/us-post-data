import sys

import pandas as pd


def expand_agency_abbreviations(agencies):
    """Expand all abbreviations in the name of the agency, e.g.:
    'CHP' to 'California Highway Patrol',
    'PD' to 'Police Department',
    'CO' or 'CO.' to 'County',
    etc
    """
    replacements = {
        r'\bCHP\b': 'CALIFORNIA HIGHWAY PATROL',
        r'\bPD\b': 'POLICE DEPARTMENT',
        r'\bCO\b\.?': 'COUNTY',
        r'\bCORR\b': 'CORRECTIONS ',
        r'\bCOUNTY SD\b': "COUNTY SHERIFF'S DEPARTMENT",
        r'\bCOUNTY SO\b': "COUNTY SHERIFF'S OFFICE",
        r'\bDA\b': 'DISTRICT ATTORNEY',
        r'\bCA\b\.?': 'CALIFORNIA',
        r'\bCNTR\b': 'CENTER',
        r'\bDEPT\b': 'DEPARTMENT',
        r'\bSVS\b': 'SERVICES',
        r'\bSVCS\b': 'SERVICES',
        r'\bDIV\b': 'DIVISION',
        r'\bDIST\b': 'DISTRICT',
        r'\bENF\b': 'ENFORCEMENT',
        r'\bYTH\b': 'YOUTH',
        r'\bPUB': 'PUBLIC',
        r'\bSFTY\b': 'SAFETY',
        r'\bCCD\b': 'COMMUNITY COLLEGE DISTRICT',
        r'\bCSU\b': 'CALIFORNIA STATE UNIVERSITY',
        r'\bDPS\b': 'DEPARTMENT OF PUBLIC SAFETY',
        r'\bUC\b': 'UNIVERSITY OF CALIFORNIA',
        r'\bUNIF\b': 'UNIFIED',
        r'\bSCHL\b': 'SCHOOL',
        r'\bUSD\b': 'UNIFIED SCHOOL DISTRICT',
        r'\bOFC\b': 'OFFICE'
    }
    out = agencies
    out = out.str.replace(r'\s+', ' ', regex=True).str.strip()
    for pattern, replacement in replacements.items():
        out = out.str.replace(pattern, replacement, regex=True)
    out = out.str.replace(r'\s+', ' ', regex=True).str.strip()
    return out

if __name__ == "__main__":
    inleo = sys.argv[1]
    incor = sys.argv[2]
    outname = sys.argv[3]

    leo = pd.read_csv(inleo).reset_index(drop=True)
    cor = pd.read_csv(incor).reset_index(drop=True)
    cor.person_nbr = cor.person_nbr.astype(str)
    out = pd.concat([leo, cor])
    out['agency_name'] = expand_agency_abbreviations(out['agency_name'])
    out.to_csv(outname, index=False)
