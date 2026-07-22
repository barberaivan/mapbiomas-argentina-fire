#!/usr/bin/env Rscript
# Stage 0b (memory-bounded): 8-connected labelling by UNION-FIND. No edge list, no graph
# object — only an N-int parent array (~0.5 GB). Unions are applied one forward-offset at a
# time (only one offset's index pairs in RAM at once), so peak RAM ~ the cached table + parent.
# Plain 8-conn (no dilation halo) — fine for the A-vs-B comparison (both paths take THIS pid).
suppressPackageStartupMessages({ library(data.table); library(Rcpp); library(jsonlite) })
OUT <- Sys.getenv("F2000_DIR")
g <- jsonlite::fromJSON(file.path(OUT, "meta_grid.json")); nc <- g$ncol; N <- g$n_cells
row <- readBin(file.path(OUT, "row.i32"), integer(), n = N, size = 4L)
col <- readBin(file.path(OUT, "col.i32"), integer(), n = N, size = 4L)
dt <- data.table(row = row, col = col, idx = seq_len(N)); rm(row, col)
dt[, cell := (as.numeric(row) - 1) * nc + col]; setkey(dt, cell)

Rcpp::sourceCpp(code = '
#include <Rcpp.h>
#include <vector>
using namespace Rcpp;
static int uf_find(std::vector<int>&p,int x){while(p[x]!=x){p[x]=p[p[x]];x=p[x];}return x;}
// [[Rcpp::export]]
SEXP uf_new(int n){std::vector<int>*p=new std::vector<int>(n);for(int i=0;i<n;i++)(*p)[i]=i;XPtr<std::vector<int>>xp(p,true);return xp;}
// [[Rcpp::export]]
void uf_union(SEXP s, IntegerVector a, IntegerVector b){XPtr<std::vector<int>>xp(s);std::vector<int>&p=*xp;
  R_xlen_t m=a.size();for(R_xlen_t i=0;i<m;i++){int ra=uf_find(p,a[i]-1),rb=uf_find(p,b[i]-1);if(ra!=rb)p[ra]=rb;}}
// [[Rcpp::export]]
IntegerVector uf_labels(SEXP s){XPtr<std::vector<int>>xp(s);std::vector<int>&p=*xp;int n=p.size();
  IntegerVector out(n);for(int i=0;i<n;i++)out[i]=uf_find(p,i)+1;return out;}
')

t1 <- Sys.time()
uf  <- uf_new(N)
fwd <- list(c(0L,1L), c(1L,0L), c(1L,1L), c(1L,-1L))   # 4 offsets cover 8-adjacency once
for (o in fwd) {
  ncl <- dt$col + o[2]; ok <- ncl >= 1L & ncl <= nc
  nb  <- (as.numeric(dt$row) + o[1] - 1) * nc + ncl
  j   <- dt[.(nb), on = "cell", idx]
  keep <- ok & !is.na(j)
  uf_union(uf, dt$idx[keep], j[keep])
  rm(ncl, ok, nb, j, keep); gc(FALSE)
}
pid <- as.integer(factor(uf_labels(uf)))                # compact roots -> 1..n_pids
np  <- length(unique(pid))
cat(sprintf("STAGE0b label (8-conn union-find): n_pids=%d label_wall_s=%.1f\n",
            np, as.numeric(Sys.time() - t1, units = "secs")))
writeBin(as.integer(pid), file.path(OUT, "pid.i32"), size = 4L)
write_json(c(g, list(n_pids = np)), file.path(OUT, "meta.json"), auto_unbox = TRUE, digits = 15)
cat("STAGE0 DONE\n")
