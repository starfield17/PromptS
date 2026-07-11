#!/usr/bin/env sh
set -eu
printf '%s\n' 'patch fixture' > smoke-created.txt
printf '%s\n' '{"type":"system","subtype":"init","provider":"fixture","model":"fixture-1"}'
printf '%s\n' '{"type":"result","subtype":"success","is_error":false,"result":"patch fixture ok","provider":"fixture","model":"fixture-1"}'
