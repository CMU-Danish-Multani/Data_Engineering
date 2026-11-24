-- Personal PostgreSQL login for Danish on the shared stock_intelligence RDS.
-- Run by a teammate who can create roles (the RDS master user), connected to
-- the stock_intelligence database in pgAdmin (Query Tool). No secrets in here:
-- replace TEMPORARY_PASSWORD, then Danish replaces it with a personal one (step 4).

-- 1. Who owns the project objects? Expect one owner, probably stock_team.
SELECT DISTINCT tableowner AS owner FROM pg_tables WHERE schemaname IN ('dev', 'final')
UNION
SELECT DISTINCT viewowner FROM pg_views WHERE schemaname IN ('dev', 'final');

-- 2. Create the login and make it a member of that owner role.
--    Membership is needed because adding columns to final.company_financials_quarterly
--    replaces the view, which only its owner may do.
CREATE ROLE mmultani LOGIN PASSWORD 'TEMPORARY_PASSWORD';
GRANT stock_team TO mmultani;          -- use the owner from step 1 if it differs

-- 3. New tables and views created by Danish are owned by the team role, so
--    teammates can still change them.
ALTER ROLE mmultani SET role TO stock_team;

-- 4. Danish, after the first login, sets a personal password:
--    ALTER ROLE mmultani PASSWORD 'new password';

-- 5. Check: should list mmultani with membership in stock_team.
SELECT r.rolname, array_agg(m.rolname) AS member_of
FROM pg_roles r
JOIN pg_auth_members a ON a.member = r.oid
JOIN pg_roles m ON m.oid = a.roleid
WHERE r.rolname = 'mmultani'
GROUP BY r.rolname;
