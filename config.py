SOURCE_DIR = "C:/Users/Joel/dev/python/BackupTool/testSource"
TARGET_DIR = "C:/Users/Joel/dev/python/BackupTool/testTarget"

EXCLUDE_PATHS = [
	"ignoredir/*",
	"*.png"
]

# save (not yet implemented), mirror , hardlinks (not yet implemented)
MODE = "save"

# This HAS to be true in Hardlink-Mode
VERSIONED = True

# Uses time.strftime
VERSION_NAME = "%d.%m.%y"

# only relevant when VERSIONED = True, will not use the directory writing to
# This HAS to be true in Hardlink-Mode
COMPARE_WITH_LAST_BACKUP = True

EXECUTE_ACTIONLIST = True
OPEN_ACTIONLIST = True
DELETE_ACTIONLIST = False

EXCLUDE_LOG_INFO = False
EXCLUDE_LOG_WARNING = False

# ordered list of possible elements "moddate", "size", "bytes", "md5" (not yet implemented)
COMPARE_METHOD = ["moddate", "size", "bytes"]
CACHE_TARGET_DATA = False

# both not implemented
MOVE_DETECTION = False