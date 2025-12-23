# Packages ---------------------------------------------------------

library(lubridate)
library(dplyr)
library(tidyr)
library(ggplot2)
library(viridis)
library(patchwork)

# Constants --------------------------------------------------------

# vegetation levels
veg_levels <- c("forest", "shrubland", "grassland")

# Functions --------------------------------------------------------

theme_set(theme_classic())
nice_theme <- function() {
  theme(
    panel.border = element_blank(),
    panel.grid.minor.y = element_blank(),
    panel.grid.minor.x = element_line(linewidth = 0.1, color = "gray"),
    panel.grid.major =  element_line(linewidth = 0.2, color = "gray"),

    axis.line = element_line(linewidth = 0.35),

    axis.text = element_text(size = 9),
    axis.title = element_text(size = 11),

    strip.text = element_text(size = 11),
    strip.background = element_rect(fill = "white", color = "white")
  )
}

# Compute high and low values of a vector, robust to outliers
get_extremes <- function(x) {
  # Remove NA values
  x <- x[!is.na(x)]
  N <- length(x)
  
  # Return all NA if fewer than 2 observations
  if (N < 2) {
    return(setNames(rep(NA_real_, 2), c("low", "high")))
  }
  
  # Sort ascending and descending
  sortedAsc  <- sort(x)
  sortedDesc <- rev(sortedAsc)
  
  # --- Low values ---
  low1 <- min(x)
  low2 <- mean(sortedAsc[1:min(2, N)])
  low3 <- mean(sortedAsc[pmin(2:3, N)])  # second–third
  
  low <- if (N > 20) {
    low3
  } else if (N >= 9) {
    low2
  } else {
    low1
  }
  
  # --- High values ---
  high1 <- max(x)
  high2 <- mean(sortedDesc[1:min(2, N)])
  high3 <- mean(sortedDesc[pmin(2:3, N)])
  
  high <- if (N > 20) {
    high3
  } else if (N >= 9) {
    high2
  } else {
    high1
  }
  
  # Combine into a named vector
  summ <- c(low = low, high = high)
  
  return(summ)
}

# Function to flag outliers for one band (fire index which decreases with fire)
flag_outliers_band <- function(df_point, band) {
  uu <- df_point[[band]][df_point$burned == 0]
  bb <- df_point[[band]][df_point$burned == 1]

  if (length(uu) == 0 || length(bb) == 0)
    return(rep(FALSE, nrow(df_point)))

  high_unburned <- max(uu, na.rm = TRUE)
  low_burned    <- min(bb, na.rm = TRUE)

  out_band <- 
    (df_point$burned == 1 & df_point[[band]] >= high_unburned) |
    (df_point$burned == 0 & df_point[[band]] <= low_burned)
  
  return(out_band)
}

# Function to import and prepare data for a single fire:
# get nbr summaries, veg, pair previous year, and remove outliers.
prep_data <- function(id) {
  # load data
  ld <- read.csv(file.path("data", "raw", land_names[grep(id, land_names)]))
  fd <- read.csv(file.path("data", "raw", fi_names[grep(id, fi_names)]))

  # summarize fire indices
  summs <- aggregate(
    cbind(nbr, nbr2, mirbi, ndvi) ~ point_id + year, 
    fd, get_extremes
  )
  summs <- do.call(data.frame, summs)
  names(summs) <- c(
    "point_id", "year", 
    "nbr_low", "nbr_high", 
    "nbr2_low", "nbr2_high", 
    "mirbi_low", "mirbi_high",
    "ndvi_low", "ndvi_high"
  )

  # relabel MapBiomas land cover
  from <- c(3, 66, 6, 12, 11, 75, 63, 21, 9, 29, 25, 24, 33, 34, 27)
  to   <- c(1,  2, 1,  3,  3,  3,  3,  3, 1,  0,  0,  0,  0,  0,  0)
  # new values:
  # 0: no quemable
  # 1: bosque
  # 2: arbustal
  # 3: pastizal

  # copy original just in case
  ld$veg_raw <- ld$veg
  ld$veg <- to[match(ld$veg_raw, from, nomatch = NA)]

  # in the burned class, some points become non-burnable after fire, 
  # So we cannot predict burn probability (we need a valid veg type).
  # Correct that, turn into grassland.
  rows_nb <- ld$veg == 0 & ld$class == "burned"
  ld$veg[rows_nb] <- 3

  # merge nbr summaries with land cover data
  annual <- left_join(
    summs, ld, by = c("point_id", "year")
  )

  # rename year to match with fire indices ts data
  annual$year_prev <- annual$year
  fd$year_prev <- fd$year - 1

  # merge with annual table
  use <- c(
    "point_id", "year_prev", 
    "nbr_low", "nbr_high", 
    "nbr2_low", "nbr2_high", 
    "mirbi_low", "mirbi_high",
    "ndvi_low", "ndvi_high",
    "veg"
  )

  d <- left_join(
    fd, annual[, use], by = c("point_id", "year_prev")
  )

  # burned label at observation-level, based on fire dates. 
  # 2 means not used (not labelled)
  metadata <- tf[tf$fire_id == paste("fire_", id, sep = ""), ]

  d$date <- as.Date(d$date, format = "%Y-%m-%d")
  d$burned <- 2 # not-used value

  # define pre- and post-fire periods
  prefire <- 
    d$date >= (metadata$pre_upr - years(1)) &
    d$date <= metadata$pre_upr 

  postfire <- 
    d$date >= (metadata$post_lwr) &
    (
      (d$veg == 3 & d$date <= metadata$post_upr_short) | # grassland
      (d$veg <  3 & d$date <= metadata$post_upr_long)    # shrubland and grassland
    )
  
  # Burned based on class and period
  rows_burned <- d$class == "burned" & postfire
  rows_unburned <- prefire | (d$class == "unburned" & postfire)

  d$burned[rows_burned] <- 1
  d$burned[rows_unburned] <- 0

  d$out <- FALSE  # initialize

  out_list <- lapply(split(d, d$point_id), function(df_point) {
    # Skip if too few observations
    if (nrow(df_point) < 3) {
      df_point$out <- FALSE
      return(df_point)
    }

    outs <- do.call(cbind, lapply(c("nbr", "nbr2", "mirbi", "ndvi"), function (b) {
      flag_outliers_band(df_point, b)
    }))
    
    df_point$out <- apply(outs, 1, any)

    return(df_point)
  })

  d <- do.call(rbind, out_list)
  d <- d[!d$out, ]
  
  # remove NAs
  names(d)
  cols <- c(
    "class", "date", "point_id", "year", "veg", "burned",
    "nbr", "nbr_low", "nbr_high", 
    "nbr2", "nbr2_low", "nbr2_high", 
    "mirbi", "mirbi_low", "mirbi_high", 
    "ndvi", "ndvi_low", "ndvi_high"
  )
  d <- d[complete.cases(d[, cols]), ]
  d$fire_id <- paste("fire_", id, sep = "")

  keep <- c(
    "fire_id", "class", "date", "point_id", "year", 
    "burned",
    "veg",
    "nbr", "nbr_low", "nbr_high", 
    "nbr2", "nbr2_low", "nbr2_high", 
    "mirbi", "mirbi_low", "mirbi_high", 
    "ndvi", "ndvi_low", "ndvi_high"
  )
  return(d[, keep])
}

# Error metrics for cross-validation (leave fire out).
error_metrics <- function(obs, pred) {
  # Check inputs
  stopifnot(length(obs) == length(pred))
  stopifnot(all(obs %in% c(0, 1)))
  stopifnot(all(pred %in% c(0, 1)))
  
  # Confusion matrix components
  TP <- sum(obs == 1 & pred == 1)
  TN <- sum(obs == 0 & pred == 0)
  FP <- sum(obs == 0 & pred == 1)
  FN <- sum(obs == 1 & pred == 0)
  
  # Errors
  omission_error   <- FN / (TP + FN)  # false negatives / actual positives
  commission_error <- FP / (TP + FP)  # false positives / predicted positives
  
  # Cohen's kappa
  n <- length(obs)
  po <- (TP + TN) / n
  pe <- ((TP + FP) * (TP + FN) + (FN + TN) * (FP + TN)) / n^2
  kappa <- (po - pe) / (1 - pe)
  
  out <- c(
    omission   = omission_error,
    commission = commission_error,
    kappa_error  = 1 - kappa
  )
  return(out)
}

# Compute the log probability from the logit-burn-probability
# (it's -softplus(-logit)))
logit2logprob <- function(x) -log1p(exp(-x))

# Aggregate a vector with itself, using a window of length K. 
# Any summary function can be provided in fun. 
# Used to smooth the burn probability time series.
# It returns a vector of length L = length(x) - (K - 1).
self_aggregate <- function(x, K = 5, fun = median) {
  N <- length(x)
  L <- N - (K - 1)
  M <- matrix(NA, L, K)
  for (k in 1:K) M[, k] <- x[k:(N-K+k)]
  return(apply(M, 1, fun))
}

# softplus stable
softplus <- function(x) {
  # numerically stable softplus
  ifelse(x >= 0, x + log1p(exp(-x)), log1p(exp(x)))
}

# Cumulative probability (P) of observing at least a fire up to time T.
# Takes the logit burn prob at observation level (eta).
# It smoothes the logit through a K-window fun, and computes 
# the cumulative probability from the smoothed obs-level probabilities.
# agg indicates whether to aggregate (smooth) or not.
Pcalc <- function(eta, K = 5, fun = median, agg = T) {
  # med5 on logits -> centers at indices 3:(T-2)
  if (agg) {
    med5_eta <- self_aggregate(eta, K = K, fun = fun)  
  } else {
    med5_eta <- eta
  }

  # softplus per centered obs
  s <- softplus(med5_eta) # gets log(1 - burn prob)

  # cumulative S_t
  S <- cumsum(s)

  # P_t
  P <- 1 - exp(-S)

  return(P)
}

# Add cumulative burn probability (P) to a data.frame containing the 
# logit-burn-prob in the column named 'colname'. It uses Pcalc. 
# Use K = 3 or K = 5.
addP <- function(df, colname = "eta", K = 5, fun = median, agg = F) {
  eta <- df[, colname]
  P <- Pcalc(eta, K = K, fun = fun, agg)
  
  if (agg) {
    # append NA to the P vector
    extra <- floor(K / 2)
    Pfull <- c(
      rep(NA, extra),
      P,
      rep(NA, extra)
    )
  } else {
    Pfull <- P
  }
  
  df$P <- Pfull

  # return data.frame including P
  return(df)
}

# Visualize burn probability time series (bpts) in observed points, 
# along with a smoothed version and the cumulative probability (optional).

# fire_id a, point_id: numeric integers to choose fire and point to visualize. 
#   If not provided, they are sampled. 
# class: display either "burned" or "unburned" points.
# model_obs: The observation-level model for burn probability. Default is 
#   "mbp", so it should be loaded to use the function.
# K, fun: define how to smooth the burn probability, based on self_aggregate().
# Mbelow, Mabove: how many raw obs to take from the previous and
#   following year to compute cumulative probability. Note these are raw
#   observations, not smoothed ones. To have 2 smoothed observations, with K = 5,
#   these M must be 4.
# cumulative: logical, display cumulative burn probability?
# fire_index: fire index to display: nbr, nbr2, mirbi, ndvi
plot_bpts <- function(
  fire_id = NULL,
  point_id = NULL,
  class = "burned",
  model_obs = mbp,  
  K = 5,
  fun = median,
  Mbelow = 4, 
  Mabove = 4,
  cumulative = TRUE,
  fire_index = "nbr"
) {
  fnum <- ifelse(
    is.null(fire_id),
    sample(1:30, 1),
    fire_id
  )

  fid <- paste("fire", sprintf("%02d", fnum), sep = "_")
  filter1 <- 
    data_full$fire_id == fid & 
    data_full$class == class
    
  d0 <- data_full[filter1, ]

  point <- ifelse(
    is.null(point_id), 
    sample(unique(d0$point_id), 1),
    point_id
  )
  
  d <- d0[d0$point_id == point, ]
  d <- d[order(d$date), ]
  
  # predict
  d$logit_p <- predict(model_obs, d, type = "link")
  d$p <- plogis(d$logit_p)

  # choose variable to display
  d$fire_index <- d[, fire_index]

  # make title
  vegt <- table(d$veg_fac)
  vv <- names(which.max(vegt))
  tit <- paste(fid, point, class, vv, sep = " | ")

  p1 <-
  ggplot(d, aes(date, fire_index)) + 
    geom_line() + 
    geom_point(data = d[d$burned == 0, ], color = "blue") +
    geom_point(data = d[d$burned == 1, ], color = "red") +
    ylab(fire_index) + 
    xlab(NULL) + 
    # geom_hline(yintercept = 0, linetype = "dashed", color = "gray") +
    ggtitle(tit) + 
    nice_theme()
  
  # Burn probability, smoothed and not
  
  # Smoothed probability
  yy <- paste("Smoothed burn probability (K = ", K, ")", sep = "")

  # Assign 5-obs-median to middle date.
  dagg <- d[3:(nrow(d) - (K - 1) + 2), ]
  dagg$p <- self_aggregate(d$p, K = K, fun = median)
  
  dagg$type <- "median5"
  d$type <- "raw"

  dboth <- rbind(d, dagg)
  dboth$type <- factor(dboth$type, levels = c("raw", "median5"))

  p2 <-
  ggplot() + 
    geom_line(
      data = dboth, mapping = aes(date, p, color = type),
      linewidth = 0.9
    ) + 
    scale_color_manual(values = c("black", viridis(1, begin = 0.5))) +
    geom_point(
      data = d[d$burned == 0, ], mapping = aes(date, p), color = "blue"
    ) +
    geom_point(
      data = d[d$burned == 1, ], mapping = aes(date, p), color = "red"
    ) +
    ylab("Burn probability") + 
    xlab("Date") + 
    ylim(0, 1) +
    nice_theme() +
    theme(
      legend.position = "none",
      legend.title = element_blank()
    )
  
  if (!cumulative) {
    out <- p1 / p2
  print(out)
  } else {
    # Probability of at least one (smoothed) burned observation up to time t.
    # Compute this by year.
    years <- unique(d$year)
    dP <- do.call("rbind", lapply(years, function (y) {
      # Get focal observations +-M observations in neighbouring years
      # y = 2016
      rows_focal <- which(d$year == y)
      first_row <- rows_focal[1]
      last_row <- rows_focal[length(rows_focal)]
      begin <- max(c(first_row - Mbelow, 1))
      end <- min(c(last_row + Mabove, max(nrow(d))))
      dlocal <- d[begin:end, ]
      
      # Assign focal year to extended dates
      dlocal$year <- y

      # Cumulative prob
      dlocal <- addP(dlocal, "logit_p", K = K, fun = fun)
    }))
    dP$year_fac <- factor(as.character(dP$year), as.character(years))
    
    # Plot cumulative evidence
    ltys <- rep(c("solid", "dashed"), 10)
    p3 <-
    ggplot(
      dP, 
      aes(date, P, color = year_fac, linetype = year_fac, group = year_fac)
    ) + 
      geom_line(linewidth = 0.9) + 
      scale_color_manual(values = viridis(length(years), end = 0.9, option = "A")) +
      scale_linetype_manual(values = ltys[1:length(years)]) +
      ylab("Cumulative burn probability") + 
      xlab("Date") + 
      ylim(0, 1) +
      nice_theme() +
      theme(
        legend.position = "none",
        legend.title = element_blank()
      )
    
    out <- p1 / p2 / p3
    print(out)
  }
}

# Annual summaries of (smoothed) burn probability time series. 
# Takes a data.frame with
#   logit_p: smoothed logit-burn probability and
#   date: date.

# Returns a single-row data.frame with columns
# pmax: largest bp
# pdiff_max: largest increase in bp
# date_pre: date before the largest increase in bp
# date_post: date after the largest increase in bp
# date_mid: middate between pre and post
# Pmax: maximum cumulative probability in the year
# Pdiff_max: maximum difference in cumulative probability
# Pdiff_mean: mean(diff(P)). It may help identify delayed mortality in 
#   forests
# obs_after: number of observations after the Pdff_max is observed.
#   Used because the cumulative probability tends to be lower if few burn
#   observations are available after the max diff occurs.
annual_summaries <- function(df) {
  # Cumulative probability
  df <- addP(df, "logit_p")
  
  # Burn probability
  df$p <- plogis(df$logit_p)

  # Differences
  pdiff <- diff(df$p)
  Pdiff <- diff(df$P)

  # Actual summaries
  pmax <- max(df$p, na.rm = T)
  pdiff_max <- max(pdiff, na.rm = T)
  Pmax <- max(df$P, na.rm = T)
  Pdiff_max <- max(Pdiff, na.rm = T)
  Pdiff_mean <- mean(Pdiff, na.rm = T)

  # Dates
  idx_max <- which.max(pdiff)
  n_after_max <- length(pdiff) - idx_max
  date_pre <- df$date[idx_max]
  date_post <- df$date[idx_max + 1]
  date_delta <- date_post - date_pre
  date_mid <- as.Date(ifelse(
    date_delta < 2,
    date_post,
    date_pre + ceiling(as.numeric(date_delta) / 2)
  ), origin = "1970-01-01")
  
  # Put in data.frame
  out <- data.frame(
    year = year(mean(df$date)),
    pmax = pmax,
    pdiff_max = pdiff_max,
    Pmax = Pmax,
    Pdiff_max = Pdiff_max,
    Pdiff_mean = Pdiff_mean,
    date_pre = date_pre,
    date_post = date_post,
    date_mid = date_mid,
    n_after_max = n_after_max
  )

  return(out)
}

# Summarize data at the point level. 
# It implies recording the response variable and predictors for each year.
# Label burn years of a given point, based on the max(diff(bp)).
# bp, for burn probability is its K-obs fun() smoothed version.
# M is the number of (smoothed) observations before and after focal year
# included in the annual time series.

# returns a data.frame with columns
# fire_id
# point_id
# burned {0, 1}
# and the output from annual_summaries()
prep_annual_point <- function(
  fire_id, 
  point_id, 
  K = 5, 
  fun = median,
  M = 2
) {
  ## Test/trial
  # fire_id = "fire_10"
  # point_id = 76
  # K = 5
  # fun = median
  # M = 2
  
  filter <- data_full$fire_id == fire_id & data_full$point_id == point_id
  d <- data_full[filter, ]
  d <- d[order(d$date), ]
  
  # determine years to use: year(pre_upr) +- 2
  year_centre <- year(tf$pre_upr[tf$fire_id == fire_id])
  years_full <- c(year_centre - 1, year_centre, year_centre + 1)
  years <- years_full[years_full %in% unique(d$year)]
  
  if (length(years) == 0) return(NULL)

  # Compute logit-burn probability at the observation level
  d$eta <- predict(mbp, newdata = d, type = "link")
  
  # Smooth with K-obs fun, assigning value to the middle date. 
  extra <- floor(K / 2)
  logit_p <- self_aggregate(d$eta, K = K, fun = fun)
  d$logit_p <- c(
    rep(NA, extra),
    logit_p,
    rep(NA, extra)
  )

  # Compute annual summaries (not burn label)
  dannual <- do.call("rbind", lapply(years, function (y) {
    # Get focal observations +-(M-extra) smoothed observations in neighbouring 
    # years. 
    # y = 2014
    rows_focal <- which(d$year == y)
    first_row <- rows_focal[1]
    last_row <- rows_focal[length(rows_focal)]
    begin <- max(c(first_row - M, 1))
    end <- min(c(last_row + M, max(nrow(d))))
    dlocal <- d[begin:end, ]

    # Remove NA, which may appear in logit_p
    dlocal <- dlocal[!is.na(dlocal$logit_p), ]
    
    # Assign focal year to extended dates
    dlocal$year <- y

    # Cumulative prob (tell the function not to smooth the burn prob, 
    # with agg = F)
    dlocal <- addP(dlocal, "logit_p", agg = F)

    # Annual summaries
    dann <- annual_summaries(dlocal)

    # Recover previous predictors at annual level 
    # (veg, veg_fac, nbr_cold, nbr_hot)
    d1r <- dlocal[year(dlocal$date) == y, ]
    d1r <- d1r[1, , drop = F]

    vars_keep <- c(
      "veg", "veg_fac", 
      "nbr_low", "nbr_high",
      "nbr2_low", "nbr2_high",
      "mirbi_low", "mirbi_high",
      "ndvi_low", "ndvi_high"
    )

    dann <- cbind(
      dann,
      d1r[, vars_keep]
    ) 

    return(dann)
  }))  

  # To detect burn year
  d$p <- plogis(d$logit_p)
  d$pdiff <- c(NA, diff(d$p))
  
  # Assign burned at annual level
  dannual$burned <- NA
  if (d$class[1] == "unburned") {
    dannual$burned <- 0
  } else {
    # Find burn year using pre-post dates at fire level
    pre_upr <- tf$pre_upr[tf$fire_id == fire_id]
    post_lwr <- tf$post_lwr[tf$fire_id == fire_id]

    pre <- pre_upr - 30 * 5
    post <- post_lwr + 30 * 6

    # Easy if pre and post are in the same year
    if (year(pre) == year(post)) {
      yy <- year(post)
      dannual$burned <- as.numeric(dannual$year == yy)
    } else {
      # get the year in which p increases as much as the max increase between
      # pre and post
      rr <- d$date >= pre & d$date <= post
      
      if (sum(rr) == 0) stop("Dates missmatch")
      
      target <- max(d$pdiff[rr], na.rm = T)
      dannual$burned <- as.numeric(dannual$pdiff_max == target)
    }
  }

  # Keep fire_id and point_id
  dannual$fire_id <- fire_id
  dannual$point_id <- point_id

  return(dannual)
}


# Visualize burn probability time series (bpts) in observed points, 
# its smoothed version, the cumulative probability (optional), and the 
# annual-level burn probability. This is an extended version of plot_bpts().

# fire_id a, point_id: numeric integers to choose fire and point to visualize. 
#   If not provided, they are sampled. 
# class: display either "burned" or "unburned" points.
# model_obs: The observation-level model for burn probability. Default is 
#   "mbp", so it should be loaded to use the function.
# model_annual: The annual-level model for burn probability. Default is 
#   "mbp_annual", so it should be loaded to use the function.
# K, fun: define how to smooth the burn probability, based on self_aggregate().
# Mbelow, Mabove: how many raw obs to take from the previous and
#   following year to compute cumulative probability. Note these are raw
#   observations, not smoothed ones. To have 2 smoothed observations, with K = 5,
#   these M must be 4.
# fire_index: fire index to display: nbr, nbr2, mirbi, ndvi
plot_bpts_fit <- function(
  fire_id = NULL,
  point_id = NULL,
  class = "burned",
  model_obs = mbp,
  model_annual = mbp_annual,
  K = 5,
  fun = median,
  Mbelow = 4, 
  Mabove = 4,
  fire_index = "nbr"
) {

  # # Test
  # fire_id = 18
  # point_id = 31
  # class = "burned"
  # model = mbp
  # K = 5
  # fun = median
  # Mbelow = 4 
  # Mabove = 4
  # fire_index = "nbr"

  fnum <- ifelse(
    is.null(fire_id),
    sample(1:30, 1),
    fire_id
  )

  fid <- paste("fire", sprintf("%02d", fnum), sep = "_")
  filter1 <- 
    data_full$fire_id == fid & 
    data_full$class == class
    
  d0 <- data_full[filter1, ]

  point <- ifelse(
    is.null(point_id), 
    sample(unique(d0$point_id), 1),
    point_id
  )
  
  d <- d0[d0$point_id == point, ]
  d <- d[order(d$date), ]
  
  # predict
  d$logit_p <- predict(model_obs, d, type = "link")
  d$p <- plogis(d$logit_p)

  # choose variable to display
  d$fire_index <- d[, fire_index]

  # make title
  vegt <- table(d$veg_fac)
  vv <- names(which.max(vegt))
  tit <- paste(fid, point, class, vv, sep = " | ")

  p1 <-
  ggplot(d, aes(date, fire_index)) + 
    geom_line() + 
    geom_point(data = d[d$burned == 0, ], color = "blue") +
    geom_point(data = d[d$burned == 1, ], color = "red") +
    ylab(fire_index) + 
    xlab(NULL) + 
    geom_hline(yintercept = 0, linetype = "dashed", color = "gray") +
    ggtitle(tit) + 
    nice_theme()
  
  # Burn probability, smoothed and not
  
  # Smoothed probability
  yy <- paste("Smoothed burn probability (K = ", K, ")", sep = "")

  # Assign 5-obs-median to middle date.
  dagg <- d[3:(nrow(d) - (K - 1) + 2), ]
  dagg$logit_p <- self_aggregate(d$logit_p, K = K, fun = median)
  dagg$p <- plogis(dagg$logit_p)
  
  dagg$type <- "median5"
  d$type <- "raw"

  dboth <- rbind(d, dagg)
  dboth$type <- factor(dboth$type, levels = c("raw", "median5"))

  p2 <-
  ggplot() + 
    geom_line(
      data = dboth, mapping = aes(date, p, color = type),
      linewidth = 0.9
    ) + 
    scale_color_manual(values = c("black", viridis(1, begin = 0.5))) +
    geom_point(
      data = d[d$burned == 0, ], mapping = aes(date, p), color = "blue"
    ) +
    geom_point(
      data = d[d$burned == 1, ], mapping = aes(date, p), color = "red"
    ) +
    ylab("Burn probability") + 
    xlab(NULL) + 
    ylim(0, 1) +
    nice_theme() +
    theme(
      legend.position = "none",
      legend.title = element_blank()
    )
  
  # Probability of at least one (smoothed) burned observation up to time t.
  # Compute this by year.
  years <- unique(d$year)
  dP <- do.call("rbind", lapply(years, function (y) {
    # Get focal observations +-M observations in neighbouring years
    # y = 2016
    rows_focal <- which(d$year == y)
    first_row <- rows_focal[1]
    last_row <- rows_focal[length(rows_focal)]
    begin <- max(c(first_row - Mbelow, 1))
    end <- min(c(last_row + Mabove, max(nrow(d))))
    dlocal <- d[begin:end, ]
    
    # Assign focal year to extended dates
    dlocal$year <- y

    # Cumulative prob
    dlocal <- addP(dlocal, "logit_p", K = K, fun = fun)
  }))
  dP$year_fac <- factor(as.character(dP$year), as.character(years))
  
  # Plot cumulative evidence
  ltys <- rep(c("solid", "dashed"), 10)
  p3 <-
  ggplot(
    dP, 
    aes(date, P, color = year_fac, linetype = year_fac, group = year_fac)
  ) + 
    geom_line(linewidth = 0.9) + 
    scale_color_manual(values = viridis(length(years), end = 0.9, option = "A")) +
    scale_linetype_manual(values = ltys[1:length(years)]) +
    ylab("Cumulative burn probability") + 
    xlab(NULL) + 
    ylim(0, 1) +
    nice_theme() +
    theme(
      legend.position = "none",
      legend.title = element_blank()
    )
  
  # Annual plot: fitted prob and labeled data.
  filter2 <- 
    data_annual$fire_id == fid & 
    data_annual$point_id == point
    
  da <- data_annual[filter2, ]
  da <- da[order(da$year), ]

  # Assign center date to the year
  da$date <- as.Date(
    paste(da$year, "07", "01", sep = "-"), format = "%Y-%m-%d"
  )

  # Get annual-level prob
  da$p <- predict(model_annual, da, type = "response")

  # Factor burned
  da$burned_fac <- factor(
    da$burned, 
    levels = as.character(0:1),
    labels = c("unburned", "burned")
  )

  p4 <- ggplot(da, aes(date, p, fill = burned_fac)) +
    geom_bar(stat = "identity", width = 60) + 
    scale_fill_viridis(discrete = T, option = "C", end = 0.7) +
    nice_theme() + 
    # ghost data to extend date range
    geom_point(
      data = dP, 
      mapping = aes(date, P),
      alpha = 0,
      inherit.aes = F
    ) +
    theme(
      legend.title = element_blank(),
      legend.position = c(0.8, 0.5)
    ) +
    ylim(0, 1) +
    ylab("Annual burn probability") + 
    xlab("Date")

  out <- p1 / p2 / p3 / p4
  print(out)
}

# Visualize temporal segmentation at the fire level, mostly through spaghetti
# plots of fire indices and burn probability.

# fire_id: integer to choose fire to visualize [1:30].
# n_points: number of points to display. If not provided, 
#   100 by burn class are sampled.
# model_obs: The observation-level model for burn probability. Default is 
#   "mbp", so it should be loaded to use the function.
# model_annual: The annual-level model for burn probability. Default is 
#   "mbp_annual", so it should be loaded to use the function.
# K, fun: define how to smooth the burn probability, based on self_aggregate().
# Mbelow, Mabove: how many raw obs to take from the previous and
#   following year to compute cumulative probability. Note these are raw
#   observations, not smoothed ones. To have 2 smoothed observations, with K = 5,
#   these M must be 4.
# fire_index: fire index to display: nbr, nbr2, mirbi, ndvi
plot_tempseg <- function(
  fire_id = NULL,
  n_points = 100,
  model_obs = mbp,
  model_annual = mbp_annual,
  K = 5,
  fun = median,
  Mbelow = 4, 
  Mabove = 4,
  fire_index = "nbr"
) {
  # return a plot with 3 panels:
  # [1] Time series of a fire index.
  # [2] Time series of smoothed burn probability (from obs-level model).
  # [3] Annual violin plot showing the distribution of burn probability
  #     at the annual level by annual-level burn class.

  # [1] and [2] show a line by point, with color varying by class 
  # (burned/unburned)
}