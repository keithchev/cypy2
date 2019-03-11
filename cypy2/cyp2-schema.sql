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

CREATE TYPE ACTIVITY_TYPE AS ENUM ('ride', 'run', 'walk', 'hike');
CREATE TYPE CYCLING_TYPE AS ENUM ('road', 'cross', 'indoor');
CREATE TYPE BIKE_NAME AS ENUM ('giant-defy-advanced', 'lynskey-cx');

CREATE TYPE DEVICE_MANUFACTURER AS ENUM ('garmin', 'wahoo');
CREATE TYPE DEVICE_MODEL AS ENUM (
    'fenix3', 
    'fr220',
    'edge520', 
    'elemnt'  -- nb the typo is correct
);


CREATE TABLE metadata (

    activity_id char(14),
    activity_type ACTIVITY_TYPE,

    filename varchar,
    file_date timestamp,
    strava_title varchar,
    strava_date timestamp,

    bike_name BIKE_NAME,
    cycling_type CYCLING_TYPE,

    device_model DEVICE_MODEL,
    device_manufacturer DEVICE_MANUFACTURER,

    power_meter_flag boolean,
    speed_sensor_flag boolean,
    heart_rate_monitor_flag boolean,
    
    PRIMARY KEY (activity_id)
);


-- each row here is the 'session' message from one FIT file
CREATE TABLE device_summary (

    activity_id char(14), 
    start_time timestamp,

    avg_cadence int,
    max_cadence int,

    avg_running_cadence int,  -- runs only
    max_running_cadence int,  -- runs only

    avg_heart_rate int,
    max_heart_rate int,

    avg_speed real,
    max_speed real,
    enhanced_avg_speed real,
    enhanced_max_speed real,

    -- rides with power only
    avg_power int,
    max_power int,
    normalized_power int,
    threshold_power int,
    intensity_factor real,
    training_stress_score real,
    
    total_ascent int,
    total_descent int,
    total_distance real,
    total_elapsed_time real,
    total_timer_time real,

    total_work int,     -- ride w power only
    total_calories int, -- surprisingly, exists for all activities
    total_strides int,  -- runs only

    PRIMARY KEY (activity_id),
    FOREIGN KEY (activity_id) REFERENCES metadata (activity_id)
);


CREATE TYPE EVENT_TYPE AS ENUM ('start', 'stop');

CREATE TABLE events (
    
    activity_id char(14),
    event_time timestamp,
    event_type EVENT_TYPE,

    PRIMARY KEY (event_time),
    FOREIGN KEY (activity_id) REFERENCES metadata (activity_id)
);


CREATE TABLE timepoints (

    activity_id char(14), 

    timepoint timestamp[],
    position_lat int[],        -- semicircles
    position_long int[],       -- semicircles
    distance real[],           -- meters
    altitude real[],           -- meters
    enhanced_altitude real[],  -- meters
    speed real[],              -- m/s
    enhanced_speed real[],     -- m/s

    power int[],              -- watts
    cadence int[],            -- rpm
    heart_rate int[],         -- bpm
    temperature int[],        -- degrees C

    grade real[],              -- percent
    gps_accuracy int[],        -- meters

    PRIMARY KEY (activity_id),
    FOREIGN KEY (activity_id) REFERENCES metadata (activity_id)
);



REVOKE ALL ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM postgres;
GRANT ALL ON SCHEMA public TO postgres;
GRANT ALL ON SCHEMA public TO PUBLIC;
