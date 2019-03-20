--
-- Running/cycling activity database
--
--
-- Usage
-- -----
-- psql -f cypy-schema.sql -v dbname="dbname"
--
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
    'elemnt'  -- nb the typo is correct -_-
);


CREATE TABLE metadata (

    activity_id char(14) PRIMARY KEY,
    activity_type ACTIVITY_TYPE,

    filename varchar,
    file_date timestamp,
    strava_title varchar,
    strava_date timestamp,

    cycling_type CYCLING_TYPE,
    bike_name BIKE_NAME,

    device_model DEVICE_MODEL,
    device_manufacturer DEVICE_MANUFACTURER,

    -- flags for the presence of a power meter, speed sensor, or HRM
    power_flag boolean,
    speed_flag boolean,
    heart_rate_flag boolean
);


-- column names here are mostly copied from the 'session' message type
CREATE TABLE raw_summary (

    activity_id char(14) PRIMARY KEY,
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

    total_work int,     -- ride with power only
    total_calories int, -- surprisingly, exists for all activities
    total_strides int,  -- runs only

    FOREIGN KEY (activity_id) REFERENCES metadata (activity_id)
);


CREATE TYPE RAW_EVENT_TYPE AS ENUM ('start', 'stop');

CREATE TABLE raw_events (

    event_time timestamp PRIMARY KEY,
    event_type RAW_EVENT_TYPE,
    activity_id char(14),

    FOREIGN KEY (activity_id) REFERENCES metadata (activity_id)
);



CREATE TABLE raw_records (

    activity_id char(14) PRIMARY KEY, 

    timepoint timestamp[],
    position_lat int[],        -- semicircles
    position_long int[],       -- semicircles
    distance real[],           -- meters

    altitude real[],           -- meters
    enhanced_altitude real[],  -- meters
    speed real[],              -- m/s
    enhanced_speed real[],     -- m/s

    power int[],               -- watts
    cadence int[],             -- rpm
    heart_rate int[],          -- bpm
    temperature int[],         -- degrees C

    grade real[],              -- percent
    gps_accuracy int[],        -- meters

    FOREIGN KEY (activity_id) REFERENCES metadata (activity_id)
);


CREATE TABLE proc_records (

    activity_id char(14), 

    date_created timestamptz  DEFAULT now(),
    date_modified timestamptz DEFAULT NULL,

    -- cypy2 commit that created the row  
    commit_hash char(40)      NOT NULL,

    -- elapsed time in seconds
    elapsed_time int[],
    lat real[],                -- decimal degrees 
    lon real[],                -- decimal degrees

    distance real[],        -- meters
    altitude real[],        -- meters
    grade real[],           -- percent
    speed real[],           -- m/s
    vam real[],             -- m/h

    power int[],           -- watts
    cadence int[],         -- rpm
    heart_rate int[],      -- bpm

    pause_mask boolean[],  -- true when paused, false when not
    climb_mask boolean[],  -- true when climbing, false when not (rides only)

    PRIMARY KEY (activity_id, date_created),
    FOREIGN KEY (activity_id) REFERENCES metadata (activity_id)
);


CREATE FUNCTION update_date_modified() RETURNS trigger AS $$
BEGIN
    NEW.date_modified = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- note that 'EXECUTE FUNCTION' here doesn't work
CREATE TRIGGER proc_records_date_modified BEFORE UPDATE ON proc_records
FOR EACH ROW EXECUTE PROCEDURE update_date_modified();


REVOKE ALL ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM postgres;
GRANT ALL ON SCHEMA public TO postgres;
GRANT ALL ON SCHEMA public TO PUBLIC;
