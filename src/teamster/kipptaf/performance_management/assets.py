import numpy
import pandas
from sklearn.cluster import DBSCAN
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest


def current_term(df: pandas.DataFrame):
    df_current_year = df[df["academic_year"] == df["academic_year"].max()]

    df_current_term: pandas.DataFrame = df_current_year[
        df_current_year["term_num"] == df["term_num"].max()
    ]

    df_current_term.reset_index(inplace=True)

    return df_current_term


# IQR
def get_iqr_outliers(df: pandas.DataFrame):
    # Calculate the IQR.
    q1 = numpy.percentile(df["overall_score"], 25)
    q3 = numpy.percentile(df["overall_score"], 75)

    iqr = q3 - q1

    # Find the outliers.
    outliers = numpy.where(
        (df["overall_score"] < q1 - 1.5 * iqr) | (df["overall_score"] > q3 + 1.5 * iqr)
    )[0]

    outliers = df.loc[outliers]["observer_employee_number"].tolist()

    return outliers


# PCA
def get_pca(df: pandas.DataFrame):
    # isolate fields
    df_num = df.drop(
        labels=[
            "observer_employee_number",
            "overall_score",
            "iqr_outliers",
            "academic_year",
            "form_term",
            "term_num",
        ],
        axis=1,
    )

    # set num of compenents
    pca = PCA(n_components=2)

    principal_components = pca.fit_transform(X=df_num)

    principal_df = pandas.DataFrame(
        data=principal_components,
        columns=["principal_component_1", "principal_component_2"],
    )

    # percent of variance
    df["pc1_variance_explained"] = pca.explained_variance_ratio_[0]
    df["pc2_variance_explained"] = pca.explained_variance_ratio_[1]

    return principal_df


# DBSCAN
def get_dbscan(principal_df):
    # All time Outlier Detction Using PCA
    # 0.6 is the historic optimal epsilon, but we may need to adjust
    outlier_detection = DBSCAN(min_samples=3, eps=0.6)

    clusters = outlier_detection.fit_predict(X=principal_df)
    # print(list(clusters))

    cluster_rename = {0: "core", 1: "boundary", -1: "outlier"}

    cluster_name = [cluster_rename.get(n, n) for n in list(clusters)]

    cluster_df = pandas.DataFrame(data=list(cluster_name), columns=["clusters"])

    final_df = pandas.concat(objs=[principal_df, cluster_df[["clusters"]]], axis=1)

    final_df["clusters"] = final_df["clusters"].apply(func=str)

    return final_df


# Isolation Forest
def get_isolation_forest(df: pandas.DataFrame):
    # isolate fields
    df_num = df.drop(
        labels=[
            "observer_employee_number",
            "overall_score",
            "iqr_outliers",
            "academic_year",
            "form_term",
            "term_num",
            "clusters",
            "pc1_variance_explained",
            "pc2_variance_explained",
            "principal_component_1",
            "principal_component_2",
        ],
        axis=1,
    )

    model = IsolationForest(contamination=0.1)  # assuming 10% of the data are outliers

    model.fit(X=df_num)
    outliers = model.predict(X=df_num)

    tree_rename = {1: "core", -1: "outlier"}
    tree_name = [tree_rename.get(n, n) for n in list(outliers)]

    tree_df = pandas.DataFrame(data=list(tree_name), columns=["tree_outliers"])

    df = pandas.concat(objs=[df, tree_df[["tree_outliers"]]], axis=1)

    return df


# replace this block with a connection to teamster, the data here is just a sample
df = pandas.read_csv(
    "src_dbt_kipptaf_models_people_staging_stg_people__manager_pm_score_averages.csv"
)

# df['primary_site_schoolid'] = df['primary_site_schoolid'].apply(str)
# df['observer_id'] = df['observer_id'].apply(str)
df.dropna(inplace=True)
df.reset_index(inplace=True)
df.drop(labels=["index"], axis=1, inplace=True)

df_current_term = current_term(df)

# all time IQR outliers
outliers = get_iqr_outliers(df)

df["iqr_outliers"] = df["observer_employee_number"].isin(outliers)
df["iqr_outliers"] = df["iqr_outliers"].replace({True: "outlier", False: "core"})

# current term IQR outliers
outliers = get_iqr_outliers(df_current_term)

df_current_term["iqr_outliers"] = df_current_term["observer_employee_number"].isin(
    outliers
)
df_current_term["iqr_outliers"] = df_current_term["iqr_outliers"].replace(
    {True: "outlier", False: "core"}
)

principal_df = get_pca(df)

df = pandas.merge(
    left=df, right=principal_df, left_index=True, right_index=True, how="left"
)

final_df = get_dbscan(principal_df)

df = pandas.concat(objs=[df, final_df[["clusters"]]], axis=1)

principal_df = get_pca(df_current_term)

df_current_term = pandas.merge(
    left=df_current_term,
    right=principal_df,
    left_index=True,
    right_index=True,
    how="left",
)

final_df = get_dbscan(principal_df)

df_current_term = pandas.concat(objs=[df_current_term, final_df[["clusters"]]], axis=1)

df = get_isolation_forest(df)

df_current_term = get_isolation_forest(df_current_term)

df_current_term.rename(
    columns={
        "iqr_outliers": "iqr_outliers_current_term",
        "clusters": "dbscan_clusters_current_term",
        "tree_outliers": "tree_Outliers_current_term",
        "index": "index_old",
    },
    inplace=True,
)

df_current_term = pandas.merge(
    left=df_current_term, right=df, left_on="index_old", right_index=True, how="left"
)

df_current_term.rename(
    columns={
        "iqr_outliers": "iqr_outliers_all_time",
        "clusters": "dbscan_clusters_all_time",
        "tree_outliers": "tree_outliers_all_time",
    },
    inplace=True,
)

# combine all
# Create a new column that counts the number of 'Outlier' values in each row.
df_current_term["outlier_count"] = (
    df_current_term["iqr_outliers_current_term"].str.count("outlier")
    + df_current_term["dbscan_clusters_current_term"].str.count("outlier")
    + df_current_term["tree_outliers_current_term"].str.count("outlier")
    + df_current_term["iqr_outliers_all_time"].str.count("outlier")
    + df_current_term["dbscan_clusters_all_time"].str.count("outlier")
    + df_current_term["tree_outliers_all_time"].str.count("outlier")
)

# Create a new column that maps the outlier_count column to the values 1, 2, or 3.
df_current_term["outlier_value"] = df_current_term["outlier_count"].map(
    {
        0: "Not an Outlier",
        1: "One Outlier",
        2: "Two Outliers",
        3: "Three Outliers",
        4: "Four Outliers",
        5: "Five Outliers",
        6: "Six Outliers",
    }
)

df_current_term.drop("index_old", axis=1, inplace=True)

# Save this data frame as a table:
# df_current_term
