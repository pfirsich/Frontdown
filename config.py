SOURCE_DIR = "C:/Users/Joel/dev/python/BackupTool/testSource"
TARGET_DIR = "C:/Users/Joel/dev/python/BackupTool/testTarget"

EXCLUDE_PATHS = [
	"ignoredir/*",
	"*.png"
]

# save, mirror, hardlinks
MODE = "hardlink"

# In hardlink mode this is True automatically
VERSIONED = True

# Uses time.strftime
VERSION_NAME = "%d.%m.%y"

# only relevant when VERSIONED = True, will not use the directory writing to
# In hardlink mode this is True automatically
COMPARE_WITH_LAST_BACKUP = True

EXECUTE_ACTIONLIST = True
OPEN_ACTIONLIST = True
DELETE_ACTIONLIST = False

# ordered list of possible elements "moddate", "size", "bytes", "md5" (not yet implemented)
COMPARE_METHOD = ["moddate", "size", "bytes"]

# Caching not yet implemented
CACHE_TARGET_DATA = False

# Move detection not yet implemented. And I probably never will, since the gain is very small and sometimes even non-existent if the moved files are big enough
MOVE_DETECTION = False

# Log level, possible options: "ERROR", "WARNING", "INFO", "DEBUG"
LOG_LEVEL = "INFO"
