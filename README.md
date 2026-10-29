# GHOST Backend

The REST API for GHOST. The website in `../frontend` uses it for logins,
products, orders, reviews and the contact form.

## Stack

- Python 3.11+ and Django 5.2
- Django REST Framework
- JWT login with Simple JWT
- SQLite by default, PostgreSQL (Supabase) when you set `DATABASE_URL`

## Quick start

```bash
python3 -m venv .venv
source .venv\Scripts\activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_products   # adds the 5 hoodies
python manage.py runserver 8000
.\.venv\Scripts\activate  
```

The API runs at http://localhost:8000/api. Django's admin panel is at
http://localhost:8000/admin.

Run the tests with:

```bash
python manage.py test apps
```

## Database setup

### SQLite (default)

You don't need to do anything. If `DATABASE_URL` is empty, Django uses
`backend/db.sqlite3`.

### Supabase PostgreSQL

1. Create a **separate Supabase project for Vault**. Do not reuse another Django app's database, because their Django tables can conflict.
2. In the project dashboard click **Connect** → **Direct Connection** → set **Method** to **Session Pooler**. Copy the provided URI. Keep the pooler host, username, and port exactly as shown; do not substitute the direct-connection host.
3. Replace `[YOUR-PASSWORD]` in the URI with the database password. If it contains URL-special characters (such as `@`, `#`, `/`, or `%`), URL-encode them first. Add the values to the Vault backend `.env` file (or your production host's environment):

   ```
   DATABASE_URL=<paste the complete Session Pooler URI here>
   DATABASE_SSL_REQUIRE=1
   ```

   Keep the URI private. The `.env` file is ignored by Git; do not commit or share it.
4. Create the tables and add the products:

   ```bash
   python manage.py migrate
   python manage.py seed_products
   ```

5. Start the server again. Accounts and other data from SQLite are not copied over, so sign up again or migrate the data separately.

## Plesk production deployment

For the Docker Stack setup on Plesk, using `g4057.com` for the frontend and
`api.g4057.com` for this API, follow
[PLESK_PANEL_DEPLOY_GUIDE.md](PLESK_PANEL_DEPLOY_GUIDE.md). Start from
`.env.plesk.example` for production settings; never upload or commit the real
`.env`. To build a timestamped, validated release archive on Windows, run
`python .\scripts\make_plesk_release.py` from this backend folder.

## Apps

| App        | What it does                                       |
| ---------- | -------------------------------------------------- |
| `accounts` | Sign up, login, JWT tokens, member approval        |
| `products` | Products and stock for each size (S, M, L, XL)     |
| `orders`   | Placing orders and updating order status           |
| `reviews`  | Product reviews and admin replies                  |
| `contact`  | Contact form messages and admin replies            |

## Access rules

- New accounts start as **pending**. They can log in but can't shop.
- **Approved** accounts can shop, see their orders and write reviews.
- **Rejected** accounts can't log in. Their old tokens stop working too.
- Admins approve or reject members from the Admin Dashboard.
- `hasshamahmed73@gmail.com` is the owner. It is approved as admin on sign up.
  Nobody can reject or delete it.
- Only the owner can make other people admins.

## Login credentials

| Role          | Email                      | Password      |
| ------------- | -------------------------- | ------------- |
| Owner / Admin | `hasshamahmed73@gmail.com` | `12Admin45/?` |
| Member        | `hasshamahmed13@gmail.com` | `12Hassham01`   |

On a new database, sign up with these first. The owner then approves the member.

## Main API endpoints

All paths start with `/api`. Send `Authorization: Bearer <access token>` for
anything that needs a login.

| Method       | Path                         | Who            | What it does                  |
| ------------ | ---------------------------- | -------------- | ----------------------------- |
| POST         | `/auth/register/`            | Anyone         | Create an account             |
| POST         | `/auth/login/`               | Anyone         | Get access and refresh tokens |
| POST         | `/auth/token/refresh/`       | Anyone         | Get a new access token        |
| GET          | `/auth/me/`                  | Logged in      | Your profile and status       |
| GET          | `/auth/members/`             | Admin          | List members                  |
| PATCH        | `/auth/members/<id>/`        | Admin          | Approve or reject a member    |
| GET          | `/products/`                 | Anyone         | List products                 |
| POST         | `/products/`                 | Admin          | Add a product                 |
| PATCH        | `/products/<id>/`            | Admin          | Edit a product or its stock   |
| POST         | `/orders/`                   | Approved       | Place an order                |
| GET          | `/orders/`                   | Logged in      | Your orders (admins see all)  |
| PATCH        | `/orders/<id>/status/`       | Admin          | Change order status           |
| GET / POST   | `/reviews/`                  | Anyone / Approved | Read or write reviews      |
| POST         | `/contact/`                  | Anyone         | Send a message                |

Order status goes Pending → Confirmed → Processing → Shipped → Delivered.

## Environment variables

Copy `.env.example` to `.env`. Everything has a default for local use.

| Name                    | Default                    | What it does                              |
| ----------------------- | -------------------------- | ----------------------------------------- |
| `DJANGO_DEBUG`          | `0`                        | Set to `1` for local development          |
| `DJANGO_SECRET_KEY`     | (dev key when debug is on) | Required when debug is off                |
| `DATABASE_URL`          | empty (SQLite)             | PostgreSQL connection string              |
| `DATABASE_SSL_REQUIRE`  | `0`                        | Set to `1` for Supabase                   |
| `CORS_ALLOWED_ORIGINS`  | localhost ports 3000, 5173, 8080 | Frontend addresses allowed to call the API |
| `FRONTEND_URL`          | `http://localhost:8080`    | Used in password reset emails             |
| `EMAIL_BACKEND`         | console                    | Emails print in the terminal by default   |
| `JWT_ACCESS_MINUTES`    | `15`                       | How long an access token lasts            |
| `JWT_REFRESH_DAYS`      | `7`                        | How long a refresh token lasts            |
