library(argparse)
library(assertr)
library(tidyverse)
library(readxl)
library(janitor)

parser <- ArgumentParser()
parser$add_argument("--ak-employment-2017")
parser$add_argument("--ak-active-2023")
parser$add_argument("--ak-changes-2023")
parser$add_argument("--output")
args <- parser$parse_args()


uniqueify_names <- function(nms) {
    # make names unique by appending _1, _2, etc to duplicates
    dups <- nms[duplicated(nms)]
    for (d in unique(dups)) {
        inds <- which(nms == d)
        nms[inds] <- paste0(d, "_", seq_along(inds))
    }
    nms
}

ak2017 <- read_excel(args$ak_employment_2017,
                     .name_repair = uniqueify_names) %>%
    clean_names() %>%
    rename(person_nbr = person_apsc_id,
           first_name = person_first_name,
           middle_initial = person_middle_initial,
           last_name = person_last_name) %>%
    mutate(first_name = str_to_upper(first_name) %>% str_squish,
           last_name = str_to_upper(last_name) %>% str_squish,
           middle_initial = str_to_upper(middle_initial) %>% str_squish)

ak2023 <- read_csv(args$ak_active_2023) %>%
    clean_names() %>%
    rename(person_nbr = apsc_id,
           agency_name = primary_organization,
           start_date = last_hired_date) %>%
    mutate(start_date = as.Date(start_date, format="%m/%d/%Y"),
           start_date = format(start_date, "%Y-%m-%d"),
           first_name = str_to_upper(first_name) %>% str_squish,
           last_name = str_to_upper(last_name) %>% str_squish)

changes2023 <- read_csv(args$ak_changes_2023) %>%
    clean_names() %>%
    rename(person_nbr = apsc_id,
           agency_name = primary_organization,
           start_date = last_hired_date) %>%
    mutate(start_date = as.Date(start_date, format="%m/%d/%Y"),
           start_date = format(start_date, "%Y-%m-%d"),
           first_name = str_to_upper(first_name) %>% str_squish,
           last_name = str_to_upper(last_name) %>% str_squish) %>%
    verify(employment_status %in% c("Active", "Resigned", "Terminated")) %>%
    filter(employment_status != "Active")

wide <- ak2017 %>%
    filter(!is.na(person_nbr)) %>%
    select(person_nbr, first_name, middle_initial, last_name,
           matches("^employ(ment_|ing)")) %>%
    mutate_if(is.POSIXct, as.character)

# after the first 4 columns, everything else is in repeated groups of 3 fields
# "employment_start_date", "employment_end_date", "employing_organization_name"
# repeated for each employment stint
long <- wide %>%
    pivot_longer(cols = matches("^employ(ment_|ing)"),
                 names_to = "colname", values_to = "value") %>%
    mutate(pieces = str_match(colname, "^(.*)_([0-9]+)$"),
           colname = pieces[,2],
           colgroup = pieces[,3]) %>% select(-pieces) %>%
    filter(!is.na(value))

ak17_out <- long %>%
    pivot_wider(names_from = colname, values_from = value) %>%
    select(person_nbr, first_name, middle_initial, last_name,
           start_date = employment_start_date, end_date = employment_end_date,
           agency_name = employing_organization_name)

# make sure we didn't lose anything
n_start_dates_orig <- wide %>%
    select(contains("start_date")) %>%
    summarise_all(~sum(!is.na(.))) %>%
    as.list %>%
    as.numeric %>%
    sum

n_start_dates_new <- sum(!is.na(ak17_out$start_date))

stopifnot(length(unique(ak17_out$person_nbr)) == nrow(wide))
stopifnot(n_start_dates_orig == n_start_dates_new)

# in a few cases, the display name for the agency changed between 2017 and 2023,
# so we use person_nbr+start_date only to identify new hires
new_hires <- ak2023 %>%
    anti_join(ak17_out, by = c("person_nbr", "start_date")) %>%
    left_join(ak17_out %>% distinct(person_nbr, first_name, middle_initial, last_name),
              by = "person_nbr") %>%
    mutate(first_name = coalesce(first_name.x, first_name.y),
           last_name = coalesce(last_name.x, last_name.y)) %>%
    distinct(person_nbr, first_name, middle_initial, last_name,  start_date, agency_name)

out <- bind_rows(ak17_out, new_hires) %>%
    left_join(changes2023 %>%
                  select(person_nbr, start_date, ch_agency = agency_name, employment_status),
              by = c("person_nbr", "start_date")) %>%
    verify(is.na(employment_status) | employment_status %in% c("Resigned", "Terminated")) %>%
    mutate(end_date = case_when(
        !is.na(end_date) ~ end_date,
        !is.na(employment_status) ~ '2023-01-31', # date of the records disclosure
        TRUE ~ end_date)) %>%
    select(person_nbr, first_name, middle_initial, last_name,
           agency_name, start_date, end_date)

write_csv(out, "output/ak-processed.csv", na = "")

# done.
