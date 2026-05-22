import pandas as pd
path_to_all_records = 'all_NPI_OOVA_matches.csv'
n_samples = 4
sample_size = 500

""" this script produces 3 types exports --
(1) NPI_OOVA_match_table with fields person_nbr,oova_id (officer_id in original file), and confidence level of match
(2) Match table for exact and high confidence matches & optionally(medium high matches, low matches) for reviewers to quickly skim
(3) Samples of medium-high confidence matches for reviewers to check thoroughly and mark whether there is a real match or not. 
These samples are produced using parameters above -- n_samples, and sample size. Arguments only need to be entered into the main function. 
"""



def process_data(path_to_records):

    # organizes all matches by filtering based on confidence levels, and producing a clean table with just IDs and match information.
    all_matches = pd.read_csv(path_to_all_records)

    # for stints that fall into multiple confidence groups based on categories, round to lowest confidence tier, dropping any NPI-OOVA pair duplicates
    all_matches['min_score'] = all_matches[['agency_name_score', 'full_name_score']].min(axis=1)
    keys = ['person_nbr', 'officer_id', 'full_name', 'agency_name', 'start_date', 'end_date']
    all_matches = (all_matches.sort_values('min_score', ascending=True).drop_duplicates(subset=keys, keep='first'))

    #there should be no NPI-OOVA duplicates at this point
    matches_collapsed = (all_matches.groupby(['person_nbr'], as_index=True).apply(collapse_history).reset_index(drop=False)).reset_index(drop=True) 
    matches_collapsed['confidence_level'] = 'none'
    matches_collapsed['confidence_level'].loc[(matches_collapsed['min_score'] == 1)] = 'exact'
    matches_collapsed['confidence_level'].loc[(matches_collapsed['min_score'] > .9)&(matches_collapsed['min_score'] < 1)] = 'high'
    matches_collapsed['confidence_level'].loc[(matches_collapsed['min_score'] > .8)&(matches_collapsed['min_score'] <= .9)] = 'medium-high'
    matches_collapsed['confidence_level'].loc[(matches_collapsed['min_score'] >= .68)&(matches_collapsed['min_score'] <= .8)] = 'low'
    npi_oov_match_table = matches_collapsed.drop(columns = ['min_score','full_name_npi', 'full_name_oova', 'npi_history', 'oova_history'])
    
    # cases with multiple OOVA ids corresponding to the same person_nbr are brought to the top for review purposes (there are ~ 5 cases like this)
    npi_oov_match_table = reorder_dataframes_for_review(npi_oov_match_table)
    npi_oov_match_table.to_csv("NPI_OOVA_match_table.csv", index=False)
    return matches_collapsed


def collapse_history(group):
    # this collapses history (multiple stints) of unique person-nbr and OOVA links. 
    group = group.sort_values('start_date')
    npi_history = '\n'.join(f"{row.start_date} - {row.end_date}: {row.agency_name}" for row in group.itertuples())
    oova_history = '\n'.join(f"{row.start_date} - {row.end_date}: {row.oov_agency_name}" for row in group.itertuples())
  
    scalar_entry  = group.loc[group['min_score'].idxmin()]
    middle = scalar_entry['oov_middle_initial']
    middle_str = f"{middle} " if pd.notna(middle) and str(middle).strip() else ""
    officer_id_entry  = group['officer_id'].unique().tolist() if group['officer_id'].nunique() > 1 else group['officer_id'].values[0]
    return pd.Series({
        'min_score': scalar_entry['min_score'],
        'oova_id': officer_id_entry,
        'full_name_npi': scalar_entry['first_name_npi'] + ' ' + scalar_entry['last_name_npi'],
        'full_name_oova': scalar_entry['first_name_oov'] + ' ' + middle_str + ' ' + scalar_entry['last_name_oov'], 
        'npi_history': npi_history,
        'oova_history': oova_history,
    })


def reorder_dataframes_for_review(df):
    df['has_multiple'] = df['oova_id'].apply(lambda x: isinstance(x, list))
    df = df.sort_values('has_multiple', ascending=False).reset_index(drop=True)
    df = df.drop(columns='has_multiple')
    return df


def make_samples(df, n_samples, sample_size=500, random_state=81):
    # samples from pool of matches for human review 
    multiple_ids = df[df['oova_id'].apply(lambda x: isinstance(x, list))].sample(frac=1, random_state=random_state).reset_index(drop=True)
    single_id = df[~df['oova_id'].apply(lambda x: isinstance(x, list))].sample(frac=1, random_state=random_state).reset_index(drop=True)

    n_multi = len(multiple_ids)
    n_single_needed = sample_size - min(n_multi, sample_size)
    total_needed = n_samples * n_single_needed

    if total_needed > len(single_id):
        print(f"Warning: not enough records for {n_samples} non-overlapping samples. "
              f"Have {len(single_id)}, need {total_needed}.")
    for i in range(n_samples):
        single_slice = single_id.iloc[i * n_single_needed : (i + 1) * n_single_needed]
        sample = pd.concat([multiple_ids, single_slice]).reset_index(drop=True)
        sample.to_csv(f"SAMPLES_MediumHigh_Matches_{i}.csv")



def separate_match_tiers(df):
    # separates match tiers from larger pool of all matches, and makes exports that by tier category
    exact = reorder_dataframes_for_review(df[df['confidence_level'] == 'exact'])
    high = reorder_dataframes_for_review(df[df['confidence_level'] == 'high'])
    medium_high = reorder_dataframes_for_review(df[df['confidence_level'] == 'medium-high'])
    low = reorder_dataframes_for_review(df[df['confidence_level'] == 'low'])
    exact_high_matches = pd.concat([exact, high])
    exact_high_matches = exact_high_matches.drop(columns=['min_score', 'confidence_level'])
    medium_high = medium_high.drop(columns=['min_score', 'confidence_level'])
    exact_high_matches.to_csv('all_Exact_&_HighConfidence_Matches_Review_Sheet.csv', index=False)
    medium_high.to_csv('all_MediumHighConfidence_Matches_Review_Sheet.csv', index=False)
    low.to_csv('all_LowConfidence_Matches_Review_Sheet.csv', index=False)
    return exact, high, medium_high, low

def main(path_to_all_matched_records, n_samples, sample_size):
    path_to_all_matched_records = '/Users/mahajabin/Desktop/Projects/NPI/all_matches_70.csv'
    matches = process_data(path_to_all_matched_records)
    # get medium-high matches
    exact, high, medium_high, low = separate_match_tiers(matches)
    #args can changed based on tier
    make_samples(medium_high, n_samples, sample_size, random_state=81)



main(path_to_all_records, n_samples, sample_size)



