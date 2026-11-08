"""Containment is opt-in, Docker-only, auditable and honestly unverified in CI mocks."""
from __future__ import annotations

from fastapi.testclient import TestClient

from inneros_agent_rush.containment import SCENARIOS, classify_scenario_result
from inneros_agent_rush.core import Ledger, WorkflowEngine, verify_run_integrity
from inneros_agent_rush.main import create_app
from inneros_agent_rush.runner import ExecutionResult, SandboxUnavailable


class RulesOnly:
    label = "deterministic_rules"
    enabled = False


class FakeRunner:
    def __init__(self, result: ExecutionResult | None = None, *, available=True):
        self.result = result
        self.available = available
        self.inputs = []

    def ready(self) -> bool:
        return self.available

    def run(self, code: str, assertions: str) -> ExecutionResult:
        if not self.available:
            raise SandboxUnavailable("Docker daemon unavailable; host execution forbidden")
        self.inputs.append((code, assertions))
        return self.result


def engine(tmp_path, runner: FakeRunner):
    return WorkflowEngine(Ledger(tmp_path / 'containment.sqlite'), runner=runner, model=RulesOnly())


def test_no_docker_is_saved_as_blocked_without_executing_host(tmp_path):
    runner = FakeRunner(available=False)
    app = create_app(engine(tmp_path, runner), public_demo=True)
    with TestClient(app) as client:
        r = client.post('/api/containment/verify', json={'scenario_id': 'network_egress'})
        assert r.status_code == 200
        result = r.json()
        assert result['kind'] == 'containment_lab'
        assert result['status'] == 'blocked'
        assert result['artifact'] is None
        assert result['events'][-1]['details']['no_host_fallback'] is True
        assert not runner.inputs
        assert client.get('/api/runs/' + result['id'] + '/verify').json()['verified'] is True
        assert client.get('/api/runs').json()[0]['status'] == 'blocked'


def test_mocked_isolation_facts_persist_with_real_hash_validation(tmp_path):
    # This is deliberately a stub; it does not certify a live Docker implementation.
    runner = FakeRunner(ExecutionResult(True, 0, "ASSERTIONS_PASSED", "", False,
                                        cleanup_verified=True))
    e = engine(tmp_path, runner)
    result = e.run_containment('read_only_root', public_demo=True)
    assert result['status'] == 'contained'
    assert len(runner.inputs) == 1
    assert runner.inputs[0] == (SCENARIOS['read_only_root'].code,
                                 SCENARIOS['read_only_root'].assertions)
    assert result['execution']['containment']['cleanup_verified'] is True
    assert verify_run_integrity(e.store.one(result['id']))['verified'] is True
    assert 'no independent Vultr' in result['artifact']['content']


def test_security_check_cannot_pass_without_cleanup_confirmation():
    scenario = SCENARIOS['network_egress']
    for state in (None, False):
        passed, reason = classify_scenario_result(
            scenario, ExecutionResult(True, 0, "ASSERTIONS_PASSED", "", False,
                                      cleanup_verified=state))
        assert passed is False
        assert 'removal' in reason


def test_timeout_requires_real_expiration_and_verified_cleanup():
    scenario = SCENARIOS['runaway_timeout']
    good = ExecutionResult(False, None, "", "deadline", True, cleanup_verified=True)
    bad = ExecutionResult(False, 2, "", "", False, cleanup_verified=True)
    assert classify_scenario_result(scenario, good)[0] is True
    assert classify_scenario_result(scenario, bad)[0] is False


def test_maliciously_claimed_host_mode_is_not_considered_isolated():
    scenario = SCENARIOS['read_only_root']
    fake_host = ExecutionResult(True, 0, "ASSERTIONS_PASSED", "", False,
                                execution_mode='host_subprocess', cleanup_verified=True)
    assert classify_scenario_result(scenario, fake_host)[0] is False


def test_public_demo_only_accepts_allowlisted_scenarios(tmp_path):
    runner = FakeRunner(available=False)
    with TestClient(create_app(engine(tmp_path, runner), public_demo=True)) as client:
        opts = client.get('/api/containment/scenarios')
        assert opts.status_code == 200
        assert {s['id'] for s in opts.json()['cases']} == set(SCENARIOS)
        assert client.post('/api/containment/verify', json={'scenario_id': '__import__("os")'}).status_code == 422
        assert client.post('/api/containment/verify', json={'scenario_id': 'arbitrary_code'}).status_code == 422
        assert not runner.inputs


def test_private_runner_does_not_expose_its_records_to_public(tmp_path):
    runner = FakeRunner(available=False)
    e = engine(tmp_path, runner)
    app = create_app(e, public_demo=False, auth_token='private-operator-token')
    with TestClient(app) as client:
        assert client.post('/api/containment/verify', json={'scenario_id': 'runaway_timeout'}).status_code == 401
        private = client.post('/api/containment/verify', json={'scenario_id':'network_egress'},
                              headers={'Authorization':'Bearer private-operator-token'})
        assert private.status_code == 200
        assert private.json()['public_demo'] is False
        assert client.get('/api/runs/'+private.json()['id']).status_code == 401


def test_tampering_with_containment_evidence_is_detected(tmp_path):
    e = engine(tmp_path, FakeRunner(ExecutionResult(True, 0, 'ASSERTIONS_PASSED', '', False,
                                                   cleanup_verified=True)))
    run = e.run_containment('network_egress')
    altered = {**run, 'artifact': {**run['artifact'], 'content': '{"fabricated": true}'}}
    assert verify_run_integrity(altered)['verified'] is False
    assert verify_run_integrity(run)['verified'] is True
