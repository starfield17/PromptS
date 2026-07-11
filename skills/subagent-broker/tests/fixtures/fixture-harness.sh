#!/usr/bin/env sh
set -eu
printf '%s\n' '{"type":"system","subtype":"init","provider":"fixture","model":"fixture-1"}'
printf '%s\n' '{"type":"result","subtype":"success","is_error":false,"result":"fixture smoke ok","provider":"fixture","model":"fixture-1"}'
