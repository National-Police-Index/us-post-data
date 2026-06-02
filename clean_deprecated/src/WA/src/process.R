library(tidyverse)

wide2long <- function(df, prefix, outname) {
    df %>%
        select(person_nbr, starts_with(prefix)) %>%
        pivot_longer(cols = -person_nbr, names_to = "stint", values_to = outname) %>%
        mutate(stint = str_remove(stint, fixed(prefix)),
               stint = if_else(stint == "", "_0", stint),
               stint = as.integer(str_remove(stint, "_"))) %>%
        filter(!is.na( !!sym(outname) ))
}

reshape_employment_data <- function(df) {
    p_info <- df %>%
        select(person_nbr,
               first_name = person_first_name,
               middle_name = person_middle_name,
               last_name = person_last_name,
               suffix = person_suffix,
               sex = person_gender,
               birth_year)
    agcy_names <- wide2long(df, "employing_organization_name", "agcy_name")
    start_dates <- wide2long(df, "employment_start_date", "start_date") %>%
        mutate(start_date = as.Date(start_date, format = "%m/%d/%Y"))
    end_dates <- wide2long(df, "employment_end_date", "end_date") %>%
        mutate(end_date = as.Date(end_date, format = "%m/%d/%Y"))
    ranks <- wide2long(df, "employment_title_rank_current", "rank")
    change_reason <- wide2long(df, "employment_change_reason", "change_reason")
    status <- wide2long(df, "status", "status")
    types <- wide2long(df, "employment_appointment_type", "type")
    stopifnot(nrow(agcy_names) == nrow(start_dates),
              nrow(agcy_names) == nrow(ranks) ,
              nrow(agcy_names) == nrow(change_reason))
    stint_info <- agcy_names %>%
        left_join(start_dates, by = c("person_nbr", "stint")) %>%
        left_join(end_dates, by = c("person_nbr", "stint")) %>%
        left_join(ranks, by = c("person_nbr", "stint")) %>%
        left_join(change_reason, by = c("person_nbr", "stint")) %>%
        left_join(status, by = c("person_nbr", "stint")) %>%
        left_join(types, by = c("person_nbr", "stint"))
    out <- p_info %>% inner_join(stint_info, by = "person_nbr")
    out
}

leo <- read_csv("input/wa-2024-original-leo.csv", guess_max = 50000) %>%
    rename(person_nbr = person_student_id)
corrections <- read_csv("input/wa-2024-original-corrections.csv", guess_max = 50000) %>%
    rename(person_nbr = person_student_id)

stopifnot(
    length(unique(leo$person_nbr)) == nrow(leo),
    length(unique(corrections$person_nbr)) == nrow(corrections)
)

cleaned_leo <- reshape_employment_data(leo)
cleaned_corrections <- reshape_employment_data(corrections)

out <- bind_rows(cleaned_leo, cleaned_corrections) %>%
    mutate(separation_reason =
           if_else(!is.na(end_date), replace_na(change_reason, ""), ""),
           status = if_else(is.na(status), "", str_glue("(LICENSE {status})")),
           status = if_else(is.na(end_date), "", status)) %>%
    mutate(separation_reason = str_squish(str_glue("{separation_reason} {status}"))) %>%
    select(-stint, -change_reason, -status)

write_csv(out, "output/wa-2024-npi-index.csv")
