-- Create the test database alongside the dev database.
-- This script runs automatically on first container start
-- (via /docker-entrypoint-initdb.d/).
CREATE DATABASE releasedb_test OWNER releasedb;
