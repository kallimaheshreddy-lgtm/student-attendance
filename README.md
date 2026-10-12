# Student Attendance System

A web application for managing student records and daily attendance. It is built
with Python and Flask, and stores its data in a local SQLite database.

## What the application does

- Keeps a student roster with each student's name, student number, and class.
- Records attendance for a selected date as **Present**, **Absent**, **Late**, or
  **Excused**.
- Lets an administrator record attendance by scanning a student's QR code or
  entering their student number.
- Creates printable student ID cards with QR codes.
- Shows attendance summaries and date-range reports.
- Includes a dashboard and a SQLite database viewer.
- Requires an administrator account to use the main student and attendance
  pages.

## Requirements

- Windows with **Python 3.11** installed and available in Command Prompt.
- A modern web browser.
- Internet access is needed for the QR scanner and ID card pages to load their
  QR-code JavaScript libraries from their CDNs.

To check that Python is available, open **Command Prompt** and run:

```cmd
python --version
```

If Windows says that `python` is not recognized, install Python and select
**Add Python to PATH** during installation.

## Run locally with Windows Command Prompt

Open Command Prompt and change to the project folder. Update the path if you
saved the project somewhere else:

```cmd
cd /d "C:\Users\kalli\OneDrive\Desktop\Student Attendance"
```

Create and activate a virtual environment:

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

Install the required Python packages and start the app:

```cmd
python -m pip install -r requirements.txt
set ADMIN_USERNAME=your-admin-username
set ADMIN_PASSWORD=replace-with-a-unique-password-at-least-12-characters
python app.py
```

Replace the example values with your own before running the app. These
environment variables are used only to create the first administrator account
when the database has no administrator yet. The password is stored as a hash.
Do not commit real credentials to Git.

Keep this Command Prompt window open while using the application. In your
browser, open:

```text
http://127.0.0.1:5000
```

To stop the local server, return to Command Prompt and press **Ctrl+C**.

### Sign in and recover a password

Sign in with the administrator username and password configured above. The
public account-creation page has been removed. If an administrator account
already exists in `database.db`, its credentials remain in effect; changing
the environment variables does not replace an existing account.

To reset a forgotten password while running locally, open
`http://127.0.0.1:5000/forgot-password`. Choose a new password with at least 12
characters.

## Database and data

The application uses **`database.db`** in the project folder. It creates the
required tables when it starts, and adds sample students if the students table
is empty. Student and attendance data are stored in this file.

To print database tables and up to ten rows from each table in Command Prompt,
activate the virtual environment as above and run:

```cmd
python view_db.py
```

You can also view database tables in the browser at
`http://127.0.0.1:5000/database`.

**Back up `database.db` before moving the project or changing its data.** The
application uses `database.db`; other database files in the folder are not
automatically selected by the app.

## Project files

```text
app.py                 Flask application, routes, and database logic
api/index.py           Vercel serverless entry point
templates/             HTML pages
static/                CSS and JavaScript
database.db            Local SQLite database
view_db.py             Command-line database viewer
requirements.txt       Python dependencies
Procfile               Gunicorn start command
render.yaml            Render deployment configuration
vercel.json            Vercel routing configuration
```

## Deployment notes

The repository includes configuration for Render and Vercel.

For Render, deploy this repository as a Blueprint using `render.yaml`. Set
`ADMIN_USERNAME` and `ADMIN_PASSWORD` when Render prompts for the administrator
credentials; use a password of at least 12 characters. The Blueprint generates
a `SECRET_KEY`, enables production mode, and generates a
`PASSWORD_RESET_TOKEN`. In Render's **Environment** settings, retrieve the
recovery token and enter it on the **Forgot password?** page when resetting the
administrator password. Keep all of these values private.

The administrator account is created from the environment variables only if
the database does not already contain an administrator. If the service has
already been deployed with another account, use the existing credentials or
the recovery token to reset its password.

SQLite data stored on temporary serverless filesystems may not persist between
deployments or invocations. For a production deployment, use storage that
persists or replace SQLite with a persistent database service. Render's local
filesystem is also ephemeral unless a persistent disk is configured.
