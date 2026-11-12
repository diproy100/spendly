# Spec: Profile Page

## Overview
This feature replaces the `/profile` placeholder string with a designed, read-only profile page for the logged-in user. The page shows an identity card (avatar initials, name, email, "member since" date), a row of summary stats (total spent, number of expenses, top category), a per-category spending breakdown, and the user's most recent expenses. This is the first page in Spendly that reads user-specific data out of the database, so it sets up the patterns that later expense features reuse: a login guard, user-scoped queries, and rupee formatting. It comes after login and logout because it needs `session["user_id"]` to know whose profile to show.

## Depends on
- Step 01 — Database Setup (`users` and `expenses` tables, `get_db()`, seed data)
- Step 02 — Registration (users can exist beyond the demo user)
- Step 03 — Login and Logout (`session["user_id"]` is set on login and cleared on logout)

## Routes
- `GET /profile` — render the profile page for the logged-in user — logged-in (redirect to `/login` with a flash message if `session["user_id"]` is missing)

The existing `/profile` placeholder route is upgraded; no other new routes.

## Database changes
No database changes. The existing `users` and `expenses` tables already contain everything the page needs.

New read-only helpers in `database/db.py`:
- `get_user_by_id(user_id)` — returns the `users` row (`id`, `name`, `email`, `created_at`), or `None`. Must not return `password_hash` to the template.
- `get_expense_summary(user_id)` — returns a dict with `total_amount` (float, `0.0` if no expenses), `expense_count` (int) and `top_category` (str or `None`), computed with `SUM` / `COUNT` / `GROUP BY` in SQL.
- `get_category_breakdown(user_id)` — returns a list of rows `(category, total)` ordered by `total DESC`.
- `get_recent_expenses(user_id, limit=5)` — returns the user's latest expenses ordered by `date DESC, id DESC`.

## Templates
- **Create:** `templates/profile.html` — extends `base.html`, loads `profile.css` through `{% block head %}`. Sections:
  1. **Profile header card**: a circular avatar with the user's initials, their name (display font), their email, and "Member since <Month YYYY>"
  2. **Stats row**: three cards for Total spent (₹, 2 decimals), Expenses (count) and Top category
  3. **Category breakdown**: one row per category showing its name, the ₹ total and a horizontal bar whose width is that category's percentage of the total spend (CSS width only, no chart library)
  4. **Recent expenses**: a table or list of the latest 5 expenses with date, description, category badge and amount
  5. **Empty state**: if the user has no expenses, a friendly message replaces sections 3 and 4
- **Modify:** `templates/base.html` — when `session.user_id` is set, the navbar shows "Profile" and "Sign out" links instead of "Sign in" / "Get started". Skip this if Step 03 has already done it.

## Files to change
- `app.py` — implement `profile()`: login guard, call the DB helpers, render `profile.html`; import `session` if not already imported
- `database/db.py` — add `get_user_by_id`, `get_expense_summary`, `get_category_breakdown`, `get_recent_expenses`
- `templates/base.html` — make the navbar links depend on whether the user is logged in (see Templates)

## Files to create
- `templates/profile.html`
- `static/css/profile.css`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()`
- Parameterised queries only — never use f-strings or string formatting in SQL
- Passwords hashed with werkzeug (no password handling on this page; never pass `password_hash` to the template)
- Use CSS variables — never hardcode hex values; reuse the existing tokens in `style.css` (`--paper-card`, `--accent`, `--accent-light`, `--border`, `--radius-md` etc.)
- All templates extend `base.html`
- Use `url_for()` for every internal link
- Every expense query must filter by `user_id = ?` so a user only ever sees their own data
- Do aggregation (sums, counts, grouping) in SQL, not in Python loops
- If `session["user_id"]` is missing, or refers to a user that no longer exists, clear the session, flash "Please sign in to view your profile." and redirect to `url_for("login")`
- Format money as `₹` followed by the amount with 2 decimals
- Page-specific styles go in `static/css/profile.css`, not in `style.css`
- The layout must work on mobile: stats cards stack to one column below ~640px, with no horizontal scroll

## Definition of done
- [ ] Visiting `/profile` while logged out redirects to `/login` and shows the sign-in flash message
- [ ] After logging in as `demo@spendly.com` / `demo123`, `/profile` shows "Demo User", the email and a "Member since" date
- [ ] The avatar shows the initials "DU" for Demo User
- [ ] Total spent for the demo user is ₹400.24 and the expense count is 8 (the seed data)
- [ ] Top category for the demo user is "Bills"
- [ ] The category breakdown lists every category the demo user has spent in, largest first, with bar widths that match each category's share
- [ ] Recent expenses shows 5 rows, newest date first
- [ ] A newly registered user with no expenses sees ₹0.00, 0 expenses and the empty-state message, with no errors
- [ ] When logged in, the navbar shows Profile and Sign out; when logged out, it shows Sign in and Get started
- [ ] At a narrow (~375px) window width the page has no horizontal scroll and the stat cards stack
- [ ] No hex colour values appear in `profile.html` or `profile.css`
- [ ] `/profile` no longer returns the placeholder string
