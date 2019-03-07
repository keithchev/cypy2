--
-- Running/cycling activity database


-- Tables
-- ------
--

-- Usage
-- -----
-- psql -f cypy-schema.sql -v dbname="dbname"

-- Keith Cheveralls
-- Feb 2019
--

-- \set dbname 'cypy2'

---------------------------------------------------------------------------------------------------
--
-- disallow new connections
UPDATE pg_database SET datallowconn = 'false' WHERE datname = :'dbname';

-- force drop any existing connections
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :'dbname';

-- drop the database
DROP DATABASE IF EXISTS :dbname;
--
---------------------------------------------------------------------------------------------------


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

-- from Strava metadata
CREATE TYPE ACTIVITY_TYPE AS ENUM ('ride', 'run', 'walk', 'hike');

-- 'indoor' from FIT file's sub_sport field; 'cross' must be manually labeled
CREATE TYPE CYCLING_TYPE AS ENUM ('road', 'cross', 'indoor');

-- from Strava metadata
CREATE TYPE BIKE_NAME AS ENUM ('giant-defy-advanced', 'lynskey-cx');

CREATE TYPE DEVICE_MODEL AS ENUM (
    'garmin-fenix-3', 
    'garmin-forerunner-220'
    'garmin-edge-520', 
    'wahoo-elemnt-bolt', 
);

-- 'internal' indicates the use of the Fenix 3's built-in HRM
CREATE TYPE HRM_TYPE AS ENUM ('external', 'internal');


CREATE TABLE metadata (
    -- activity_id is timestamp in ymdHMS format
    activity_id char(14),

    fitfilename varchar,
    strava_title varchar,
    strava_date timestamp,
    activity_type ACTIVITY_TYPE,
    cycling_type CYCLING_TYPE,
    bike_name BIKE_NAME,

    -- these columns are inferred from the 'device_info' message
    device_model DEVICE_MODEL,
    power_meter_flag boolean,
    speed_sensor_flag boolean,
    heart_rate_monitor_flag boolean,
    heart_rate_monitor_type HRM_TYPE
    
    PRIMARY KEY (activity_id)
);


-- each row here is the 'session' message from one FIT file
CREATE TABLE device_summary (
    activity_id char(14), 
    PRIMARY KEY (activity_id),
    FOREIGN KEY (activity_id) REFERENCES metadata (activity_id)
);


CREATE TABLE device_events (

    PRIMARY KEY (),
    FOREIGN KEY (activity_id) REFERENCES metadata (activity_id)
);


CREATE TABLE records (

    PRIMARY KEY (),
    FOREIGN KEY (activity_id) REFERENCES metadata (activity_id)
);



REVOKE ALL ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM postgres;
GRANT ALL ON SCHEMA public TO postgres;
GRANT ALL ON SCHEMA public TO PUBLIC;
