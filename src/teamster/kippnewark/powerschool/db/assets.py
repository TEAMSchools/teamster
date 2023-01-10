from teamster.core.powerschool.db.assets import hourly_partition, table_asset_factory

# local_ps_db_assets = []

# whenmodified
for table_name in [
    "s_nj_crs_x",
    "s_nj_ren_x",
    "s_nj_stu_x",
    "s_nj_usr_x",
    "u_clg_et_stu",
    "u_clg_et_stu_alt",
    "u_def_ext_students",
    "u_studentsuserfields",
]:
    # local_ps_db_assets.append(
    table_asset_factory(
        table_name=table_name,
        where={"column": "whenmodified"},
        partitions_def=hourly_partition,
    )
# )
