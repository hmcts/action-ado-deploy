import json

import pytest
import responses

from deploy import get_required_env, main, monitor_pipeline, trigger_pipeline, write_output


ADO_BASE_URL = "https://dev.azure.com/test-org/test-project/_apis/pipelines/123"
API_VERSION = "7.0"
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": "Basic OnRlc3QtcGF0",
}


class TestGetRequiredEnv:
    def test_returns_value_when_set(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "hello")
        assert get_required_env("TEST_VAR") == "hello"

    def test_returns_none_when_missing(self, monkeypatch):
        monkeypatch.delenv("TEST_VAR", raising=False)
        assert get_required_env("TEST_VAR") is None

    def test_returns_none_when_empty(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "")
        assert get_required_env("TEST_VAR") is None


class TestTriggerPipeline:
    @responses.activate
    def test_successful_trigger(self):
        responses.add(
            responses.POST,
            f"{ADO_BASE_URL}/runs?api-version={API_VERSION}",
            json={"id": 456, "state": "inProgress"},
            status=200,
        )

        run_id = trigger_pipeline(
            ADO_BASE_URL, HEADERS, "refs/heads/main", {"env": "dev"}, API_VERSION
        )
        assert run_id == "456"

        body = json.loads(responses.calls[0].request.body)
        assert body["templateParameters"] == {"env": "dev"}
        assert body["resources"]["repositories"]["self"]["refName"] == "refs/heads/main"

    @responses.activate
    def test_trigger_failure_exits(self):
        responses.add(
            responses.POST,
            f"{ADO_BASE_URL}/runs?api-version={API_VERSION}",
            json={"message": "Unauthorized"},
            status=401,
        )

        with pytest.raises(SystemExit) as exc:
            trigger_pipeline(
                ADO_BASE_URL, HEADERS, "refs/heads/main", {"env": "dev"}, API_VERSION
            )
        assert exc.value.code == 1

    @responses.activate
    def test_trigger_missing_id_exits(self):
        responses.add(
            responses.POST,
            f"{ADO_BASE_URL}/runs?api-version={API_VERSION}",
            json={"state": "inProgress"},
            status=200,
        )

        with pytest.raises(SystemExit) as exc:
            trigger_pipeline(
                ADO_BASE_URL, HEADERS, "refs/heads/main", {"env": "dev"}, API_VERSION
            )
        assert exc.value.code == 1

    @responses.activate
    def test_trigger_non_json_response_exits(self):
        responses.add(
            responses.POST,
            f"{ADO_BASE_URL}/runs?api-version={API_VERSION}",
            body="Internal Server Error",
            status=500,
        )

        with pytest.raises(SystemExit) as exc:
            trigger_pipeline(
                ADO_BASE_URL, HEADERS, "refs/heads/main", {"env": "dev"}, API_VERSION
            )
        assert exc.value.code == 1


class TestMonitorPipeline:
    @responses.activate
    def test_returns_result_on_completion(self):
        responses.add(
            responses.GET,
            f"{ADO_BASE_URL}/runs/456?api-version={API_VERSION}",
            json={"state": "completed", "result": "succeeded"},
            status=200,
        )

        result = monitor_pipeline(ADO_BASE_URL, "456", HEADERS, API_VERSION, 1, 10)
        assert result == "succeeded"

    @responses.activate
    def test_polls_until_complete(self):
        responses.add(
            responses.GET,
            f"{ADO_BASE_URL}/runs/456?api-version={API_VERSION}",
            json={"state": "inProgress", "result": ""},
            status=200,
        )
        responses.add(
            responses.GET,
            f"{ADO_BASE_URL}/runs/456?api-version={API_VERSION}",
            json={"state": "completed", "result": "failed"},
            status=200,
        )

        result = monitor_pipeline(ADO_BASE_URL, "456", HEADERS, API_VERSION, 0, 10)
        assert result == "failed"
        assert len(responses.calls) == 2

    @responses.activate
    def test_timeout_exits(self):
        responses.add(
            responses.GET,
            f"{ADO_BASE_URL}/runs/456?api-version={API_VERSION}",
            json={"state": "inProgress", "result": ""},
            status=200,
        )

        with pytest.raises(SystemExit) as exc:
            monitor_pipeline(ADO_BASE_URL, "456", HEADERS, API_VERSION, 0, 0)
        assert exc.value.code == 1

    @responses.activate
    def test_api_error_exits(self):
        responses.add(
            responses.GET,
            f"{ADO_BASE_URL}/runs/456?api-version={API_VERSION}",
            json={"message": "Not Found"},
            status=404,
        )

        with pytest.raises(SystemExit) as exc:
            monitor_pipeline(ADO_BASE_URL, "456", HEADERS, API_VERSION, 1, 10)
        assert exc.value.code == 1


class TestWriteOutput:
    def test_writes_to_github_output(self, monkeypatch, tmp_path):
        output_file = tmp_path / "output.txt"
        monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))

        write_output("run_id", "789")
        assert output_file.read_text() == "run_id=789\n"

    def test_appends_multiple_outputs(self, monkeypatch, tmp_path):
        output_file = tmp_path / "output.txt"
        monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))

        write_output("run_id", "789")
        write_output("result", "succeeded")
        assert output_file.read_text() == "run_id=789\nresult=succeeded\n"

    def test_no_op_without_github_output(self, monkeypatch):
        monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
        write_output("run_id", "789")


class TestMain:
    def _set_env(self, monkeypatch, tmp_path, overrides=None):
        output_file = tmp_path / "output.txt"
        env = {
            "INPUT_ADO_ORG": "test-org",
            "INPUT_ADO_PROJECT": "test-project",
            "INPUT_PIPELINE_ID": "123",
            "INPUT_ADO_PAT": "test-pat",
            "INPUT_REF_NAME": "refs/heads/main",
            "INPUT_API_VERSION": "7.0",
            "INPUT_TEMPLATE_PARAMETERS": '{"env": "dev"}',
            "INPUT_POLL_INTERVAL": "0",
            "INPUT_TIMEOUT": "10",
            "INPUT_WAIT": "true",
            "GITHUB_OUTPUT": str(output_file),
        }
        if overrides:
            env.update(overrides)
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        return output_file

    def test_missing_required_input_exits(self, monkeypatch, tmp_path):
        self._set_env(monkeypatch, tmp_path, {"INPUT_ADO_PAT": ""})

        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1

    def test_invalid_json_exits(self, monkeypatch, tmp_path):
        self._set_env(monkeypatch, tmp_path, {"INPUT_TEMPLATE_PARAMETERS": "not-json"})

        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1

    def test_empty_template_parameters_exits(self, monkeypatch, tmp_path):
        self._set_env(monkeypatch, tmp_path, {"INPUT_TEMPLATE_PARAMETERS": "{}"})

        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1

    @responses.activate
    def test_fire_and_forget(self, monkeypatch, tmp_path):
        output_file = self._set_env(monkeypatch, tmp_path, {"INPUT_WAIT": "false"})

        responses.add(
            responses.POST,
            f"{ADO_BASE_URL}/runs?api-version={API_VERSION}",
            json={"id": 789, "state": "inProgress"},
            status=200,
        )

        main()

        output = output_file.read_text()
        assert "run_id=789" in output
        assert "result=" not in output

    @responses.activate
    def test_successful_deploy(self, monkeypatch, tmp_path):
        output_file = self._set_env(monkeypatch, tmp_path)

        responses.add(
            responses.POST,
            f"{ADO_BASE_URL}/runs?api-version={API_VERSION}",
            json={"id": 789, "state": "inProgress"},
            status=200,
        )
        responses.add(
            responses.GET,
            f"{ADO_BASE_URL}/runs/789?api-version={API_VERSION}",
            json={"state": "completed", "result": "succeeded"},
            status=200,
        )

        main()

        output = output_file.read_text()
        assert "run_id=789" in output
        assert "result=succeeded" in output

    @responses.activate
    def test_failed_deploy_exits(self, monkeypatch, tmp_path):
        self._set_env(monkeypatch, tmp_path)

        responses.add(
            responses.POST,
            f"{ADO_BASE_URL}/runs?api-version={API_VERSION}",
            json={"id": 789, "state": "inProgress"},
            status=200,
        )
        responses.add(
            responses.GET,
            f"{ADO_BASE_URL}/runs/789?api-version={API_VERSION}",
            json={"state": "completed", "result": "failed"},
            status=200,
        )

        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1
