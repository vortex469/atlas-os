`commit-outcome-unknown.json` is synthetic test data serialized from the Agent's
`_candidate_audit_detail` projection with the maintained candidate workflow,
planning and approval fixtures. It represents a blocked workflow with
`commit_outcome_unknown`, a valid partial evidence chain, and no verified commit
result. Both the commit section and timeline report `unknown`.

It is not a real approval, executed operator request or production acceptance
record. Browser tests serve it only for exact-origin reads and reject mutations.
