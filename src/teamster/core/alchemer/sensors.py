# SENSOR
# modified_on = pendulum.parse(text=s.get("modified_on"), tz=alchemer_timezone)
# bookmark = state.get(s.get("id"))
# if bookmark is not None:
#     start_datetime = pendulum.parse(bookmark, tz=alchemer_timezone)
# else:
#     start_datetime = pendulum.from_timestamp(0, tz=alchemer_timezone)
# start_str = start_datetime.format("YYYY-MM-DD HH:mm:ss Z")
# end_datetime = pendulum.now(tz=alchemer_timezone).subtract(hours=1)
# end_str = end_datetime.format("YYYY-MM-DD HH:mm:ss Z")
# ay_start_datetime = pendulum.datetime(
#     year=int(os.getenv("CURRENT_ACADEMIC_YEAR")), month=7, day=1, tz=alchemer_timezone
# )
# ay_start_str = ay_start_datetime.format("YYYY-MM-DD HH:mm:ss Z")
# # skip unmodified archived surveys that haven't been downloaded
# if s.get("status") == "Archived" and start_datetime > modified_on:
#     continue

# CURSOR
# state_file_path = data_dir / "state.json"
# if not state_file_path.exists():
#     state = {}
#     with state_file_path.open("a+") as f:
#         json.dump(state, f)
# else:
#     with state_file_path.open("r+") as f:
#         state = json.load(f)
# # update bookmark
# state[survey.id] = end_datetime.isoformat()
# print()
# # save state
# with state_file_path.open("r+") as f:
#     f.seek(0)
#     json.dump(state, f)
#     f.truncate()
