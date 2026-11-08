"""A local model may add hypotheses but never own the incident priority or side effects."""
from __future__ import annotations

import io
import json
from unittest.mock import patch

from inneros_agent_rush.core import Ledger, WorkflowEngine, event_chain_valid, verify_run_integrity
from inneros_agent_rush.llm import ModelError, OpenAICompatibleModel


class NoDocker:
    def ready(self): return False
    def run(self, *args): raise AssertionError("Triage must not require Docker")


class AdviceModel:
    label = "local_openai_compatible"
    enabled = True
    def incident_advice(self, **kwargs):
        assert kwargs["priority"] == "P1"
        return {"summary":"An upstream optical path may be interrupted.",
                "hypotheses":["Fiber patch lead could be disconnected"],
                "origin": self.label, "authority":"advisory_only"}


class UnavailableModel(AdviceModel):
    def incident_advice(self, **kwargs):
        raise ModelError("Endpoint unavailable; use policy-only flow")


def test_local_model_is_optional_and_does_not_override_policy(tmp_path):
    e = WorkflowEngine(Ledger(tmp_path / 'ai.sqlite'), runner=NoDocker(), model=AdviceModel())
    run = e.run_triage('Fiber switch offline', 'Remote SFP port link is down in synthetic demo')
    assert run['status'] == 'completed'
    assert 'P1' in run['artifact']['content']
    assert 'Optional AI advisory (non-binding)' in run['artifact']['content']
    assert 'Possible cause' in run['artifact']['content']
    assert any(ev['step']=='ai_advisory' and ev['details']['decision_authority']=='deterministic_policy'
               for ev in run['events'])
    assert event_chain_valid(run['events'])
    assert verify_run_integrity(run)['verified'] is True


def test_model_failure_never_breaks_critical_service_ticket_flow(tmp_path):
    e = WorkflowEngine(Ledger(tmp_path/'ai.sqlite'), runner=NoDocker(), model=UnavailableModel())
    run = e.run_triage('Fiber switch offline', 'Synthetic connectivity down on optical uplink')
    assert run['status']=='completed' and run['ticket_id']
    assert 'Optional AI advisory' not in run['artifact']['content']
    assert any(ev['step']=='ai_advisory' and ev['status']=='unavailable' for ev in run['events'])


def test_openai_compatible_api_advice_validation(monkeypatch):
    model = OpenAICompatibleModel()
    model.base = 'http://localhost:9999/v1'
    model.model = 'local-qwen-mock'
    model.key = 'test-secret-value'
    class FakeResponse:
        def __enter__(self): return self
        def __exit__(self,*args): return None
        def read(self,n):
            return json.dumps({'choices':[{'message':{'content':json.dumps({
                'summary':'Optical signal loss is plausible',
                'hypotheses':['SFP interface issue','Fiber patch cord issue'],
            })}}]}).encode()
    with patch('inneros_agent_rush.llm.urllib.request.urlopen', return_value=FakeResponse()) as req:
        advice = model.incident_advice(title='Demo switch offline', description='SFP is down',
                                       priority='P1',category='connectivity',checks=['Verify port'])
    assert advice['origin'] == 'local_openai_compatible'
    assert advice['authority'] == 'advisory_only'
    actual_request = req.call_args.args[0]
    payload = json.loads(actual_request.data)
    assert payload['model'] == 'local-qwen-mock'
    assert payload['messages'][0]['role'] == 'system'
    assert actual_request.get_header('Authorization') == 'Bearer test-secret-value'
    assert req.call_args.kwargs['timeout'] == 6
