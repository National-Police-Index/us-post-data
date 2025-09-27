# vim: set ts=4 sts=0 sw=4 si fenc=utf-8 et:
# vim: set fdm=marker fmr={{{,}}} fdl=0 foldcolumn=4:
library(argparse)
library(readxl)
library(tidyverse)
library(janitor)
library(tidygraph)
library(writexl)

# args {{{
parser <- ArgumentParser()
parser$add_argument("--input", default = "input/Hawaii Police Personnel Records Completed Files .xlsx",
                    help = "Path to the input Excel file")
args <- parser$parse_args()
# }}}

# importers {{{
# dates got imported inconsistently
# sometimes it is just the string "MISSING" which should be an NA date
# sometimes it is a date or date-like
# it's coming from excel and sometimes we import the underlying numeric
# from excel's date representation, which is counted in days since 1900-01-01(?)
fix_date <- function(dates) {
    if (is.numeric(dates)) {
        # Excel date representation
        dates <- as.Date(dates, origin = "1899-12-30")
    } else if (is.character(dates)) {
        dates <- case_when(
            str_detect(dates, "^[0-9.]+$") ~ as.Date(as.numeric(dates), origin = "1899-12-30"),
            dates == "MISSING" ~ NA_Date_,
            str_detect(dates, "^[0-9]{4}[\\-/][0-9]{1,2}[\\-/][0-9]{1,2}$") ~ 
                lubridate::parse_date_time(dates, orders = "ymd"),
            str_detect(dates, "^[0-9]{1,2}[\\-/][0-9]{1,2}[\\-/][0-9]{4}$") ~
                lubridate::parse_date_time(dates, orders = "mdy"),
            TRUE ~ as.Date(NA)
        )
    }
    return(dates)
}

read_sheet <- function(sheet_name) {
    raw <- read_excel(args$input, sheet = sheet_name, guess_max = 100000)
    # from -> to
    renamer <- c(
        hire_date       = "start_date",
        id              = "person_nbr",
        employee_number = "person_nbr",
        position_number = "person_nbr"
    )
    out <- raw %>% clean_names
    for (name in names(renamer)) {
        if (name %in% names(out)) {
            out <- out %>% rename(!!renamer[[name]] := !!name)
        }
    }
    outcols <- c(
        "sheet_name",
        "person_nbr",
        "last_name",
        "first_name",
        "middle_name",
        "agency_name",
        "start_date",
        "end_date"
    )
    out <- out %>% mutate(sheet_name = sheet_name) %>%
        select(any_of(outcols))
    if (!("person_nbr" %in% names(out))) {
        out <- out %>%
            mutate(person_nbr = NA_character_)
    }
    to_return <- out %>%
        mutate(person_nbr = as.character(person_nbr),
               start_date = fix_date(start_date),
               end_date = fix_date(end_date),
               last_name = str_to_upper(last_name),
               first_name = str_to_upper(first_name))
    if (sheet_name == "Kauai County Prosecutor Current") {
        to_return <- group_by(
            to_return, sheet_name, person_nbr,
            last_name, first_name, middle_name, agency_name, start_date
        ) %>% summarise(end_date = max(end_date, na.rm = TRUE), .groups = "drop") %>%
        mutate(end_date = if_else(end_date < 0, NA_Date_, end_date))
    }
    to_return
}
# }}}

add_blank_row <- function(df) {
    # add a blank row to the dataframe
    # this is useful for debugging and visualizing the data
    # it will not affect the analysis
    blank_row <- df[1, ] %>% mutate(across(everything(), ~ NA))
    bind_rows(df, blank_row)
}

sheets <- excel_sheets(args$input)
alldata <- map(set_names(sheets), read_sheet)

#map(alldata, function(x) mean(is.na(x$start_date)))
#map(alldata, function(x) mean(is.na(x$end_date)))

hi <- bind_rows(alldata) %>%
    filter(!is.na(first_name) & !is.na(last_name)) %>%
    mutate(middle_name = str_replace_all(middle_name, "[.]", "") %>% str_squish) %>%
    distinct %>%
    mutate(seqid = row_number()) %>%
    mutate(person_nbr = if_else(person_nbr == "MISSING", NA_character_, person_nbr))

formatted <- hi %>%
    group_by(first_name, last_name) %>%
    mutate(n = n(),
           years = as.numeric(max(replace_na(end_date, Sys.Date())) - min(replace_na(start_date, Sys.Date())), "days") / 365.25) %>%
    ungroup %>%
    nest(data = c(-years, -n, -first_name, -last_name)) %>%
    mutate(sorter = if_else(n > 1, -years, 0)) %>%
    arrange(desc(n), sorter, last_name, first_name) %>%
    mutate(data = map(data, add_blank_row)) %>%
    unnest(data) %>%
    mutate(first_name = if_else(is.na(sheet_name), NA_character_,
                                str_to_upper(first_name)),
           last_name = if_else(is.na(sheet_name), NA_character_,
                               str_to_upper(last_name)))


formatted %>%
    mutate(start_date = strftime(start_date, '%Y-%m-%d'),
           end_date = strftime(end_date, '%Y-%m-%d')) %>%
    transmute(
        first_name,
        last_name,
        middle_name,
        agency_name,
        start_date, end_date) %>%
    write_xlsx("output/HI-police-employment-for-review.xlsx")

#hi %>%
#    inner_join(hi, by = c("last_name", "first_name"),
#               relationship = "many-to-many") %>%
#    filter(sheet_name.x != sheet_name.y | person_nbr.x == person_nbr.y,
#           seqid.x != seqid.y) %>%
#    filter(sheet_name.x != sheet_name.y) %>%
#    distinct(first_name, last_name, sheet_name.x, sheet_name.y, seqid.x, seqid.y)
#
#hi %>% group_by(sheet_name) %>%
#    summarise(across(c(start_date, end_date), ~ mean(is.na(.)))) %>%
#    filter(str_detect(sheet_name, "[Cc]urrent"))
#    filter(start_date > .9 | end_date > .9)

# match names and send list of potential pairs of employment
# logic:
#  - first + last name
#  - time (date overlaps)

