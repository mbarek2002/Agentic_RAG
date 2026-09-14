#!/bin/bash
set -e

# Initialize Airflow database
echo "Initializing Airflow database..."
airflow db init

# Create admin user with admin/admin credentials
echo "Creating admin user..."
airflow users create \
    --username admin \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email admin@example.com \
    --password admin || echo "Admin user already exists"

# Start webserver and scheduler in the foreground (no --daemon, no pidfile).
# A container restart always starts both from a clean process state, so there
# is nothing stale to clean up and nothing that can conflict with a leftover
# "already running" pidfile check.
echo "Starting Airflow webserver and scheduler..."
airflow webserver --port 8080 &
WEBSERVER_PID=$!
airflow scheduler &
SCHEDULER_PID=$!

trap 'kill -TERM "$WEBSERVER_PID" "$SCHEDULER_PID" 2>/dev/null' TERM INT

# If either process dies, exit so Docker can restart the container cleanly
# instead of limping along with only the scheduler or only the webserver up.
wait -n "$WEBSERVER_PID" "$SCHEDULER_PID"
exit $?
