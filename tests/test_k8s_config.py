"""Structural checks on the Kubernetes config the Dagster Cloud agent consumes.

`dagster-cloud.yaml` has no schema gate before the agent applies it, so a
malformed `server_k8s_config` is otherwise caught only by a failed deploy. These
tests run the same coercion the agent runs, and encode the invariants the
scheduling-resilience spec depends on:
docs/superpowers/specs/2026-08-18-code-server-scheduling-resilience-design.md
"""

import pathlib
from typing import Any

import pytest
import yaml
from dagster_k8s.models import k8s_model_from_dict, k8s_snake_case_dict
from dagster_shared import check
from kubernetes.client.models import V1PodAntiAffinity, V1PodSpec

REPO_ROOT = pathlib.Path(__file__).parent.parent

CODE_LOCATIONS = ["kippcamden", "kippmiami", "kippnewark", "kipppaterson", "kipptaf"]

GRACE_PERIOD_KEY = "DAGSTER_CLOUD_CLEANUP_SERVER_GRACE_PERIOD_SECONDS"

# Autopilot minimum requests for an extended-duration pod, which
# cluster-autoscaler.kubernetes.io/safe-to-evict: "false" makes this pod
CODE_SERVER_MIN_CPU = "500m"
CODE_SERVER_MIN_MEMORY = "2.0Gi"


def _helm_values() -> dict[str, Any]:
    return yaml.safe_load((REPO_ROOT / ".k8s/dagster/values-override.yaml").read_text())


def _server_pod_spec_config(location: str) -> dict[str, Any]:
    path = REPO_ROOT / f"src/teamster/code_locations/{location}/dagster-cloud.yaml"
    doc = yaml.safe_load(path.read_text())

    k8s = doc["locations"][0]["container_context"]["k8s"]

    return k8s["server_k8s_config"]["pod_spec_config"]


def _coerce(pod_spec_config: dict[str, Any]) -> V1PodSpec:
    """Run the agent's own coercion. Raises on a shape Kubernetes would reject."""
    return k8s_model_from_dict(
        V1PodSpec,
        {**k8s_snake_case_dict(V1PodSpec, pod_spec_config), "containers": []},
    )


@pytest.mark.parametrize("location", CODE_LOCATIONS)
def test_server_anti_affinity_is_valid_and_self_scoped(location: str):
    """The per-location self-anti-affinity must coerce to a real
    V1WeightedPodAffinityTerm and must select its OWN location, not a copied one.
    """
    pod_spec = _coerce(_server_pod_spec_config(location))

    affinity = check.not_none(value=pod_spec.affinity)
    anti_affinity = check.inst(obj=affinity.pod_anti_affinity, ttype=V1PodAntiAffinity)

    assert anti_affinity.required_during_scheduling_ignored_during_execution is None

    terms = check.is_list(
        obj=anti_affinity.preferred_during_scheduling_ignored_during_execution
    )

    assert len(terms) == 1

    term = terms[0]

    assert term.weight == 100
    assert term.pod_affinity_term.topology_key == "kubernetes.io/hostname"

    expressions = term.pod_affinity_term.label_selector.match_expressions

    assert [e.key for e in expressions] == ["location_name"]
    assert expressions[0].values == [location]


def test_coercion_rejects_an_unnested_pod_affinity_term():
    """Guards the test above from being vacuous.

    `preferred` takes a WeightedPodAffinityTerm, so the un-nested form produced by
    renaming `required` to `preferred` without adding the `weight` /
    `podAffinityTerm` wrapper must fail rather than pass silently.
    """
    unnested = {
        "affinity": {
            "podAntiAffinity": {
                "preferredDuringSchedulingIgnoredDuringExecution": [
                    {
                        "labelSelector": {
                            "matchExpressions": [
                                {
                                    "key": "location_name",
                                    "operator": "In",
                                    "values": ["kipptaf"],
                                }
                            ]
                        },
                        "topologyKey": "kubernetes.io/hostname",
                    }
                ]
            }
        }
    }

    with pytest.raises(Exception, match="Unexpected keys in model class"):
        _coerce(unnested)


def test_run_pod_isolation_from_code_servers_stays_required():
    """Added after a production incident where run pods starved code servers.
    Relaxing this to `preferred` would reintroduce it, so it is asserted rather
    than left to review.
    """
    anti_affinity = _helm_values()["workspace"]["runK8sConfig"]["podSpecConfig"][
        "affinity"
    ]["podAntiAffinity"]

    assert "preferredDuringSchedulingIgnoredDuringExecution" not in anti_affinity

    terms = anti_affinity["requiredDuringSchedulingIgnoredDuringExecution"]

    # one term targets code servers, the other the agent; losing either
    # silently removes half the protection
    selectors = [t["labelSelector"]["matchLabels"] for t in terms]

    assert {
        "managed_by": "K8sUserCodeLauncher",
        "deployment_name": "prod",
    } in selectors
    assert {"app.kubernetes.io/name": "dagster-cloud-agent"} in selectors


def test_code_servers_keep_default_priority():
    """Code servers stay at priority 0 by decision: promoting them above
    dagster-run would make run pods queue instead.
    """
    server_config = _helm_values()["workspace"]["serverK8sConfig"]

    assert "priorityClassName" not in server_config.get("podSpecConfig", {})


def test_code_server_requests_support_extended_duration():
    """safe-to-evict: "false" makes the pod extended-duration, which Autopilot only
    honors at or above 500m / 2GiB. Lowering either silently voids the annotation.
    """
    server_config = _helm_values()["workspace"]["serverK8sConfig"]

    annotations = server_config["podTemplateSpecMetadata"]["annotations"]

    # must be the quoted string, not a YAML boolean
    assert annotations["cluster-autoscaler.kubernetes.io/safe-to-evict"] == "false"

    requests = server_config["containerConfig"]["resources"]["requests"]

    assert requests["cpu"] == CODE_SERVER_MIN_CPU
    assert requests["memory"] == CODE_SERVER_MIN_MEMORY


def test_agent_readiness_budget_covers_worst_case_first_reconcile():
    """The readiness sentinel is written only after the first full reconcile
    returns, and that reconcile awaits deploymentStartupTimeout +
    serverProcessStartupTimeout per location. If the probe budget is smaller, the
    agent rollout stalls on the very helm upgrade that raises the timeouts.
    """
    values = _helm_values()

    workspace = values["workspace"]
    worst_case = (
        workspace["deploymentStartupTimeout"] + workspace["serverProcessStartupTimeout"]
    )

    agent = values["dagsterCloudAgent"]
    probe = agent["readinessProbe"]
    readiness_budget = probe["failureThreshold"] * probe["periodSeconds"]

    assert readiness_budget > worst_case, (
        f"readiness budget {readiness_budget}s does not cover worst-case first"
        f" reconcile {worst_case}s"
    )

    # CLAUDE.md: do not set the cleanup grace period below reconciliation time,
    # or an orphaned code server can be deleted before its replacement is ready
    grace_period = int(agent["env"][GRACE_PERIOD_KEY])

    assert grace_period > worst_case, (
        f"cleanup grace period {grace_period}s is below worst-case first reconcile"
        f" {worst_case}s"
    )

    install_sh = (REPO_ROOT / ".k8s/dagster/install.sh").read_text()
    rollout_line = next(
        line for line in install_sh.splitlines() if "rollout status" in line
    )
    rollout_timeout = int(rollout_line.split("--timeout=")[1].rstrip("s"))

    assert rollout_timeout >= readiness_budget, (
        f"install.sh rollout timeout {rollout_timeout}s is below the readiness"
        f" budget {readiness_budget}s, so a healthy-but-slow upgrade reports failure"
    )
