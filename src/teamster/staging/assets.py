import os

from dagster import AssetExecutionContext, asset


@asset
def onepassword_secret_test(context: AssetExecutionContext):
    context.log.info(msg=os.getenv("ONEPASSWORD_ITEM_TEST_1_USERNAME"))
    context.log.info(msg=os.getenv("ONEPASSWORD_ITEM_TEST_1_PASSWORD"))
    context.log.info(msg=os.getenv("ONEPASSWORD_ITEM_TEST_2_USERNAME"))
    context.log.info(msg=os.getenv("ONEPASSWORD_ITEM_TEST_2_PASSWORD"))
