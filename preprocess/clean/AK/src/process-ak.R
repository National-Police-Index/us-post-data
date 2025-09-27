library(argparse)
library(tidyverse)
library(readxl)
library(janitor)

parser <- ArgumentParser()
parser$add_argument("--input", default = "input/II/2017 & 2019 certified/Alaska Police Officers 20170125.xlsx",
                    help = "Input Excel file")
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


ak2017 <- read_excel("input/II/2017 & 2019 certified/Alaska Police Officers 20170125.xlsx",
                     .name_repair = uniqueify_names) %>%
    clean_names()

wide <- ak2017 %>%
    filter(!is.na(person_apsc_id)) %>%
    select(person_nbr = person_apsc_id,
           first_name = person_first_name,
           middle_initial = person_middle_initial,
           last_name = person_last_name,
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

out <- long %>%
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

n_start_dates_new <- sum(!is.na(out$start_date))

stopifnot(length(unique(out$person_nbr)) == nrow(wide))
stopifnot(n_start_dates_orig == n_start_dates_new)

write_csv(out, "output/ak-processed.csv", na = "")
