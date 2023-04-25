import pytest


@pytest.mark.django_db
def test_notification_view(
    mixer, token, active_user, second_user, follower, john_snow, auth_api
):
    mixer.blend("store.Ownership", token=token, owner=auth_api.user, quantity=10)
    token.owners.add(auth_api.user)
    mixer.blend(
        "activity.UserAction", user=follower, whom_follow=auth_api.user, method="follow"
    )
    mixer.blend(
        "activity.UserAction",
        user=second_user,
        whom_follow=auth_api.user,
        method="follow",
    )
    mixer.blend("activity.UserAction", user=second_user, token=token, method="like")

    response = auth_api.get("/api/v1/activity/notification/")
    assert response.status_code == 200
    assert len(response.json()) == 3

    # check read by id
    response = auth_api.post(
        "/api/v1/activity/notification/",
        data={"activity_ids": response.json()[0]["id"]},
    )
    assert response.status_code == 200
    response = auth_api.get("/api/v1/activity/notification/")
    assert response.status_code == 200
    assert len(response.json()) == 2

    # check read all
    response = auth_api.post("/api/v1/activity/notification/", data={"method": "all"})
    assert response.status_code == 200
    response = auth_api.get("/api/v1/activity/notification/")
    assert response.status_code == 200
    assert len(response.json()) == 0


@pytest.mark.django_db
def test_activity_views(
    mixer, token, active_user, second_user, follower, john_snow, api
):
    # check user activity
    mixer.blend(
        "activity.UserAction", user=follower, whom_follow=active_user, method="follow"
    )
    response = api.get(f"/api/v1/activity/{active_user.username}/")
    assert response.status_code == 200
    assert len(response.json()["results"]) == 1
    response = api.get(f"/api/v1/activity/{follower.username}/following/")
    assert response.status_code == 200
    assert len(response.json()["results"]) == 0

    # check following activity
    mixer.blend(
        "activity.UserAction",
        user=active_user,
        whom_follow=second_user,
        method="follow",
    )
    response = api.get(f"/api/v1/activity/{active_user.username}/")
    assert response.status_code == 200
    assert len(response.json()["results"]) == 1
    response = api.get(f"/api/v1/activity/{follower.username}/following/")
    assert response.status_code == 200
    assert len(response.json()["results"]) == 1

    # check all activity
    response = api.get(f"/api/v1/activity/")
    assert response.status_code == 200
    assert len(response.json()["results"]) == 2
