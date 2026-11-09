import numpy
import pandas
from dagster_shared import check
from sklearn.cluster import DBSCAN
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest

ETR_COLUMNS = [
    "etr1a",
    "etr1b",
    "etr2a",
    "etr2b",
    "etr2c",
    "etr2d",
    "etr3a",
    "etr3b",
    "etr3c",
    "etr3d",
    "etr4a",
    "etr4b",
    "etr4c",
    "etr4d",
    "etr4e",
    "etr4f",
    "etr5a",
    "etr5b",
    "etr5c",
]

# Each Grow coach rubric scores ETR plus one set of manager-feedback measures.
# measure_set comes from rpt_python__manager_pm_averages.
MEASURE_SET_COLUMNS = {
    "etr_so": [*ETR_COLUMNS, "so1", "so2", "so3", "so4", "so5", "so6", "so7", "so8"],
    "etr_values": [
        *ETR_COLUMNS,
        "excellence",
        "fun",
        "kid_focus",
        "presence",
        "punctuality",
        "radical_love",
        "team",
    ],
}

# DBSCAN's min_samples; PCA's 2 components need 2 rows
MIN_FIT_ROWS = 3

FIT_OUTPUT_COLUMNS = [
    "is_iqr_outlier",
    "pc1",
    "pc1_variance_explained",
    "pc2",
    "pc2_variance_explained",
    "cluster",
    "tree_outlier",
]

KEY_COLUMNS = ["observer_employee_number", "academic_year", "form_term"]


def _iqr_outliers(df: pandas.DataFrame) -> pandas.Series:
    q1 = numpy.percentile(df["overall_score"], 25)
    q3 = numpy.percentile(df["overall_score"], 75)

    iqr = q3 - q1

    outliers_array = numpy.where(
        (df["overall_score"] < q1 - 1.5 * iqr) | (df["overall_score"] > q3 + 1.5 * iqr)
    )[0]

    return check.inst(
        obj=df["observer_employee_number"].isin(
            df.loc[outliers_array]["observer_employee_number"].tolist()
        ),
        ttype=pandas.Series,
    )


def fit_outliers(df: pandas.DataFrame, columns: list[str]) -> pandas.DataFrame:
    """Add outlier-detection columns fit on one group of observer-rounds.

    Adds `is_iqr_outlier` (IQR on `overall_score`), `pc1`/`pc2` and their
    variance explained (2-component PCA on `columns`), `cluster` (DBSCAN on the
    principal components, -1 is an outlier), and `tree_outlier` (Isolation
    Forest on `columns`, -1 is an outlier).

    Args:
        df: Observer-round rows with no nulls in `columns` or `overall_score`.
        columns: Measure columns to fit on.

    Returns:
        A copy of `df` with a reset index and the output columns added. A group
        smaller than `MIN_FIT_ROWS` gets the output columns as all-null.
    """
    df = df.reset_index(drop=True)

    if df.shape[0] < MIN_FIT_ROWS:
        for col in FIT_OUTPUT_COLUMNS:
            df[col] = None
        return df

    df["is_iqr_outlier"] = _iqr_outliers(df)

    pca = PCA(n_components=2)
    principal_components = pca.fit_transform(X=df[columns])

    df["pc1"] = principal_components[:, 0]
    df["pc2"] = principal_components[:, 1]
    df["pc1_variance_explained"] = pca.explained_variance_ratio_[0]
    df["pc2_variance_explained"] = pca.explained_variance_ratio_[1]

    # 0.6 is the historic optimal epsilon
    df["cluster"] = DBSCAN(min_samples=3, eps=0.6).fit_predict(X=df[["pc1", "pc2"]])

    # assumes 10% of the data are outliers
    # trunk-ignore(pyright/reportArgumentType)
    model = IsolationForest(contamination=0.1)
    model.fit(X=df[columns])
    df["tree_outlier"] = model.predict(X=df[columns])

    return df


def score_partition(
    df: pandas.DataFrame, academic_year: int, form_term: str
) -> list[dict]:
    """Score one PM round's observers against their round and against all time.

    Each measure set is fit separately, on its own columns. A row missing one
    of its set's columns or `overall_score` is dropped. The global fit covers
    every row of the set across all years; the current fit covers the round's
    rows of the set.

    Args:
        df: Every row of `rpt_python__manager_pm_averages`.
        academic_year: The partition's academic year.
        form_term: The partition's PM round code (`PM1`-`PM3`).

    Returns:
        One record per scored observer-round in the partition, with fit
        columns suffixed `_current` and `_global`. Missing values are `None`,
        never `NaN`, so the records write to Avro.
    """
    records = []

    for measure_set, columns in MEASURE_SET_COLUMNS.items():
        is_scored = df[[*columns, "overall_score"]].notna().all(axis=1)

        df_set = check.inst(
            obj=df.loc[(df["measure_set"] == measure_set) & is_scored],
            ttype=pandas.DataFrame,
        )

        is_partition = (df_set["academic_year"] == academic_year) & (
            df_set["form_term"] == form_term
        )

        if not is_partition.any():
            continue

        df_global = fit_outliers(df_set, columns)
        df_current = fit_outliers(
            check.inst(obj=df_set.loc[is_partition], ttype=pandas.DataFrame), columns
        )

        df_scored = pandas.merge(
            left=df_current,
            right=df_global[[*KEY_COLUMNS, *FIT_OUTPUT_COLUMNS]],
            how="left",
            on=KEY_COLUMNS,
            suffixes=("_current", "_global"),
        )

        df_scored = df_scored.astype(object).where(df_scored.notna(), None)

        records.extend(df_scored.to_dict(orient="records"))

    return records
