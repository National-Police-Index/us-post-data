# vim: set ts=4 sts=0 sw=4 si fenc=utf-8 et:
# vim: set fdm=marker fmr={{{,}}} fdl=0 foldcolumn=4:

library(assertr)
library(janitor)
library(stringdist)
library(tidyverse)
library(writexl)

# shortens/removes common terms to reduce false positive matches
# (we are matching on string similarity)
simplify_pd_name <- function(name) {
    name %>%
        str_replace_all("police department", "pd") %>%
        str_replace_all("sheriff's office", "sd") %>%
        str_replace_all("sheriff's department", "sd") %>%
        str_squish %>%
        str_replace("office$", "") %>%
        str_squish
}

# setup {{{
load("input/36697-0001-Data.rda")

lear <- as_tibble(da36697.0001) %>% clean_names() %>%
    filter(state == "IL") %>%
    mutate(lear_name = str_squish(name) %>% str_to_lower) %>%
    mutate(lear_name = simplify_pd_name(lear_name))
il_post <- read_csv("input/illinois-processed.csv", guess_max=40000) %>% clean_names %>%
    mutate(post_agency_name = str_to_lower(str_squish(agency_name))) %>%
    mutate(post_agency_name = simplify_pd_name(post_agency_name))

stopifnot(length(unique(lear$lear_id)) == nrow(lear))
# }}}

# match logic {{{
lear_agencies <- distinct(lear, lear_name, lear_name_orig = name,
                          lear_id, ori7, ori9, csllea08_id)

post_agencies <- il_post %>%
    distinct(post_agency_name)

match1 <- stringdist::amatch(post_agencies$post_agency_name,
                             lear_agencies$lear_name,
                             nthread = 7, method = "cosine", maxDist = .2, q=3)
match2 <- stringdist::amatch(post_agencies$post_agency_name,
                             lear_agencies$lear_name,
                             nthread = 7, method = "osa", maxDist = 1)
match3 <- stringdist::amatch(post_agencies$post_agency_name,
                             lear_agencies$lear_name,
                             nthread = 7, method = "lv")
# }}}

match_candidates <- post_agencies %>%
    mutate(cand1 = lear_agencies$lear_name[match1],
           cand2 = lear_agencies$lear_name[match2],
           cand3 = lear_agencies$lear_name[match3]) %>%
    mutate(cos_dist = stringdist(post_agencies$post_agency_name, cand1, method = "cosine", q=3),
           osa_dist = stringdist(post_agencies$post_agency_name, cand2, method = "osa"),
           lv_dist = stringdist(post_agencies$post_agency_name, cand3, method = "lv"))

# get officer counts from each source, to help validate/review matches {{{
# LEAR data is from 2016
il_active_in_2016 <- il_post %>%
    filter(start_date <= "2017-01-01", is.na(end_date) | end_date >= "2016-01-01") %>%
    group_by(post_agency_name) %>%
    summarise(post_n = n_distinct(person_nbr))
# }}}

for_review <- match_candidates %>%
    select(-starts_with("dist")) %>%
    pivot_longer(cols = starts_with("cand"), names_to = "candidate", values_to = "lear_name") %>%
    distinct(post_agency_name, lear_name) %>%
    group_by(post_agency_name) %>% filter(!is.na(lear_name) | all(is.na(lear_name))) %>%
    assert(function(x) {is_uniq(x, allow.na=TRUE)}, lear_name,
           error_fun = function(x) "Multiple matches found for post agency") %>%
    ungroup %>%
    left_join(il_active_in_2016, by = "post_agency_name") %>%
    left_join(lear, by = "lear_name") %>%
    arrange(desc(post_n), post_agency_name) %>%
    transmute(post_agency_name, lear_name, lear_id, post_n,
              lear_n = csllea08_parttime_sworn + csllea08_fulltime_sworn) %>%
    inner_join(distinct(il_post, post_agency_name, agency_name), by = "post_agency_name") %>%
    left_join(lear_agencies %>% select(-lear_name), by = "lear_id") %>%
    transmute(npi = agency_name, lear = str_squish(lear_name_orig),
              lear_id, ori7, ori9, csllea08_id,
              post_count = post_n, lear_count = lear_n)


# correlation 95% conf interval = [.91, .93]
cor.test(for_review$post_count, for_review$lear_count)

# linear regression r^2 = .85
#Coefficients:
#(Intercept)   post_count
#     4.0531       0.8956
lm(lear_count ~ post_count, data = for_review) %>% summary

write_xlsx(for_review, "output/il-lear-matches.xlsx", col_names = TRUE)
