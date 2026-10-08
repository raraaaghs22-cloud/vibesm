# Auth Testing (Emergent Google Auth)
- Create test user + session directly in MongoDB (db: test_database, collections: users, user_sessions).
- users: {user_id, email, name, picture, created_at}; user_sessions: {user_id, session_token, expires_at (Date, +7d), created_at}
- Admin = email stored in db.settings {key:"admin", email}. Currently raraaaghs22@gmail.com (seeded from ADMIN_EMAIL env).
- To test admin: create a user with email raraaaghs22@gmail.com (or reuse existing user doc) + session token.
- To test non-admin: any other email -> /api/admin/* returns 403, /dashboard shows "bukan akun guru".
- Use cookie `session_token` (httpOnly, secure, SameSite=None) or `Authorization: Bearer <token>`.
- Cleanup: db.users.deleteMany({email:/test\.user\./}); db.user_sessions.deleteMany({session_token:/test_session/})
