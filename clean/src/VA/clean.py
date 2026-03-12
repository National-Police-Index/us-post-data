import os
import pandas as pd
import re


def expand_abbreviations(text):
    if pd.isna(text):
        return text
    return pattern.sub(lambda m: abbr_map[m.group(0)], text)


# 1) Load raw data in original excel format and merge into one dataframe
df_active = pd.read_excel('Active-Inactive-LEO-JailOfficer 1-29-2026 Settlement Production.xlsx', sheet_name='Active')
df_inactive  = pd.read_excel('Active-Inactive-LEO-JailOfficer 1-29-2026 Settlement Production.xlsx', sheet_name='Inactive')
df = pd.concat([df_active, df_inactive], axis = 0, join = 'outer')

# 2) create version of dataframe to copy
df_merged = df.copy()

# 3) Rename existing column titles and reformat entries; Add optional fields 
df_merged.rename(columns  = {'OfficerID': 'person_nbr', 'EmployingEntityName': 'agency_name', 'HireDate': 'start_date', 'EndDate': 'end_date', 
                         'RankDesc': 'rank', 'FirstName':'first_name', 'LastName': 'last_name'}, inplace=True)
df_merged['state'] = 'va'
df_merged['first_name'] = df_merged['first_name'].str.replace('.', '', regex=False).str.upper()
df_merged['last_name'] = df_merged['last_name'].astype(str).str.replace('.', '', regex=False).str.upper()
df_merged['full_name'] = df_merged['first_name']+ ' ' + df_merged['last_name']
df_merged['agency_name'] = df_merged['agency_name'].str.replace('.', '', regex=False).str.upper()


# Fix formatting of dates
df_merged['start_date'] = pd.to_datetime(df_merged['start_date'].astype(str), errors = 'coerce').dt.strftime('%Y-%m-%d')
df_merged['end_date'] = pd.to_datetime(df_merged['end_date'].astype(str), errors='coerce').dt.strftime('%Y-%m-%d')

# Add offense information 
df_merged['offense'] = df_merged['DecertificationReason']
df_merged['separation_reason'] = None 
df_merged['separation_reason'][~(df_merged['DecertificationDate'].isna())] = 'decertified'
df_merged['separation_reason'][df_merged['DecertifiedByDCJS'] == 'Yes'] = 'decertified by DCJS'

# Fix formatting of rank titles (expand abbreviations). Appreviation map is based on most frequent abbreviations seen in this dataset
df_merged['rank'] = df_merged['rank'].str.replace('.', '', regex=False).str.upper()
abbr_map = {
    "ASST": "ASSISTANT",
    "SPEC": "SPECIAL",
    "LT": "LIEUTENANT",
    "SR": "SENIOR"}

pattern = re.compile(r"\b(" + "|".join(re.escape(k) for k in abbr_map.keys()) + r")\b") 
df_merged["rank"] = df_merged["rank"].apply(expand_abbreviations)

# 4) Select and order columns according to schema
output_columns = ['person_nbr', 'full_name', 'first_name', 'last_name', 'agency_name', 'rank', 'start_date', 'end_date', 'state', 'offense', 'separation_reason']
output_df = df_merged[output_columns]

save_path = 'processed_output/va_index.csv'
os.makedirs(os.path.dirname(save_path), exist_ok=True)
output_df.to_csv(save_path, index=False)