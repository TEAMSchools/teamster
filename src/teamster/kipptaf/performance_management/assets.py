#!/usr/bin/env python
# coding: utf-8

# ## Initial Data Load + Exploration

# In[1]:


import numpy as np
import pandas as pd
import scipy.stats as stats
from sklearn.cluster import DBSCAN
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest


def current_term(df):
    max_academic_year = df["academic_year"].max()
    df_current_year = df[df["academic_year"] == max_academic_year]
    max_term = df["term_num"].max()
    df_current_term = df_current_year[df_current_year["term_num"] == max_term]
    df_current_term = df_current_term.reset_index()
    return df_current_term


df_current_term = current_term(df)


# IQR
def get_iqr_outliers(df):
    # Calculate the IQR.
    q1 = np.percentile(df["overall_score"], 25)
    q3 = np.percentile(df["overall_score"], 75)
    iqr = q3 - q1

    # Find the outliers.
    outliers = np.where(
        (df["overall_score"] < q1 - 1.5 * iqr) | (df["overall_score"] > q3 + 1.5 * iqr)
    )[0]
    df_iqr_outliers = df.loc[outliers]
    outliers = df_iqr_outliers["observer_employee_number"].tolist()
    return outliers


# PCA
def get_pca(df):
    # isolate fields
    df_num = df.drop(
        [
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
    principalComponents = pca.fit_transform(df_num)
    principaldf = pd.DataFrame(
        data=principalComponents,
        columns=["principal component 1", "principal component 2"],
    )
    # get loadings
    loadings_alltime = pca.components_
    # percent of variance
    df["PC1_variance_explained"] = pca.explained_variance_ratio_[0]
    df["PC2_variance_explained"] = pca.explained_variance_ratio_[1]
    return principaldf


# DBSCAN
def get_dbscan(principaldf):
    min_samples = 3
    # All time Outlier Detction Using PCA
    outlier_detection = DBSCAN(
        min_samples=min_samples, eps=0.6
    )  # 0.6 is the historic optimal epsilon, but we may need to adjust
    clusters = outlier_detection.fit_predict(principaldf)
    print(list(clusters))
    cluster_rename = {0: "Core", 1: "Boundary", -1: "Outlier"}
    cluster_name = [cluster_rename.get(n, n) for n in list(clusters)]

    clusterdf = pd.DataFrame(list(cluster_name), columns=["Clusters"])

    finaldf = pd.concat([principaldf, clusterdf[["Clusters"]]], axis=1)
    finaldf["Clusters"] = finaldf["Clusters"].apply(str)

    return finaldf


# Isolation Forest
def get_isolation_forest(df):
    # isolate fields
    df_num = df.drop(
        [
            "observer_employee_number",
            "overall_score",
            "iqr_outliers",
            "academic_year",
            "form_term",
            "term_num",
            "Clusters",
            "PC1_variance_explained",
            "PC2_variance_explained",
            "principal component 1",
            "principal component 2",
        ],
        axis=1,
    )
    model = IsolationForest(contamination=0.1)  # assuming 10% of the data are outliers
    model.fit(df_num)
    outliers = model.predict(df_num)
    tree_rename = {1: "Core", -1: "Outlier"}
    tree_name = [tree_rename.get(n, n) for n in list(outliers)]
    treedf = pd.DataFrame(list(tree_name), columns=["Tree_Outliers"])
    df = pd.concat([df, treedf[["Tree_Outliers"]]], axis=1)
    return df


# replace this block with a connection to teamster, the data here is just a sample
df = pd.read_csv(
    "src_dbt_kipptaf_models_people_staging_stg_people__manager_pm_score_averages.csv"
)
# df['primary_site_schoolid'] = df['primary_site_schoolid'].apply(str)
# df['observer_id'] = df['observer_id'].apply(str)
df = df.dropna()
df = df.reset_index()
df = df.drop(["index"], axis=1)

# all time IQR outliers
outliers = get_iqr_outliers(df)
df["iqr_outliers"] = df["observer_employee_number"].isin(outliers)
df["iqr_outliers"] = df["iqr_outliers"].replace({True: "Outlier", False: "Core"})

# current term IQR outliers
outliers = get_iqr_outliers(df_current_term)
df_current_term["iqr_outliers"] = df_current_term["observer_employee_number"].isin(
    outliers
)
df_current_term["iqr_outliers"] = df_current_term["iqr_outliers"].replace(
    {True: "Outlier", False: "Core"}
)

principaldf = get_pca(df)
df = pd.merge(df, principaldf, left_index=True, right_index=True, how="left")
finaldf = get_dbscan(principaldf)
df = pd.concat([df, finaldf[["Clusters"]]], axis=1)

principaldf = get_pca(df_current_term)
df_current_term = pd.merge(
    df_current_term, principaldf, left_index=True, right_index=True, how="left"
)
finaldf = get_dbscan(principaldf)
df_current_term = pd.concat([df_current_term, finaldf[["Clusters"]]], axis=1)

df = get_isolation_forest(df)
df_current_term = get_isolation_forest(df_current_term)

df_current_term.rename(
    columns={
        "iqr_outliers": "iqr_outliers_current_term",
        "Clusters": "dbscan_clusters_current_term",
        "Tree_Outliers": "tree_Outliers_current_term",
        "index": "index_old",
    },
    inplace=True,
)

df_current_term = pd.merge(
    df_current_term, df, left_on="index_old", right_index=True, how="left"
)

df_current_term.rename(
    columns={
        "iqr_outliers": "iqr_outliers_all_time",
        "Clusters": "dbscan_clusters_all_time",
        "Tree_Outliers": "tree_Outliers_all_time",
    },
    inplace=True,
)

# combine all
# Create a new column that counts the number of 'Outlier' values in each row.
df_current_term["Outlier Count"] = (
    df_current_term["iqr_outliers_current_term"].str.count("Outlier")
    + df_current_term["dbscan_clusters_current_term"].str.count("Outlier")
    + df_current_term["tree_Outliers_current_term"].str.count("Outlier")
    + df_current_term["iqr_outliers_all_time"].str.count("Outlier")
    + df_current_term["dbscan_clusters_all_time"].str.count("Outlier")
    + df_current_term["tree_Outliers_all_time"].str.count("Outlier")
)

# Create a new column that maps the Outlier Count column to the values 1, 2, or 3.
df_current_term["Outlier Value"] = df_current_term["Outlier Count"].map(
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
df_current_term
