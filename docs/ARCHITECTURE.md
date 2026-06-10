# Architecture (Phase 1)

Hayward is intentionally thin. It does not implement a router, a budget engine,
or an identity system — it composes two things that already do those jobs and
writes only the join.

## The two halves

**asfquart** (front) handles *who you are and what you're allowed to do*. In
production the app is built with `asfquart.construct("hayward")`, which mounts
the ASF OAuth gateway at `/auth`, supports bearer PATs via a `token_handler`,
and populates a `ClientSession` from LDAP with the user's `uid`, committer
`projects`, and PMC `committees`. Per-PMC gating is the `@require(R.pmc_member)`
decorator. None of this is reimplemented here.

**litellm proxy** (backend) handles *the catalog, the call, and what it cost*.
It exposes an OpenAI-compatible API, tracks spend per *team*, and enforces
per-team budgets. Hayward provisions one team per ASF project.

## The seam

`seam.py` is the Phase 1 code that matters. On each call it:

1. **authorizes** — the calling identity must be a member of the project it
   wants to bill (or a site admin);
2. **resolves** the ASF project to a litellm team, provisioning the team with a
   budget on first use;
3. **runs** the metered chat through the backend, where the budget is enforced.

The activity view (`/v1/projects/<p>/usage`) is gated to PMC admins, so "for
each project you can see everyone's activity" is satisfied without exposing one
project's usage to another.

Keeping the ASF-project ↔ litellm-team mapping correct as PMC membership
changes is the substance flagged in the plan as "the part that isn't free." In
Phase 1 the mapping is created lazily and persisted in `store.py`; a production
deployment should reconcile it against LDAP on a schedule.

## Why it runs with no infrastructure

So the gateway is reviewable and demoable anywhere, both halves have a local
stand-in selected by environment variables:

- `HAYWARD_AUTH_MODE=dev` → a stub login that produces the same `Identity` an
  asfquart session would.
- `HAYWARD_LITELLM_MODE=mock` → an in-process backend that fakes completions and
  tracks per-team spend with a simple cost model, so budgets and the activity
  view are exercised end to end.

Flipping both to `asf` / `proxy` swaps in the real systems without changing any
code above the backend interface.

## Request path

```
client → [asfquart front] → seam.authorize → seam.resolve team
       → [litellm proxy] budget-check → model → debit team → log usage
       → response
```

See `../README.md` for the API and quickstart, and the build plan PDF for the
phase roadmap.
