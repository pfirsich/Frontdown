import os, sys

import json
import shutil

if __name__ == '__main__':
    if len(sys.argv) < 2:
        quit("Please specify an actions file.")

    print("Apply", sys.argv[1])
    
    with open(sys.argv[1]) as inFile:
        actionData = json.loads(inFile.read())
    sourceDirectory = actionData["sourceDirectory"]
    compareDirectory = actionData["compareDirectory"]
    targetDirectory = actionData["targetDirectory"]

    for action in actionData["actions"]:
        actionType = action["type"]
        params = action["params"]
        if actionType == "copy":
            fromPath = os.path.join(sourceDirectory, params["name"])
            toPath = os.path.join(targetDirectory, params["name"])
            print("copy", fromPath, "to", toPath)
            shutil.copy2(fromPath, toPath)
        elif actionType == "delete":
            path = os.path.join(targetDirectory, params["name"])
            print("delete", path)
            os.remove(path)

#mklink /H "./testSource/vlc_gamecube.txt" "../2016-01-24/testSource/vlc_gamecube.txt"