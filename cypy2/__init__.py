
import sys

try:
    import dbutils
except ModuleNotFoundError:
    sys.path.append('/home/keith/Dropbox/projects-gh/dbutils/')
    import dbutils

from cypy2 import (
	strava,
	utils,
	file_utils,
	file_settings,
)

from cypy2.managers import ActivityManager
from cypy2.activity import (Activity, LocalActivity)