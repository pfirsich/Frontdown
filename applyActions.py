import os, sys

import json
import shutil
import logging

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

def executeActionList(actionData):
    logging.info("Apply actions.")

    sourceDirectory = actionData["sourceDirectory"]
    compareDirectory = actionData["compareDirectory"]
    targetDirectory = actionData["targetDirectory"]

    for action in actionData["actions"]:
        actionType = action["type"]
        params = action["params"]
        try:
            if actionType == "copy":
                fromPath = os.path.join(sourceDirectory, params["name"])
                toPath = os.path.join(targetDirectory, params["name"])
                logging.debug('copy from "' + fromPath + '" to "' + toPath + '"')
                toDirectory = os.path.dirname(toPath)
                if not os.path.isdir(toDirectory):
                    os.makedirs(toDirectory)
                shutil.copy2(fromPath, toPath)
            elif actionType == "delete":
                path = os.path.join(targetDirectory, params["name"])
                logging.debug('delete file "' + path + '"')
                os.remove(path)
            elif actionType == "hardlink":
                fromPath = os.path.join(compareDirectory, params["name"])
                toPath = os.path.join(targetDirectory, params["name"])
                logging.debug('hardlink from "' + fromPath + '" to "' + toPath + '"')
                toDirectory = os.path.dirname(toPath)
                if not os.path.isdir(toDirectory):
                    os.makedirs(toDirectory)
                hardlink(fromPath, toPath)
        except OSError as e:
            logging.exception(e)
        except IOError as e:
            logging.exception(e)

    # TODO: Set successful

if __name__ == '__main__':
    if len(sys.argv) < 2:
        quit("Please specify an actions file.")

    logging.info("Apply action file " + sys.argv[1])

    with open(sys.argv[1]) as actionFile:
        actionData = json.loads(actionFile.read())

    executeActionList(actionData)

