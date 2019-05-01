--
-- Script to drop and create a new postGIS database
--
--
-- Usage
-- -----
-- psql -f create_db.sql -v dbname="dbname"
--
-- Keith Cheveralls
-- Feb 2019
--

-- disallow new connections
UPDATE pg_database SET datallowconn = 'false' 
WHERE datname = :'dbname';

-- force drop any existing connections
SELECT pg_terminate_backend(pid) FROM pg_stat_activity 
WHERE datname = :'dbname';

-- drop the database
DROP DATABASE IF EXISTS :dbname;

CREATE DATABASE :dbname 
    WITH 
    OWNER = keith
    TEMPLATE = template0 
    ENCODING = 'UTF8' 
    LC_COLLATE = 'en_US.UTF-8' 
    LC_CTYPE = 'en_US.UTF-8';

\connect :dbname

SET search_path = public, pg_catalog;
SET default_tablespace = '';

CREATE EXTENSION postgis;
CREATE EXTENSION postgis_topology;