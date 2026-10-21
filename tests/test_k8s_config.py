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

# Autopilot minimum requests for an extended-duration (safe-to-evict) pod
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


def test_run_pods_and_code_servers_share_default_priority():
    """Run/step pods and code servers both stay at priority 0 so neither can
    preempt the other.

    Run pods carried a `dagster-run` PriorityClass (1000) until 2026-09-08. A run
    pod preempted the kippcamden code server while the agent was uploading its
    metadata; the one gRPC UNAVAILABLE wrote ERROR to the control plane, and the
    agent never retries a location the control plane already marks as errored.
    The location stayed down for four days (#5187). Equal priority makes a run
    pod that fits nowhere wait for a new node instead.
    """
    values = _helm_values()

    for key in ("serverK8sConfig", "runK8sConfig"):
        assert "priorityClassName" not in values["workspace"][key].get(
            "podSpecConfig", {}
        )

    priority_classes = {
        m["metadata"]["name"]
        for m in values["extraManifests"]
        if m["kind"] == "PriorityClass"
    }

    assert priority_classes == {"dagster-agent"}


def test_every_dagster_pod_is_pinned_against_the_autoscaler():
    """Agent, run/step, and code server pods all carry safe-to-evict: "false".

    The code-server annotation is safe only while run pods and code servers share
    a priority. It was reverted in #4921 when run pods sat at 1000: pinning a
    code server to its node left preemption as the only way for a run pod to
    claim capacity, and Preempted ran ~118x baseline within the hour. With both
    at 0 (asserted above) that path is closed, and the annotation stops the
    autoscaler ScaleDown that killed kippmiami's code server on 2026-09-09.
    """
    values = _helm_values()
    key = "cluster-autoscaler.kubernetes.io/safe-to-evict"

    assert values["dagsterCloudAgent"]["annotations"][key] == "false"

    for config in ("serverK8sConfig", "runK8sConfig"):
        annotations = values["workspace"][config]["podTemplateSpecMetadata"][
            "annotations"
        ]

        assert annotations[key] == "false"


def test_code_server_requests_meet_extended_duration_minimum():
    """Autopilot applies a 500m / 2GiB minimum to extended-duration pods, which
    the safe-to-evict annotation makes these.
    """
    requests = _helm_values()["workspace"]["serverK8sConfig"]["containerConfig"][
        "resources"
    ]["requests"]

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


# arm64 nodes carry this taint. Autopilot adds the matching toleration only to
# pods that select arm64, and the fallback class cannot select an arch.
ARM_TOLERATION = {
    "key": "kubernetes.io/arch",
    "operator": "Equal",
    "value": "arm64",
    "effect": "NoSchedule",
}


def test_compute_class_prefers_arm_then_falls_back_to_amd64():
    """An arm64 stockout left pods Pending until runs failed the start timeout.
    The class tries arm64 first and provisions amd64 only when arm64 is out.
    """
    (compute_class,) = [
        m for m in _helm_values()["extraManifests"] if m["kind"] == "ComputeClass"
    ]

    assert compute_class["metadata"]["name"] == "dagster-arm-first"
    assert compute_class["spec"]["autopilot"]["enabled"] is True
    assert compute_class["spec"]["priorities"] == [
        {"podFamily": "general-purpose-arm"},
        {"podFamily": "general-purpose"},
    ]


@pytest.mark.parametrize("config", ["serverK8sConfig", "runK8sConfig"])
def test_dagster_pods_select_the_arm_first_class(config: str):
    """An arch key in the selector would disable the amd64 fallback, and a
    missing toleration would keep every pod off arm64. Warden rejects node
    affinity next to safe-to-evict on a custom class.
    """
    pod_spec = _helm_values()["workspace"][config]["podSpecConfig"]

    assert pod_spec["nodeSelector"] == {
        "cloud.google.com/compute-class": "dagster-arm-first"
    }
    assert ARM_TOLERATION in pod_spec["tolerations"]
    assert "nodeAffinity" not in pod_spec.get("affinity", {})


@pytest.mark.parametrize("config", ["server_k8s_config", "run_k8s_config"])
@pytest.mark.parametrize("location", CODE_LOCATIONS)
def test_locations_do_not_override_placement(location: str, config: str):
    """Per-location config deep-merges over Helm, so a location-level selector
    or node affinity would undo the fallback for that location.
    """
    path = REPO_ROOT / f"src/teamster/code_locations/{location}/dagster-cloud.yaml"
    k8s = yaml.safe_load(path.read_text())["locations"][0]["container_context"]["k8s"]
    # coerce so snake_case (node_selector) and camelCase keys are both caught
    pod_spec = _coerce(k8s.get(config, {}).get("pod_spec_config", {}))

    assert pod_spec.node_selector is None
    assert pod_spec.affinity is None or pod_spec.affinity.node_affinity is None


def test_agent_stays_on_scale_out_amd64():
    """The agent image is amd64-only, so it must not follow the other pods."""
    assert _helm_values()["dagsterCloudAgent"]["nodeSelector"] == {
        "cloud.google.com/compute-class": "Scale-Out",
        "kubernetes.io/arch": "amd64",
    }
