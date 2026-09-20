## ---------------------------------------------------------------------------
## Reproducible, unbiasable author-order draw
## ---------------------------------------------------------------------------
##
## WHAT THIS IS FOR
##
## Two authors contributed equally and the order between them has to be decided
## by chance. The draw must satisfy three things at once:
##
##   (a) reproducible  — anyone can re-run it years later and get the same order;
##   (b) shareable     — the whole procedure is public, no private state;
##   (c) unbiasable    — nobody, the person running it included, could have
##                       steered the result.
##
##
## WHY THE OBVIOUS APPROACH DOES NOT WORK
##
## The tempting version is a chain of seeds:
##
##     set.seed(1); seed2 <- rpois(1, 100); set.seed(seed2); sample(AUTHORS)
##
## This gives (a) and (b) but fails (c), and no amount of extra chaining fixes
## it. The chain has exactly ONE free parameter — the first seed — and whoever
## picks it picks the outcome: you can try seeds in a loop until the order comes
## out the way you want, in well under a second. Hashing the seed, stretching it
## through more steps, or drawing the second seed from a fancier distribution
## changes nothing, because the search is over the input, not the function.
##
## Reproducibility and unbiasability cannot both come from a number you choose.
## The randomness has to come from OUTSIDE, and its value must not exist yet at
## the moment the rule is fixed.
##
##
## THE SOURCE: drand
##
## drand (https://drand.love) is a public randomness beacon run by the League of
## Entropy — a set of mutually independent organisations. Every 30 seconds the
## network jointly produces one 256-bit value as a BLS threshold signature. Two
## properties matter here:
##
##   * UNPREDICTABLE — a round's value cannot be known, by anyone, before its
##     timestamp. No single participant can produce it alone.
##   * PERMANENT and PUBLIC — once emitted it is served forever, by many
##     independent mirrors, and is cryptographically verifiable against the
##     chain's public key. There is no version of it to disagree about.
##
## So the draw is fixed in advance and knowable by nobody in advance. That is
## the whole trick.
##
##
## THE PROTOCOL — three steps, no live session
##
##   1. COMMIT THE RULE, BEFORE THE ROUND EXISTS.
##      Commit this file to git and send both authors the commit hash. Git is a
##      timestamped hash chain, so the commit is itself the proof that the rule
##      predated the draw — which is the property that makes the result
##      trustworthy. Do this at least a day before ROUND's timestamp.
##
##   2. WAIT until the round's timestamp has passed.
##
##   3. RUN THIS SCRIPT.  Rscript author_order.R
##      Anyone can run it, from any machine, at any later date, and get the same
##      answer. Nothing below depends on local state, locale or R version.
##
##
## THE RULE — stated exactly, with no free parameters
##
##   AUTHORS is in alphabetical order by surname (Martínez < Peña): fixed, not
##   chosen. ROUND is a stated future instant. Let d be the first hex digit of
##   that round's `randomness` field:
##
##       d even  ->  AUTHORS[1] goes first
##       d odd   ->  AUTHORS[2] goes first
##
##   `randomness` is a uniform 256-bit string, so its first hex digit is uniform
##   on 0..15 and the parity split is exactly 50/50. Nothing here can be tuned
##   after the fact: every input is pinned above the line that uses it.
##
##
## VERIFYING IT WITHOUT R
##
## The value this script reads is one HTTP GET, so any reviewer can check the
## result by hand and does not have to trust this code:
##
##     curl -s https://api.drand.sh/8990e7a9aaed2ffed73dbd7092123d6f289930540d7651336225dc172e51b2ce/public/6496886
##
## Read `randomness`, take its first character, and apply the rule above.
##
##
## CHOOSING A ROUND NUMBER FOR A DIFFERENT DATE
##
## The default chain has genesis_time 1595431050 and period 30 s, so
##
##     round = floor((unix_seconds - 1595431050) / 30) + 1
##
## In R, for an instant given in UTC:
##
##     ts <- as.numeric(as.POSIXct("2026-09-25 12:00:00", tz = "UTC"))
##     (ts - 1595431050) %/% 30 + 1
##
## Always publish the round NUMBER, not only the date: the number is
## unambiguous, whereas a date needs a timezone to be meaningful.
##
## ---------------------------------------------------------------------------

## --- Parameters, all fixed before the draw ---------------------------------

AUTHORS <- c("Lican Martínez", "Ramón Peña Agrest")  # alphabetical by surname
ROUND   <- 6496886                                   # 2026-09-25 12:00:00 UTC
CHAIN   <- "8990e7a9aaed2ffed73dbd7092123d6f289930540d7651336225dc172e51b2ce"

## --- The draw ---------------------------------------------------------------

draw <- function(round = ROUND, authors = AUTHORS, chain = CHAIN) {
  url <- sprintf("https://api.drand.sh/%s/public/%d", chain, round)

  txt <- tryCatch(paste(readLines(url, warn = FALSE), collapse = ""),
                  error = function(e) stop(
                    "could not read drand round ", round, ".\n",
                    "  If its timestamp has not passed yet the round does not exist ",
                    "and this is expected;\n  otherwise check connectivity to ",
                    "api.drand.sh.\n  underlying error: ", conditionMessage(e),
                    call. = FALSE))

  randomness <- sub('.*"randomness":"([0-9a-f]+)".*', "\\1", txt)
  if (!grepl("^[0-9a-f]{64}$", randomness))
    stop("unexpected response from drand; got: ", substr(txt, 1, 200), call. = FALSE)

  digit <- strtoi(substr(randomness, 1, 1), base = 16L)
  first <- if (digit %% 2 == 0) 1L else 2L

  list(round      = round,
       randomness = randomness,
       digit      = digit,
       order      = c(authors[first], authors[-first]))
}

## --- Report -----------------------------------------------------------------

res <- draw()

cat("drand round  :", res$round, "\n")
cat("randomness   :", res$randomness, "\n")
cat("first digit  :", res$digit, if (res$digit %% 2 == 0) "(even)" else "(odd)", "\n")
cat("author order :", paste(res$order, collapse = ", "), "\n")
