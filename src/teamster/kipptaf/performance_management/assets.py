import numpy
import pandas
from sklearn.cluster import DBSCAN
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest

FIT_TRANSFORM_COLUMNS = [
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
    "so1",
    "so2",
    "so3",
    "so4",
    "so5",
    "so6",
    "so7",
    "so8",
]


def get_iqr_outliers(df: pandas.DataFrame):
    # Calculate the IQR.
    q1 = numpy.percentile(df["overall_score"], 25)
    q3 = numpy.percentile(df["overall_score"], 75)

    iqr = q3 - q1

    # Find the outliers.
    outliers_array = numpy.where(
        (df["overall_score"] < q1 - 1.5 * iqr) | (df["overall_score"] > q3 + 1.5 * iqr)
    )[0]

    df["is_iqr_outlier"] = df["observer_employee_number"].isin(
        df.loc[outliers_array]["observer_employee_number"].tolist()
    )

    return df


def get_pca(df: pandas.DataFrame):
    # set num of compenents
    pca = PCA(n_components=2)

    principal_components = pca.fit_transform(X=df[FIT_TRANSFORM_COLUMNS])

    pca_df = pandas.DataFrame(
        data=principal_components,
        columns=["pc1", "pc2"],
    )

    df = pandas.merge(left=df, right=pca_df, left_index=True, right_index=True)

    # percent of variance
    df["pc1_variance_explained"] = pca.explained_variance_ratio_[0]
    df["pc2_variance_explained"] = pca.explained_variance_ratio_[1]

    return df


def get_dbscan(df):
    # All time Outlier Detction Using PCA
    # 0.6 is the historic optimal epsilon, but we may need to adjust
    outlier_detection = DBSCAN(min_samples=3, eps=0.6)

    clusters = outlier_detection.fit_predict(X=df[["pc1", "pc2"]])

    cluster_df = pandas.DataFrame(data=clusters, columns=["cluster"])

    df = pandas.merge(left=df, right=cluster_df, left_index=True, right_index=True)

    return df


def get_isolation_forest(df: pandas.DataFrame):
    model = IsolationForest(contamination=0.1)  # assuming 10% of the data are outliers

    model.fit(X=df[FIT_TRANSFORM_COLUMNS])

    outliers = model.predict(X=df[FIT_TRANSFORM_COLUMNS])

    # tree_rename = {1: "core", -1: "outlier"}
    # tree_name = [tree_rename.get(n, n) for n in list(outliers)]

    tree_df = pandas.DataFrame(data=outliers, columns=["tree_outlier"])

    df = pandas.merge(left=df, right=tree_df, left_index=True, right_index=True)

    return df


# TODO: partition asset by year/term

# load data from extract view
df_global = pandas.read_csv("env/stg_people__manager_pm_score_averages.csv")

df_global.dropna(inplace=True)
df_global.reset_index(inplace=True)

# subset current year/term
df_current: pandas.DataFrame = df_global[
    (df_global["academic_year"] == df_global["academic_year"].max())
    & (df_global["term_num"] == df_global["term_num"].max())
]
df_current.reset_index(inplace=True)

# calculate outliers columns: all-time
df_global = get_iqr_outliers(df_global)
df_global = get_pca(df_global)
df_global = get_dbscan(df_global)
df_global = get_isolation_forest(df_global)

# calculate outliers columns: current term
df_current = get_iqr_outliers(df_current)
df_current = get_pca(df_current)
df_current = get_dbscan(df_current)
df_current = get_isolation_forest(df_current)

# merge all-time rows to matching current term rows
df_current = pandas.merge(
    left=df_current,
    right=df_global[
        [
            "observer_employee_number",
            "academic_year",
            "form_term",
            "cluster",
            "is_iqr_outlier",
            "pc1_variance_explained",
            "pc1",
            "pc2_variance_explained",
            "pc2",
            "tree_outlier",
        ]
    ],
    how="left",
    left_on=["observer_employee_number", "academic_year", "form_term"],
    right_on=["observer_employee_number", "academic_year", "form_term"],
    suffixes=["_current", "_global"],
)

# TODO: output as AVRO
