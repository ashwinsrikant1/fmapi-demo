"""Unity Catalog helpers for model serving."""

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.catalog import ModelVersionInfoStatus


def resolve_latest_ready_model_version(client: WorkspaceClient, model_full_name: str) -> str:
    """Return the highest READY model version string for a UC registered model.

    Foundation models in ``system.ai`` are not guaranteed to use version 1; some
    families only publish newer version numbers.
    """
    versions = list(client.model_versions.list(model_full_name))
    if not versions:
        raise ValueError(
            f"No model versions returned for {model_full_name!r} "
            "(check EXECUTE on the model and USE_CATALOG/USE_SCHEMA on system.ai)."
        )
    with_ver = [v for v in versions if v.version is not None]
    if not with_ver:
        raise ValueError(f"No numeric versions for {model_full_name!r}")
    ready = [v for v in with_ver if v.status == ModelVersionInfoStatus.READY]
    pool = ready or with_ver
    return str(max(v.version for v in pool))
