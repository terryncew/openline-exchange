# OpenLine limited beta walkthrough

This is a working local implementation awaiting review and separate publication
approval. No real capabilities, customers, payments or independent market
performance are represented by the shipped examples. The reviewed catalog is
empty; the synthetic examples are an explicit separate mode.

1. [Discover and compare capabilities](beta-synthetic-catalog-desktop.png).
   Search by task, inspect offered prices and context, compare immutable versions,
   and see the missing evidence instead of a universal score.
2. [Inspect provenance, usage terms and improvement lineage](beta-synthetic-detail-desktop.png).
   Original JSON and its SHA-256 remain available. Attribution metadata records
   credit; it does not establish legal ownership.
3. [Inspect failed evaluations](beta-synthetic-detail-outcomes-desktop.png).
   Each record exposes evaluator, scope, method, environment, selected sample,
   denominator, failure cases and limitations. Key authentication and actual
   reproduction are different states.
4. [Use Bureau Select](beta-synthetic-select-desktop.png).
   A generic brief, task, budget, currency, pricing unit and deadline produce a
   task-specific shortlist and ordinary cheapest-offer baseline. Synthetic,
   sparse and incompatible evidence produces abstention. Selection never
   authorizes work. Frozen mixed/reversal/sparse trials retain negative results
   and explicitly simulated settlement costs.
5. Prepare a work inquiry. A reviewed real capability with an approved contact
   creates an editable public GitHub issue draft; the visitor submits it on
   GitHub. Synthetic examples only download a sample draft. No issue was sent,
   payment initiated or work executed during validation.
6. [Use the same experience on mobile](beta-synthetic-mobile.png).
   Keyboard navigation, dialogs and responsive layout are browser-tested.
7. [Compare worker-specific execution evidence](beta-synthetic-worker-compare-desktop.png).
   Worker profiles expose their own evidence gaps and exact linked capability
   version/task/quote context. Capability reports are never promoted into worker
   execution claims.
8. [Start with the actual empty reviewed catalog](beta-reviewed-empty-desktop.png).
   The contribution guide explains capability/evaluation JSON, permissioned
   public evidence and separate maintainer approval. Agents can use the same
   versioned catalog, schemas, offline validator and GitHub PR path.

Architecture: Bureau validates data and computes evidence/selection context;
Exchange builds a static reviewed public bundle and presents discovery and
inquiries; Wallet keeps key verification and the existing owner/receiver
commissioning boundary. Contributed code is never executed by the catalog.

Run instructions and opening conditions are in the Bureau repository's
`docs/beta/DEPLOYMENT.md`; the updated assignment is `docs/beta/ASSIGNMENT.md`.
Hosted launch and real pilot contributions remain separate approved steps.
