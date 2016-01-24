import os, sys

import fnmatch
import filecmp
import importlib, importlib.util
import json
import subprocess
import time

class File:
    def __init__(self, path, source, target = False):
        self.path = path 
        self.source = source 
        self.target = target

    def __str__(self):
        inStr = []
        if self.source:
            inStr.append("source")
        if self.target:
            inStr.append("target")
        return self.path + " (" + ",".join(inStr) + ")"

class Action:
    # Possible actions:
    # copy (always from source to target),
    # delete (always in target)
    # hardlink (always from compare directory to target directory)
    # rename (always in target) (2-variate)
    # hardlink2 (alway from compare directory to target directory) (2-variate)

    def __init__(self, actionType, **kwargs):
        self.type = actionType
        self.params = kwargs

    def asDict(self):
        return {'type': self.type, 'params': self.params}

    def __str__(self):
        return json.dumps(self.asDict())

def filesEqual(a, b):
    aStat = os.stat(a)
    bStat = os.stat(b)

    equal = True
    for method in config.COMPARE_METHOD:
        if method == "moddate":
            if aStat.st_mtime != bStat.st_mtime:
                break
        elif method == "size":
            if aStat.st_size != bStat.st_size:
                break
        elif method == "bytes":
            if not filecmp.filecmp(a, b, shallow = False):
                break
    else:
        return True 

    return False

def log(msgType, msg):
    prefixes = {'critical': 'CRT', 'error': "ERR", 'warning': "WRN", 'information': "NFO"}
    line = prefixes[msgType] + " - " + msg
    print(line)
    if logFile != None:
        with open(logFile, "a") as outFile:
            outFile.write(line + "\n")
    if msgType == "critical":
        quit()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        quit("Please specify the configuration file for your backup.")

    # from here: http://stackoverflow.com/questions/67631/how-to-import-a-module-given-the-full-path
    spec = importlib.util.spec_from_file_location("config", sys.argv[1])
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)

    # Setup directories
    logFile = None
    targetDirectory = config.TARGET_DIR
    compareDirectory = targetDirectory
    if config.VERSIONED or config.MODE == "hardlink":
        targetDirectory = os.path.join(config.TARGET_DIR, time.strftime(config.VERSION_NAME), os.path.basename(config.SOURCE_DIR))
        compareDirectory = targetDirectory

        oldBackups = []
        if config.COMPARE_WITH_LAST_BACKUP or config.MODE == "hardlink":
            for entry in os.scandir(config.TARGET_DIR):
                if entry.is_dir():
                    try:
                        creationTime = time.strptime(entry.name, config.VERSION_NAME)
                    except:
                        continue
                    oldBackups.append({'time': creationTime, 'path': entry.name})

            if len(oldBackups) > 0:
                newestBackup = max(oldBackups, key = lambda x: x['time'])
                compareDirectory = os.path.join(config.TARGET_DIR, newestBackup['path'], os.path.basename(config.SOURCE_DIR))

        try:
            os.makedirs(targetDirectory)
        except FileExistsError as e:
            # TODO: Pick a new name that is unique (append "#2" or "#n" or something) and throw a warning
            log("critical", "Target Backup directory '" + targetDirectory + "' already exists. Aborting.")

    logFile = os.path.join(targetDirectory, "..", "log.txt")

    # Build a list of all files in source and target
    # TODO: A sorted list of some kind would probably be the best data structure
    fileSet = []
    for root, dirs, files in os.walk(config.SOURCE_DIR):
        relRoot = os.path.relpath(root, config.SOURCE_DIR)
        for name in files:
            fullName = os.path.normpath(os.path.join(relRoot, name))
            for exlude in config.EXCLUDE_PATHS:
                if fnmatch.fnmatch(fullName, exlude):
                    break
            else:
                fileSet.append(File(fullName, True))

    for root, dirs, files in os.walk(compareDirectory):
        relRoot = os.path.relpath(root, compareDirectory)
        for name in files:
            fullName = os.path.normpath(os.path.join(relRoot, name))
            for element in fileSet:
                if element.path == fullName:
                    element.target = True
                    break
            else:
                fileSet.append(File(fullName, True))

    for e in fileSet:
        print(e)

    # Determine what to do with these files
    actions = []

    # ============== SAVE
    # Write all files that are in source, but are not already existing in target (in that version)
    # source\target: copy
    # source&target: 
    #   same: ignore
    #   different: copy
    # target\source: ignore

    # --- move detection:
    # The same, except if files in source\target and target\source are equal, don't copy, 
    # but rather rename target\source (old backup) to source\target (new backup)

    # ============== MIRROR
    # End up with a complete copy of source in target
    # source\target: copy
    # source&target:
    #   same: ignore
    #   different: copy
    # target\source: delete

    # --- move detection:
    # The same, except if files in source\target and target\source are equal, don't delete and copy, but rename 


    # ============== HARDLINK 
    # (Attention: here the source is compared against an older backup!)
    # End up with a complete copy of source in target, but have hardlinks to already existing versions in other backups, if it exists
    # source\target: copy
    #   same: hardlink to new backup from old backup
    #   different: copy
    # target\source: ignore

    # --- move detection:
    # The same, except if files in source\target and target\source are equal, don't copy, 
    # but rather hardlink from target\source (old backup) to source\target (new backup)

    # copy source\target in every mode
    for element in fileSet:
        if element.source:
            if not element.target:
                actions.append(Action("copy", name = element.path))

    if config.MODE == "save" or config.MODE == "mirror":
        for element in fileSet:
            if element.source and element.target:
                if not filesEq(os.path.join(config.SOURCE_DIR, element.path), os.path.join(compareDirectory, element.path)):
                    actions.append(Action("copy", name = element.path))
       
    if config.MODE == "mirror":
        if config.COMPARE_WITH_LAST_BACKUP:
            for element in fileSet:
                if not element.source and element.target:
                    actions.append(Action("delete", name = element.path))
    elif config.MODE == "hardlink":
        for element in fileSet:
            if element.source and element.target:
                if filesEq(os.path.join(config.SOURCE_DIR, element.path), os.path.join(compareDirectory, element.path)):
                    actions.append(Action("hardlink", name = element.path))
                else:
                    actions.append(Action("copy", name = element.path))

    # Write the action file
    actionFilePath = os.path.join(targetDirectory, "..", "actions.json")
    with open(actionFilePath, "w") as actionFile:
        actionFile.write('{\n\t"sourceDirectory": "' + config.SOURCE_DIR.encode("unicode_escape").decode("utf-8") + 
                         '",\n\t"compareDirectory": "' + compareDirectory.encode("unicode_escape").decode("utf-8") + 
                         '",\n\t"targetDirectory": "' + targetDirectory.encode("unicode_escape").decode("utf-8") + 
                         '",\n\t"actions": [\n')

        actionFile.write("\t\t" + ",\n\t\t".join(map(lambda x: str(x), actions)) + "\n")

        actionFile.write('\t]\n}\n')

    if config.OPEN_ACTIONLIST:
        os.startfile(actionFilePath)

    if config.EXECUTE_ACTIONLIST:
        # TODO: Maybe not assume python is in the path and rather use something eval-ey?
        subprocess.run(["python", "applyActions.py", actionFilePath])

    if config.DELETE_ACTIONLIST:
        os.remove(actionFilePath)
