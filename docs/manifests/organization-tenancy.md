Organization tenancy manifest
=============================

Objective
---------
- Introduce first-class organizations to replace single-tenant login, allow admins to invite users, and scope all resources by `organization_id`.

Scope of impact
---------------
- Backend: auth/session issuance, invite flows, membership checks, DB schema, storage paths, caching keys, background jobs.
- Frontend: onboarding (create org + admin), login, org switcher, member management, org-scoped navigation/links.
- Data: migrations to add `organization_id` everywhere and backfill legacy data into a default org.
- Ops: rollout sequence, feature flag, verification scripts.

Data model (target)
-------------------
- organizations: id (UUID), name, slug, created_at, updated_at.
- users: id, email (unique), password_hash, name, created_at, updated_at.
- organization_users: id, organization_id, user_id, role (owner|admin|member), status (active|invited), created_at.
- invites: id, organization_id, email, role, token, expires_at, inviter_id, accepted_at.
- Domain tables: add `organization_id` FK + index; enforce unique constraints within org where applicable (e.g., filenames per org).

Auth/session flows
------------------
- Org creation replaces current login page: submit org name + admin credentials → create org, user, membership role=owner, issue session containing `user_id` and `organization_id`.
- Login: email/password → resolve user → load memberships; if multiple, prompt org selection; store active org in session/JWT (and optionally last-used in local storage).
- Org switching endpoint: validate membership, rotate/refresh token or session state with new `organization_id`.
- Invites: admin/owner creates invite (email + role). Accept via token link; create user if absent, attach membership, mark invite accepted.

Access control and scoping
--------------------------
- Middleware: require active `organization_id`, validate membership status=active, and inject org context into handlers/services.
- All reads/writes filter on `organization_id`; server sets org on writes (ignore client-provided org ids).
- Role checks: owner/admin manage org settings and members; members have standard resource access.
- Storage/caches: prefix keys/paths with org id/slug (e.g., `orgs/{org_id}/...`).

API and URLs
------------
- Prefer org-aware routes: `/o/{org_slug}/...` or implicit org via session; keep server-side scoping regardless of client route.
- Add endpoints: create_org_with_admin, list_memberships, switch_org, create_invite, accept_invite, list_members, update_member_role, revoke_invite.

Migrations and backfill
-----------------------
- Add tables: organizations, organization_users, invites.
- Add `organization_id` to all domain tables; create indexes on `organization_id` and compound uniques as needed.
- Backfill: create “Legacy Org”, attach all existing users as owners, update all legacy rows with that org id.
- Add NOT NULL + FK constraints after backfill verification.

Frontend plan
-------------
- Replace login page with “Create organization” flow plus a “Sign in” option.
- Post-login org selector when multiple memberships; show current org in the nav and allow switching.
- Org settings: profile (name/slug), members list, invite management, roles.
- Ensure all resource pages load data scoped to active org; include org context in client queries.

Rollout and verification
------------------------
- Ship migrations first; run backfill and validation script ensuring every row has `organization_id`.
- Gate UI/flows behind feature flag; enable after validation.
- Add smoke tests: access isolation between orgs, invite acceptance (new vs existing user), org switch, storage prefix correctness.
- Audit logging should include organization_id and user_id.

Open questions
--------------
- Which domains need scoping beyond core resources (analytics, reports, background jobs, caches)?
- Preferred URL shape: enforce org slug everywhere or rely on session context?
- Any external integrations that need tenant-aware credentials or webhooks?


