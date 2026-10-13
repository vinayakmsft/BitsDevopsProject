# ACEest Fitness & Gym

A production-ready Flask application and automated CI/CD reference project for
managing gym members and recording workout activity. The project demonstrates
application modularization, automated testing, containerization, Jenkins builds,
and continuous integration with GitHub Actions.


## Features

- Responsive fitness dashboard with live member and workout statistics
- REST API for member registration, listing, and deletion
- REST API for workout creation and activity history
- SQLite persistence with foreign-key integrity and cascading cleanup
- Input validation with consistent JSON errors and HTTP status codes
- Health endpoint suitable for container and deployment probes
- Pytest suite with branch coverage enforcement
- Non-root Docker image with a built-in health check
- Jenkins declarative build pipeline
- GitHub Actions pipeline for syntax, lint, image build, and containerized tests

## Architecture

```text
Browser / API client
        |
        v
Flask + Gunicorn
  |           |
Jinja UI    JSON API
        |
        v
      SQLite
```

The Flask application uses an application factory, opens one SQLite connection
per request context, and initializes its schema automatically. In local
development the database is created at `instance/aceest.sqlite`. The database
path can be overridden with `DATABASE_PATH`.

## Repository layout

```text
.
|-- .github/workflows/main.yml  # GitHub Actions CI pipeline
|-- static/style.css            # Dashboard styles
|-- templates/                  # Jinja dashboard and error pages
|-- tests/                      # Pytest suite and fixtures
|-- app.py                      # Application factory, data layer, and routes
|-- compose.yaml                # Local Docker Compose service
|-- Dockerfile                  # Reproducible non-root image
|-- Jenkinsfile                 # Jenkins build and quality gates
|-- pyproject.toml              # Pytest, coverage, and Ruff settings
|-- requirements.txt            # Runtime dependencies
`-- requirements-dev.txt        # Test and lint dependencies
```

## Prerequisites

Choose either the native Python workflow or Docker:

- Python 3.11 or newer
- Git
- Docker Engine or Docker Desktop (for container execution)
- Jenkins with access to Docker (for the Jenkins pipeline)

## Local setup

### Windows PowerShell

```powershell
git clone https://github.com/OWNER/REPOSITORY.git
Set-Location REPOSITORY
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python app.py
```

### macOS or Linux

```bash
git clone https://github.com/OWNER/REPOSITORY.git
cd REPOSITORY
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python app.py
```

Open <http://localhost:5000>. Verify service readiness at
<http://localhost:5000/health>.

The development server is for local use only. For a production-style local
process, run:

```bash
gunicorn --bind 0.0.0.0:5000 --workers 2 --threads 2 app:app
```

## API reference

All request bodies must use `Content-Type: application/json`.

| Method | Endpoint | Purpose | Success |
|---|---|---|---|
| `GET` | `/` | Render the activity dashboard | `200` |
| `GET` | `/health` | Check application and database health | `200` |
| `GET` | `/api/members` | List members and workout counts | `200` |
| `POST` | `/api/members` | Register a member | `201` |
| `DELETE` | `/api/members/<id>` | Delete a member and their workouts | `204` |
| `GET` | `/api/workouts` | List workout history | `200` |
| `POST` | `/api/workouts` | Record a workout | `201` |

### Register a member

```bash
curl -X POST http://localhost:5000/api/members \
  -H "Content-Type: application/json" \
  -d '{"name":"Maya Singh","email":"maya@example.com","membership":"Premium"}'
```

Membership must be `Basic`, `Premium`, or `Elite`. The optional `joined_on`
field uses `YYYY-MM-DD`; it defaults to today.

### Record a workout

```bash
curl -X POST http://localhost:5000/api/workouts \
  -H "Content-Type: application/json" \
  -d '{"member_id":1,"workout_type":"Strength","duration_minutes":45,"calories_burned":360}'
```

Workout type must be `Cardio`, `Strength`, `Flexibility`, `HIIT`, or
`Recovery`. The optional `completed_on` field uses `YYYY-MM-DD`; it defaults to
today.

## Tests and quality checks

Install the development dependencies, then run:

```bash
pytest
ruff check .
python -m compileall -q app.py tests
```

`pytest` generates a terminal coverage report and fails below 90% branch
coverage. The suite covers dashboard rendering, health checks, member and
workout lifecycles, input validation, duplicate handling, missing resources,
content types, and cascading deletion.

To generate a browsable HTML coverage report:

```bash
pytest --cov-report=html
```

Then open `htmlcov/index.html`.

## Docker

### Build and run

```bash
docker build -t aceest-fitness:local .
docker run --rm -p 5000:5000 --name aceest aceest-fitness:local
```

Run tests exactly as CI does:

```bash
docker run --rm aceest-fitness:local pytest
```

Run with persistent database storage through Compose:

```bash
docker compose up --build -d
docker compose ps
docker compose logs -f web
docker compose down
```

Use `docker compose down -v` only when the stored local database should also be
deleted.

### Image design

The image is based on the small `python:3.13-slim` base, installs pinned
dependencies without a pip cache, runs as the unprivileged `aceest` user, and
uses Gunicorn instead of Flask's development server. Its health check calls the
application's database-aware `/health` endpoint.

## Jenkins BUILD pipeline

The `Jenkinsfile` defines the controlled secondary build and quality gate:

1. **Checkout** obtains the exact revision from source control.
2. **Build image** creates a uniquely tagged image using the Jenkins build
   number.
3. **Lint and syntax** runs Ruff and Python byte-code compilation in the image.
4. **Unit tests** runs the complete Pytest suite in the image.
5. **Post-build cleanup** removes the temporary image and workspace.

### Jenkins setup

1. Provision a Linux Jenkins agent with Git and Docker installed.
2. Permit the Jenkins service account to access the Docker daemon according to
   your organization's security policy.
3. In **Manage Jenkins > Plugins**, install:
   - Pipeline
   - Git
   - GitHub
   - Workspace Cleanup
4. Select **New Item > Multibranch Pipeline** (recommended).
5. Add the GitHub repository as the branch source. For a private repository,
   add a least-privilege GitHub credential; a public repository needs none.
6. Keep the script path as `Jenkinsfile`, scan the repository, and run the
   discovered branch.
7. Add a GitHub webhook pointing to
   `https://JENKINS_HOST/github-webhook/` with the `push` event. The Jenkins
   host must be reachable by GitHub over HTTPS.
8. Confirm all four stages pass in the Jenkins build view.

For a simple Pipeline job instead, choose **Pipeline script from SCM**, select
Git, enter the repository URL, set the branch to `*/main`, and use
`Jenkinsfile` as the script path.

## GitHub Actions CI

`.github/workflows/main.yml` runs on every push and pull request. It:

1. Checks out the source.
2. Configures Python 3.13 and caches pip downloads.
3. Installs the pinned development dependencies.
4. checks Python syntax with `compileall`.
5. lints the repository with Ruff.
6. builds the Docker image.
7. runs Pytest inside that image.

The workflow has read-only repository permissions, cancels stale builds for the
same ref, and enforces a 15-minute timeout. Protect the `main` branch in GitHub
and require the **Build, lint, and test** check before merge.

## Version-control workflow

Initialize and publish the repository:

```bash
git init
git branch -M main
git add .
git commit -m "feat: build ACEest fitness management service"
git remote add origin https://github.com/OWNER/REPOSITORY.git
git push -u origin main
```

Use short-lived branches and Conventional Commit-style messages:

```bash
git switch -c feature/member-search
git commit -m "feat: add member search endpoint"
git switch main
git switch -c fix/workout-validation
git commit -m "fix: reject workouts with invalid durations"
```

Open a pull request, allow GitHub Actions and Jenkins to pass, request review,
then merge. Do not commit `.env`, local databases, virtual environments, or
credentials; these paths are excluded in `.gitignore`.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `PORT` | `5000` | Port used by direct `python app.py` execution |
| `DATABASE_PATH` | `instance/aceest.sqlite` | SQLite database file location |

Example:

```bash
DATABASE_PATH=/data/aceest.sqlite PORT=8080 python app.py
```

In PowerShell:

```powershell
$env:DATABASE_PATH = "C:\aceest-data\aceest.sqlite"
$env:PORT = "8080"
python app.py
```

## Troubleshooting

- **Port 5000 is busy:** map another host port with
  `docker run -p 8080:5000 ...` or set `PORT=8080` for direct execution.
- **Jenkins cannot access Docker:** verify Docker is running and that the
  Jenkins agent has explicit daemon access. Restart the agent after permission
  changes.
- **Database is read-only in a container:** mount a writable directory or named
  volume at `/app/instance`, as shown in `compose.yaml`.
- **GitHub webhook does not trigger Jenkins:** use GitHub's webhook delivery log
  to confirm DNS, TLS, response status, and public reachability.

## License

This project is provided for educational use as part of the ACEest DevOps
assignment.
