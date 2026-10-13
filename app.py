import os
import re
import sqlite3
from datetime import date, datetime
from pathlib import Path

from flask import Flask, current_app, g, jsonify, render_template, request

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
VALID_MEMBERSHIPS = {"Basic", "Premium", "Elite"}
VALID_WORKOUT_TYPES = {"Cardio", "Strength", "Flexibility", "HIIT", "Recovery"}


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        DATABASE=os.getenv(
            "DATABASE_PATH", str(Path(app.instance_path) / "aceest.sqlite")
        ),
        JSON_SORT_KEYS=False,
    )

    if test_config:
        app.config.update(test_config)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    app.teardown_appcontext(close_database)

    with app.app_context():
        initialize_database()

    register_routes(app)
    return app


def get_database():
    if "database" not in g:
        g.database = sqlite3.connect(current_app.config["DATABASE"])
        g.database.row_factory = sqlite3.Row
        g.database.execute("PRAGMA foreign_keys = ON")
    return g.database


def close_database(_error=None):
    database = g.pop("database", None)
    if database is not None:
        database.close()


def initialize_database():
    database = get_database()
    database.executescript(
        """
        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            membership TEXT NOT NULL,
            joined_on TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS workouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id INTEGER NOT NULL,
            workout_type TEXT NOT NULL,
            duration_minutes INTEGER NOT NULL CHECK (duration_minutes > 0),
            calories_burned INTEGER NOT NULL CHECK (calories_burned >= 0),
            completed_on TEXT NOT NULL,
            FOREIGN KEY (member_id) REFERENCES members (id) ON DELETE CASCADE
        );
        """
    )
    database.commit()


def register_routes(app):
    @app.get("/")
    def dashboard():
        database = get_database()
        stats = database.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM members) AS members,
                (SELECT COUNT(*) FROM workouts) AS workouts,
                (SELECT COALESCE(SUM(duration_minutes), 0) FROM workouts)
                    AS minutes,
                (SELECT COALESCE(SUM(calories_burned), 0) FROM workouts)
                    AS calories
            """
        ).fetchone()
        recent_workouts = database.execute(
            """
            SELECT workouts.id, members.name AS member_name,
                   workouts.workout_type, workouts.duration_minutes,
                   workouts.calories_burned, workouts.completed_on
            FROM workouts
            JOIN members ON members.id = workouts.member_id
            ORDER BY workouts.completed_on DESC, workouts.id DESC
            LIMIT 6
            """
        ).fetchall()
        return render_template(
            "index.html", stats=stats, recent_workouts=recent_workouts
        )

    @app.get("/health")
    def health():
        get_database().execute("SELECT 1").fetchone()
        return jsonify(status="healthy", service="aceest-fitness")

    @app.get("/api/members")
    def list_members():
        members = get_database().execute(
            """
            SELECT members.id, members.name, members.email, members.membership,
                   members.joined_on, COUNT(workouts.id) AS workout_count
            FROM members
            LEFT JOIN workouts ON workouts.member_id = members.id
            GROUP BY members.id
            ORDER BY members.id
            """
        ).fetchall()
        return jsonify([dict(member) for member in members])

    @app.post("/api/members")
    def create_member():
        payload, error = require_json()
        if error:
            return error

        validation_error = validate_member(payload)
        if validation_error:
            return validation_error

        database = get_database()
        try:
            cursor = database.execute(
                """
                INSERT INTO members (name, email, membership, joined_on)
                VALUES (?, ?, ?, ?)
                """,
                (
                    payload["name"].strip(),
                    payload["email"].strip().lower(),
                    payload["membership"],
                    payload.get("joined_on", date.today().isoformat()),
                ),
            )
            database.commit()
        except sqlite3.IntegrityError:
            return api_error("A member with this email already exists.", 409)

        member = database.execute(
            "SELECT * FROM members WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return jsonify(dict(member)), 201

    @app.delete("/api/members/<int:member_id>")
    def delete_member(member_id):
        database = get_database()
        cursor = database.execute("DELETE FROM members WHERE id = ?", (member_id,))
        database.commit()
        if cursor.rowcount == 0:
            return api_error("Member not found.", 404)
        return "", 204

    @app.get("/api/workouts")
    def list_workouts():
        workouts = get_database().execute(
            """
            SELECT workouts.id, workouts.member_id, members.name AS member_name,
                   workouts.workout_type, workouts.duration_minutes,
                   workouts.calories_burned, workouts.completed_on
            FROM workouts
            JOIN members ON members.id = workouts.member_id
            ORDER BY workouts.completed_on DESC, workouts.id DESC
            """
        ).fetchall()
        return jsonify([dict(workout) for workout in workouts])

    @app.post("/api/workouts")
    def create_workout():
        payload, error = require_json()
        if error:
            return error

        validation_error = validate_workout(payload)
        if validation_error:
            return validation_error

        database = get_database()
        member = database.execute(
            "SELECT id FROM members WHERE id = ?", (payload["member_id"],)
        ).fetchone()
        if member is None:
            return api_error("Member not found.", 404)

        cursor = database.execute(
            """
            INSERT INTO workouts (
                member_id, workout_type, duration_minutes,
                calories_burned, completed_on
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                payload["member_id"],
                payload["workout_type"],
                payload["duration_minutes"],
                payload["calories_burned"],
                payload.get("completed_on", date.today().isoformat()),
            ),
        )
        database.commit()
        workout = database.execute(
            """
            SELECT workouts.id, workouts.member_id, members.name AS member_name,
                   workouts.workout_type, workouts.duration_minutes,
                   workouts.calories_burned, workouts.completed_on
            FROM workouts
            JOIN members ON members.id = workouts.member_id
            WHERE workouts.id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone()
        return jsonify(dict(workout)), 201

    @app.errorhandler(404)
    def not_found(_error):
        if request.path.startswith("/api/"):
            return api_error("Resource not found.", 404)
        return render_template("404.html"), 404


def require_json():
    if not request.is_json:
        return None, api_error("Content-Type must be application/json.", 415)
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return None, api_error("Request body must be a JSON object.", 400)
    return payload, None


def validate_member(payload):
    required = ("name", "email", "membership")
    missing = [field for field in required if not payload.get(field)]
    if missing:
        return api_error(f"Missing required fields: {', '.join(missing)}.", 400)
    if not isinstance(payload["name"], str) or len(payload["name"].strip()) < 2:
        return api_error("Name must contain at least 2 characters.", 400)
    if not isinstance(payload["email"], str) or not EMAIL_PATTERN.fullmatch(
        payload["email"].strip()
    ):
        return api_error("A valid email address is required.", 400)
    if payload["membership"] not in VALID_MEMBERSHIPS:
        return api_error(
            f"Membership must be one of: {', '.join(sorted(VALID_MEMBERSHIPS))}.",
            400,
        )
    if payload.get("joined_on") and not is_iso_date(payload["joined_on"]):
        return api_error("joined_on must use YYYY-MM-DD format.", 400)
    return None


def validate_workout(payload):
    required = (
        "member_id",
        "workout_type",
        "duration_minutes",
        "calories_burned",
    )
    missing = [field for field in required if field not in payload]
    if missing:
        return api_error(f"Missing required fields: {', '.join(missing)}.", 400)
    if (
        not isinstance(payload["member_id"], int)
        or isinstance(payload["member_id"], bool)
        or payload["member_id"] < 1
    ):
        return api_error("member_id must be a positive integer.", 400)
    if payload["workout_type"] not in VALID_WORKOUT_TYPES:
        return api_error(
            f"workout_type must be one of: {', '.join(sorted(VALID_WORKOUT_TYPES))}.",
            400,
        )
    if (
        not isinstance(payload["duration_minutes"], int)
        or isinstance(payload["duration_minutes"], bool)
        or payload["duration_minutes"] < 1
        or payload["duration_minutes"] > 1440
    ):
        return api_error("duration_minutes must be an integer from 1 to 1440.", 400)
    if (
        not isinstance(payload["calories_burned"], int)
        or isinstance(payload["calories_burned"], bool)
        or payload["calories_burned"] < 0
    ):
        return api_error("calories_burned must be a non-negative integer.", 400)
    if payload.get("completed_on") and not is_iso_date(payload["completed_on"]):
        return api_error("completed_on must use YYYY-MM-DD format.", 400)
    return None


def is_iso_date(value):
    if not isinstance(value, str):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def api_error(message, status_code):
    return jsonify(error=message), status_code


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
