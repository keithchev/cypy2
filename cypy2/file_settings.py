'''
Here we explicitly list the fields to aggregate for the following message types:

event:    timer start/stop events (both manual and auto-pauses)
session:  summary statistics for the session (always one per activity)
record:   time-series data

'''

field_names = {}


# -----------------------------------------------------------------------------
#
# 'event'
# note: only events where event=='timer' are useful to identify pauses
#
#  -----------------------------------------------------------------------------
field_names['event'] = [
    'timestamp',
    'event',           # 'timer', 'session', 'off_course', 'power_down/up', 'recovery_hr'
    'event_type',      # 'start', 'stop', 'stop_all', 'stop_disable_all', 'marker'
    'timer_trigger',   # 'manual', 'auto', None
]


# -----------------------------------------------------------------------------
#
# 'record'
#
# all of these fields appear in *ride* data from both Garmin and Wahoo,
# except for 'grade' and 'gps_accuracy' (which are Wahoo-specific)
#
# all fields except for 'power' and 'temperature' also appear in runs;
# no fields are run-specific
#
#  ----------------------------------------------------------------------------- 
field_names['record'] = [
    
    'timestamp',
    'position_lat',       # semicircles
    'position_long',      # semicircles
    'distance',           # meters
    'altitude',           # meters
    'enhanced_altitude',  # meters
    'speed',              # m/s
    'enhanced_speed',     # m/s

    'cadence',            # rpm
    'heart_rate',         # bpm
    'power',              # watts
    'temperature',        # degrees C

    # Wahoo only
    'gps_accuracy',       # meters
    'grade',              # percent
]


# -----------------------------------------------------------------------------
#
# 'session'
#
# these fields, except where noted, appear in all activities 
# (runs from fr220 and fenix3, and rides from fr220, edge520, and wahoo elemnt)
# 
# note that several fields are specific to rides with power, 
# and there are three run-specific fields.
#
#  ----------------------------------------------------------------------------- 
field_names['session'] = [
    
    'start_time',

    'avg_cadence',
    'max_cadence',

    'avg_running_cadence',  # runs only
    'max_running_cadence',  # runs only

    'avg_heart_rate',
    'max_heart_rate',

    'avg_speed',
    'max_speed',
    'enhanced_avg_speed',
    'enhanced_max_speed',

    # rides with power only
    'avg_power',
    'max_power',
    'normalized_power',
    'threshold_power',
    'intensity_factor',
    'training_stress_score',
    
    'total_ascent',
    'total_descent',
    'total_distance',
    'total_elapsed_time',
    'total_timer_time',

    'total_work',            # rides with power only
    'total_calories',        # surprisingly, rides wo power and runs have this field
    'total_strides',         # runs only

]

