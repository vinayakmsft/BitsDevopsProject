import pytest


def test_dashboard_loads_with_empty_statistics(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b"ACEest Fitness & Gym" in response.data
    assert b"No workouts yet" in response.data


def test_health_check_reports_database_status(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {
        "service": "aceest-fitness",
        "status": "healthy",
    }


def test_create_and_list_member(client):
    payload = {
        "name": "  Ravi Kumar  ",
        "email": "RAVI@EXAMPLE.COM",
        "membership": "Elite",
    }

    created = client.post("/api/members", json=payload)
    members = client.get("/api/members")

    assert created.status_code == 201
    assert created.get_json()["name"] == "Ravi Kumar"
    assert created.get_json()["email"] == "ravi@example.com"
    assert created.get_json()["joined_on"]
    assert members.status_code == 200
    assert members.get_json()[0]["workout_count"] == 0


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (
            {"email": "member@example.com", "membership": "Basic"},
            "Missing required fields: name.",
        ),
        (
            {"name": "A", "email": "member@example.com", "membership": "Basic"},
            "Name must contain at least 2 characters.",
        ),
        (
            {"name": "Member", "email": "not-an-email", "membership": "Basic"},
            "A valid email address is required.",
        ),
        (
            {"name": "Member", "email": "member@example.com", "membership": "Gold"},
            "Membership must be one of: Basic, Elite, Premium.",
        ),
        (
            {
                "name": "Member",
                "email": "member@example.com",
                "membership": "Basic",
                "joined_on": "10/01/2026",
            },
            "joined_on must use YYYY-MM-DD format.",
        ),
    ],
)
def test_member_validation(client, payload, message):
    response = client.post("/api/members", json=payload)

    assert response.status_code == 400
    assert response.get_json()["error"] == message


def test_duplicate_member_email_is_rejected(client, member):
    response = client.post(
        "/api/members",
        json={
            "name": "Another Maya",
            "email": member["email"].upper(),
            "membership": "Basic",
        },
    )

    assert response.status_code == 409
    assert "already exists" in response.get_json()["error"]


def test_json_content_type_is_required(client):
    response = client.post("/api/members", data="name=Ravi")

    assert response.status_code == 415
    assert response.get_json()["error"] == "Content-Type must be application/json."


def test_create_and_list_workout(client, member):
    response = client.post(
        "/api/workouts",
        json={
            "member_id": member["id"],
            "workout_type": "Strength",
            "duration_minutes": 55,
            "calories_burned": 420,
            "completed_on": "2026-02-15",
        },
    )
    workouts = client.get("/api/workouts")
    members = client.get("/api/members")

    assert response.status_code == 201
    assert response.get_json()["member_name"] == "Maya Singh"
    assert workouts.get_json()[0]["duration_minutes"] == 55
    assert members.get_json()[0]["workout_count"] == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"member_id": 0},
        {"member_id": True},
        {"workout_type": "Swimming"},
        {"duration_minutes": 0},
        {"duration_minutes": True},
        {"duration_minutes": 1441},
        {"calories_burned": -1},
        {"calories_burned": False},
        {"completed_on": "yesterday"},
    ],
)
def test_workout_validation(client, member, changes):
    payload = {
        "member_id": member["id"],
        "workout_type": "Cardio",
        "duration_minutes": 30,
        "calories_burned": 250,
    }
    payload.update(changes)

    response = client.post("/api/workouts", json=payload)

    assert response.status_code == 400
    assert "error" in response.get_json()


def test_workout_requires_existing_member(client):
    response = client.post(
        "/api/workouts",
        json={
            "member_id": 999,
            "workout_type": "HIIT",
            "duration_minutes": 20,
            "calories_burned": 300,
        },
    )

    assert response.status_code == 404
    assert response.get_json()["error"] == "Member not found."


def test_deleting_member_also_deletes_workouts(client, member):
    client.post(
        "/api/workouts",
        json={
            "member_id": member["id"],
            "workout_type": "Recovery",
            "duration_minutes": 25,
            "calories_burned": 80,
        },
    )

    deleted = client.delete(f"/api/members/{member['id']}")

    assert deleted.status_code == 204
    assert client.get("/api/members").get_json() == []
    assert client.get("/api/workouts").get_json() == []


def test_delete_unknown_member_returns_not_found(client):
    response = client.delete("/api/members/999")

    assert response.status_code == 404
    assert response.get_json()["error"] == "Member not found."


def test_unknown_api_route_returns_json(client):
    response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    assert response.is_json
    assert response.get_json()["error"] == "Resource not found."
