import logging

GCS_PROJECT_NAME = "teamster-332318"

# Paramiko's Transport.run() background thread logs socket.error at ERROR
# before the exception propagates to SSHResource.get_connection()'s tenacity
# retry. The retry then recovers, but GCP Error Reporting has already filed a
# group. Silence the redundant ERROR; genuine unrecovered failures still log
# at the Dagster run level.
logging.getLogger("paramiko.transport").setLevel(logging.WARNING)
