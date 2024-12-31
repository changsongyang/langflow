import asyncio

import aiofiles
import anyio
import pytest


@pytest.fixture(autouse=True)
def _check_openai_api_key_in_environment_variables():
    pass


async def poll_until_job_is_completed(client, job_id, headers, times=10):
    job_endpoint = f"api/v1/jobs/{job_id}"
    for _ in range(times):
        response = await client.get(job_endpoint, headers=headers)
        if response.json()["status"] == "COMPLETED":
            return
        await asyncio.sleep(1)
    msg = f"Job {job_id} did not complete in the expected time."
    raise TimeoutError(msg)


async def test_webhook_endpoint(client, added_webhook_test, logged_in_headers):
    # The test is as follows:
    # 1. The flow when run will get a "path" from the payload and save a file with the path as the name.
    # We will create a temporary file path and send it to the webhook endpoint, then check if the file exists.
    # 2. we will delete the file, then send an invalid payload to the webhook endpoint and check if the file exists.
    endpoint_name = added_webhook_test["endpoint_name"]
    endpoint = f"api/v1/webhook/{endpoint_name}"
    # Create a temporary file
    async with aiofiles.tempfile.TemporaryDirectory() as tmp:
        file_path = anyio.Path(tmp) / "test_file.txt"

        payload = {"path": str(file_path)}

        response = await client.post(endpoint, json=payload)
        assert response.status_code == 202
        job_id = response.json()["job_id"]
        await poll_until_job_is_completed(client, job_id, logged_in_headers)

        assert await file_path.exists()

    assert not await file_path.exists()

    # Send an invalid payload
    payload = {"invalid_key": "invalid_value"}
    response = await client.post(endpoint, json=payload)
    assert response.status_code == 202
    assert not await file_path.exists()


async def test_webhook_flow_on_run_endpoint(client, added_webhook_test, created_api_key):
    endpoint_name = added_webhook_test["endpoint_name"]
    endpoint = f"api/v1/run/{endpoint_name}?stream=false"
    # Just test that "Random Payload" returns 202
    # returns 202
    payload = {
        "output_type": "any",
    }
    response = await client.post(endpoint, headers={"x-api-key": created_api_key.api_key}, json=payload)
    assert response.status_code == 200, response.json()


async def test_webhook_with_random_payload(client, added_webhook_test):
    endpoint_name = added_webhook_test["endpoint_name"]
    endpoint = f"api/v1/webhook/{endpoint_name}"
    # Just test that "Random Payload" returns 202
    # returns 202
    response = await client.post(
        endpoint,
        json="Random Payload",
    )
    assert response.status_code == 202
