"""Release scripts must be opt-in, deterministic, and never mutate by default."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_vultr_deploy_dryrun_without_any_docker_or_network():
    check = subprocess.run(['bash', str(ROOT/'scripts/deploy_vultr.sh'),
                            '--domain', 'demo.example.org'],
                           text=True, capture_output=True, timeout=5)
    assert check.returncode == 0
    assert 'PREFLIGHT ONLY' in check.stdout
    assert 'https://demo.example.org/judge' in check.stdout


def test_deploy_rejects_invalid_domains():
    for hostname in ('example;rm -rf /', 'http://demo.example.org', 'demo..example.org',
                     'localhost', 'UPPER.EXAMPLE.COM'):
        out = subprocess.run(['bash', str(ROOT/'scripts/deploy_vultr.sh'), '--domain', hostname],
                             text=True, capture_output=True, timeout=5)
        assert out.returncode == 2, hostname
        assert 'ERROR' in out.stderr


def test_deploy_never_runs_verify_without_apply():
    out = subprocess.run(['bash', str(ROOT/'scripts/deploy_vultr.sh'),
                          '--domain', 'demo.example.org', '--verify'],
                         text=True, capture_output=True, timeout=5)
    assert out.returncode == 2
    assert 'needs --apply' in out.stderr
