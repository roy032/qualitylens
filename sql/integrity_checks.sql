-- QualityLens: data-integrity queries against the Gitea database.
-- Each query returns the rows that VIOLATE a rule, so an empty result means "healthy".
-- tests/db/test_db_consistency.py runs the same rules automatically.
-- Run by hand:  docker compose exec -T db psql -U gitea -d gitea -f - < sql/integrity_checks.sql

-- 1. Repository issue counters must equal the real number of issue rows.
SELECT r.id, r.owner_name, r.name, r.num_issues, r.num_closed_issues,
       COUNT(i.id)                                 AS actual_issues,
       COUNT(i.id) FILTER (WHERE i.is_closed)      AS actual_closed
FROM repository r
LEFT JOIN issue i ON i.repo_id = r.id AND i.is_pull = false
GROUP BY r.id
HAVING r.num_issues <> COUNT(i.id)
    OR r.num_closed_issues <> COUNT(i.id) FILTER (WHERE i.is_closed);

-- 2. No orphaned issues (issue pointing at a repository that no longer exists).
SELECT i.id, i.repo_id, i.name
FROM issue i
LEFT JOIN repository r ON r.id = i.repo_id
WHERE r.id IS NULL;

-- 3. Issue comment counters must equal the number of plain comments (type 0).
SELECT i.id, i.num_comments, COUNT(c.id) AS actual_comments
FROM issue i
LEFT JOIN comment c ON c.issue_id = i.id AND c.type = 0
GROUP BY i.id
HAVING i.num_comments <> COUNT(c.id);

-- 4. Label usage counters must equal the number of issue_label links.
SELECT l.id, l.name, l.num_issues, COUNT(il.id) AS actual
FROM label l
LEFT JOIN issue_label il ON il.label_id = l.id
GROUP BY l.id
HAVING l.num_issues <> COUNT(il.id);

-- 5. Closed issues must have a close timestamp, open issues must not.
SELECT id, is_closed, closed_unix
FROM issue
WHERE (is_closed AND COALESCE(closed_unix, 0) = 0)
   OR (NOT is_closed AND COALESCE(closed_unix, 0) <> 0);

-- 6. Every user has exactly one primary email, and it matches user.email.
SELECT u.id, u.name, u.email, COUNT(e.id) FILTER (WHERE e.is_primary) AS primaries
FROM "user" u
LEFT JOIN email_address e ON e.uid = u.id
WHERE u.type = 0  -- individual users (organisations have no login email)
GROUP BY u.id
HAVING COUNT(e.id) FILTER (WHERE e.is_primary) <> 1
    OR MAX(CASE WHEN e.is_primary THEN e.lower_email END) <> lower(u.email);

-- 7. Stored lower-case names must match the display names (used for case-insensitive lookups).
SELECT id, name, lower_name FROM "user" WHERE lower_name <> lower(name)
UNION ALL
SELECT id, name, lower_name FROM repository WHERE lower_name <> lower(name);
