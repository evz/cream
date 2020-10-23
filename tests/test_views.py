import pytest


@pytest.mark.django_db
def test_index(client, income_series):
    response = client.get('/')

    assert response.status_code == 200
