from unittest.mock import patch
from fastapi.testclient import TestClient
import pytest
from inneros_agent_rush.worker_service import create_worker_app
from inneros_agent_rush.remote_runner import RemoteRunner
from inneros_agent_rush.runner import ExecutionResult, SandboxUnavailable


class StubWorker:
    def ready(self):
        return True
    def run(self, code, tests):
        return ExecutionResult(True, 0, "ASSERTIONS_PASSED", "", False)


def test_worker_requires_private_bearer_token():
    with TestClient(create_worker_app(worker_token="dedicated-secret",runner=StubWorker())) as client:
        assert client.get("/internal/healthz").status_code == 401
        assert client.post("/internal/execute", json={"code":"x=1","tests":"assert x"}).status_code == 401
        assert client.get("/internal/healthz",headers={"Authorization":"Bearer dedicated-secret"}).json()["sandbox_ready"] is True
        result=client.post("/internal/execute",json={"code":"x=1","tests":"assert x"},headers={"Authorization":"Bearer dedicated-secret"})
        assert result.status_code == 200 and result.json()["passed"] is True


def test_remote_runner_without_credentials_fails_closed():
    r=RemoteRunner("http://private-runner.invalid:8050", "")
    assert r.ready() is False
    with pytest.raises(SandboxUnavailable):
        r.run("x=1", "assert x")


def test_worker_does_not_boot_without_auth():
    with TestClient(create_worker_app(worker_token="", runner=StubWorker())) as client:
        assert client.get("/internal/healthz",headers={"Authorization":"Bearer anything"}).status_code == 401


def test_remote_worker_protocol_and_secret_handling():
    import io, json
    captured=[]
    class Reply:
        def __init__(self,payload):self.payload=payload
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,limit):return json.dumps(self.payload).encode()
    def fake_urlopen(req, timeout):
        captured.append((req.full_url,req.headers,req.data,timeout))
        if req.full_url.endswith('/healthz'):
            return Reply({'sandbox_ready':True})
        return Reply({'passed':True, 'exit_code':0,'stdout':'ASSERTIONS_PASSED','stderr':'','timeout':False})
    with patch('inneros_agent_rush.remote_runner.urllib.request.urlopen',side_effect=fake_urlopen):
        r=RemoteRunner('http://10.0.0.2:8050','private-test-token')
        assert r.ready()
        outcome=r.run('x=1','assert x')
        assert outcome.passed and outcome.execution_mode == 'remote_vultr_docker_worker'
        assert len(captured)==2
        assert all(h['Authorization']=='Bearer private-test-token' for _,h,_,_ in captured)
        assert b'"code": "x=1"' in captured[1][2]
