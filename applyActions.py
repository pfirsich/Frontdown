import os, sys

import json
import shutil

# From here: https://github.com/sid0/ntfs/blob/master/ntfsutils/hardlink.py
import ctypes
from ctypes import WinError
from ctypes.wintypes import BOOL
CreateHardLink = ctypes.windll.kernel32.CreateHardLinkW
CreateHardLink.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_void_p]
CreateHardLink.restype = BOOL

def hardlink(source, link_name):
    res = CreateHardLink(link_name, source, None)
    if res == 0:
        raise WinError()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        quit("Please specify an actions file.")

    print("Apply", sys.argv[1])
    
    with open(sys.argv[1]) as inFile:
        actionData = json.loads(inFile.read())
    sourceDirectory = actionData["sourceDirectory"]
    compareDirectory = actionData["compareDirectory"]
    targetDirectory = actionData["targetDirectory"]

    debug = True
    for action in actionData["actions"]:
        actionType = action["type"]
        params = action["params"]
        try:
            if actionType == "copy":
                fromPath = os.path.join(sourceDirectory, params["name"])
                toPath = os.path.join(targetDirectory, params["name"])
                if debug: print('copy from "' + fromPath + '" to "' + toPath + '"')
                shutil.copy2(fromPath, toPath)
            elif actionType == "delete":
                path = os.path.join(targetDirectory, params["name"])
                if debug: print('delete file "' + path + '"')
                os.remove(path)
            elif actionType == "hardlink":
                fromPath = os.path.join(compareDirectory, params["name"])
                toPath = os.path.join(targetDirectory, params["name"])
                if debug: print('hardlink from "' + fromPath + '" to "' + toPath + '"')
                hardlink(fromPath, toPath)
        except OSError as e:
            print(e)
        except IOError as e:
            print(e)
