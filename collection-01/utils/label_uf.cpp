// collection-01/utils/label_uf.cpp
// Generic union-find (disjoint-set) primitives for step-05 object labelling.
// Sourced from R via Rcpp::sourceCpp(); see workflow/05-objects_metrics.R::label_uf().
//
// WHY. Labelling burned pixels into fire objects is a connected-components problem. The
// igraph route (build an explicit edge list + a graph object) OOMs at country scale — on the
// 116 M-cell FY2000 grid it exceeded 31 GB and was SIGKILL'd. Union-find needs only ONE int
// per node (the `parent` array, ~0.5 GB at 116 M cells): edges are applied on the fly and
// discarded, so it scales. Textbook disjoint-set with path halving; near-O(1) amortised per op
// (inverse-Ackermann). Cross-validated on FY2000: 82,025 components, matching GDAL's independent
// connected-component count.
//
// The primitives are LABELLING-AGNOSTIC: the CALLER decides which pairs to union — plain
// 8-connectivity, or the 7x7 dilation-equivalent window with the veg-class distance threshold
// (docs/05 §2). Only pair generation (in R) changes; this file never does.
#include <Rcpp.h>
#include <vector>
using namespace Rcpp;

// find root with path halving (compresses the tree as it walks)
static int uf_find(std::vector<int>& p, int x) {
  while (p[x] != x) { p[x] = p[p[x]]; x = p[x]; }
  return x;
}

// [[Rcpp::export]]
SEXP uf_new(int n) {                                   // forest of n singletons (0-based internally)
  std::vector<int>* p = new std::vector<int>(n);
  for (int i = 0; i < n; i++) (*p)[i] = i;
  XPtr<std::vector<int> > xp(p, true);                 // owning external pointer (freed by R GC)
  return xp;
}

// [[Rcpp::export]]
void uf_union(SEXP s, IntegerVector a, IntegerVector b) {   // union every pair (a[i], b[i]); ids are 1-based
  XPtr<std::vector<int> > xp(s);
  std::vector<int>& p = *xp;
  R_xlen_t m = a.size();
  for (R_xlen_t i = 0; i < m; i++) {
    int ra = uf_find(p, a[i] - 1), rb = uf_find(p, b[i] - 1);
    if (ra != rb) p[ra] = rb;
  }
}

// [[Rcpp::export]]
IntegerVector uf_labels(SEXP s) {                      // representative root (1-based) of every node
  XPtr<std::vector<int> > xp(s);
  std::vector<int>& p = *xp;
  int n = (int) p.size();
  IntegerVector out(n);
  for (int i = 0; i < n; i++) out[i] = uf_find(p, i) + 1;
  return out;
}
