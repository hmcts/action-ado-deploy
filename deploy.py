import os
import sys
import time
import json
import requests
from base64 import b64encode


def get_required_env(name):
    value = os.getenv(name)
    if not value:
        return None
    return value


def trigger_pipeline(base_url, headers, ref_name, template_parameters, api_version):
    url = f"{base_url}/runs?api-version={api_version}"

    payload = {
        "resources": {
            "repositories": {
                "self": {
                    "refName": ref_name
                }
            }
        },
        "templateParameters": template_parameters
    }

    print(f"Triggering pipeline...")
    print(f"Template Parameters = {json.dumps(template_parameters, indent=2)}")

    response = requests.post(url, headers=headers, json=payload)

    try:
        response_json = response.json()
        print("Response JSON:")
        print(json.dumps(response_json, indent=2))
    except ValueError:
        print(f"Response Text: {response.text}")
        response_json = None

    if response.status_code != 200:
        print(f"Failed to trigger pipeline (HTTP {response.status_code})")
        sys.exit(1)

    if response_json is None or "id" not in response_json:
        print("Failed to get pipeline run ID from response")
        sys.exit(1)

    if not isinstance(response_json["id"], (str, int)):
        print(f"Invalid run ID type: {type(response_json['id']).__name__}")
        sys.exit(1)

    return str(response_json["id"])


def monitor_pipeline(base_url, run_id, headers, api_version, poll_interval, timeout):
    url = f"{base_url}/runs/{run_id}?api-version={api_version}"

    print(f"Monitoring pipeline run {run_id}")
    print(f"Poll interval: {poll_interval}s, timeout: {timeout}s")

    elapsed = 0
    while elapsed < timeout:
        response = requests.get(url, headers=headers)

        if response.status_code != 200:
            print(f"API request failed with status {response.status_code}: {response.text}")
            sys.exit(1)

        data = response.json()
        state = data.get("state", "unknown")
        result = data.get("result", "")

        print(f"[{elapsed}s] State: {state}, Result: {result}")

        if state == "completed":
            return result

        time.sleep(poll_interval)
        elapsed += poll_interval

    print(f"Timeout after {timeout}s waiting for pipeline to complete")
    sys.exit(1)


def write_output(name, value):
    github_output = os.getenv("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"{name}={value}\n")


def main():
    ado_org = get_required_env("INPUT_ADO_ORG")
    ado_project = get_required_env("INPUT_ADO_PROJECT")
    pipeline_id = get_required_env("INPUT_PIPELINE_ID")
    ado_pat = get_required_env("INPUT_ADO_PAT")
    ref_name = get_required_env("INPUT_REF_NAME")
    api_version = get_required_env("INPUT_API_VERSION")
    template_parameters_raw = get_required_env("INPUT_TEMPLATE_PARAMETERS")
    poll_interval = int(os.getenv("INPUT_POLL_INTERVAL", "30"))
    timeout = int(os.getenv("INPUT_TIMEOUT", "1800"))
    wait = os.getenv("INPUT_WAIT", "true").lower() == "true"

    required = {
        "ADO_ORG": ado_org,
        "ADO_PROJECT": ado_project,
        "PIPELINE_ID": pipeline_id,
        "ADO_PAT": ado_pat,
        "REF_NAME": ref_name,
        "API_VERSION": api_version,
        "TEMPLATE_PARAMETERS": template_parameters_raw,
    }

    missing = [name for name, value in required.items() if not value]
    if missing:
        print(f"Missing required inputs: {', '.join(missing)}")
        sys.exit(1)

    try:
        template_parameters = json.loads(template_parameters_raw)
    except json.JSONDecodeError:
        print("Invalid JSON for template parameters")
        sys.exit(1)

    if not template_parameters:
        print("Template parameters must not be empty")
        sys.exit(1)

    print(f"ADO Org = {ado_org}")
    print(f"ADO Project = {ado_project}")
    print(f"Pipeline ID = {pipeline_id}")
    print(f"Ref Name = {ref_name}")

    auth = b64encode(f":{ado_pat}".encode()).decode()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {auth}",
    }

    base_url = f"https://dev.azure.com/{ado_org}/{ado_project}/_apis/pipelines/{pipeline_id}"

    run_id = trigger_pipeline(base_url, headers, ref_name, template_parameters, api_version)
    print(f"Pipeline run ID: {run_id}")
    write_output("run_id", run_id)

    if not wait:
        print("Wait disabled, pipeline triggered successfully")
        return

    result = monitor_pipeline(base_url, run_id, headers, api_version, poll_interval, timeout)
    write_output("result", result)

    if result == "succeeded":
        print("Pipeline completed successfully")
    else:
        print(f"Pipeline completed with result: {result}")
        sys.exit(1)


if __name__ == "__main__":
    main()
