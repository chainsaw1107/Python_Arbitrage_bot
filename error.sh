#!/bin/bash

# Get the current date and time
error_time=$(date)
job_name=$JOB_NAME

# Multiline message using warning emojis and the error message
msg=$(cat <<EOF
🚫⛔⚠️🚫⛔⚠️🚫⛔⚠️🚫⛔⚠️️🚫⛔⚠️
    Job Name: $job_name
    Error Time: $error_time
    Hard exit. Please check the logs.
🚫⛔⚠️🚫⛔⚠️🚫⛔⚠️🚫⛔⚠️️🚫⛔⚠️
EOF
)

# Send the message using curl
curl -X POST -d "$msg" https://ntfy.rae.cloud/errors
