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
    # rename (always in target) (2-variate) (only needed for move detection)
    # hardlink2 (alway from compare directory to target directory) (2-variate) (only needed for move detection)

    def __init__(self, actionType, **kwargs):
        self.type = actionType
        self.params = kwargs

    def __str__(self):
        paramStr = ", ".join(map(lambda k_v: '"' + k_v[0] + '": "' + k_v[1].encode("unicode_escape").decode("utf-8") + '"', self.params.items())) 
        return '{"type": "' + self.type + '", "params": {' + paramStr + '}}'

def filesEq(a, b):
    try:
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
                if not filecmp.cmp(a, b, shallow = False):
                    break
        else:
            return True

        return False
    except FileNotFoundError as e: # Why is there no proper list of exceptions that may be thrown by filecmp.cmp and os.stat?
        log("error", e)
        # TODO: Solve this properly
        return True # Mostly when files are equal, nothing happens

def log(msgType, msg):
    prefixes = {'critical': 'CRT', 'error': "ERR", 'warning': "WRN", 'info': "NFO"}
    line = prefixes[msgType] + " - " + msg
    print(line)
    if logFile != None:
        with open(logFile, "a") as outFile:
            outFile.write(line + "\n")
    if msgType == "critical":
        quit()

if __name__ == '__main__':
    logFile = None
    if len(sys.argv) < 2:
        log("critical", "Please specify the configuration file for your backup.")

    # from here: http://stackoverflow.com/questions/67631/how-to-import-a-module-given-the-full-path
    if not os.path.isfile(sys.argv[1]):
        log("critical", "Configuration '" + sys.argv[1] + "' does not exist.")
    spec = importlib.util.spec_from_file_location("config", sys.argv[1])
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)

    if config.MODE == "hardlink":
        config.VERSIONED = True
        config.COMPARE_WITH_LAST_BACKUP = True

    # Setup directories
    metadataDirectory = config.TARGET_DIR
    targetDirectory = config.TARGET_DIR
    compareDirectory = targetDirectory
    if config.VERSIONED:
        metadataDirectory = os.path.join(config.TARGET_DIR, time.strftime(config.VERSION_NAME))

        suffixNumber = 1
        while True:
            try:
                path = metadataDirectory
                if suffixNumber > 1: path = path + " #" + str(suffixNumber)
                os.makedirs(path)
                metadataDirectory = path
                break
            except FileExistsError as e:
                suffixNumber += 1
                log("error", "Target Backup directory '" + metadataDirectory + "' already exists. Appending suffix '# " + str(suffixNumber) + "'")

        # Prepare metadata.json
        with open(os.path.join(metadataDirectory, "metadata.json"), "w") as outFile:
            outFile.write(json.dumps({'name': os.path.basename(metadataDirectory), 'successful': False, 'created': time.time()}))

        logFile = os.path.join(metadataDirectory, "log.txt")
        targetDirectory = os.path.join(metadataDirectory, os.path.basename(config.SOURCE_DIR))
        compareDirectory = targetDirectory
        os.makedirs(targetDirectory) # Create the config.SOURCE_DIR folder

        oldBackups = []
        if config.COMPARE_WITH_LAST_BACKUP:
            for entry in os.scandir(config.TARGET_DIR):
                if entry.is_dir() and os.path.join(config.TARGET_DIR, entry.name) != metadataDirectory:
                    metadataFile = os.path.join(config.TARGET_DIR, entry.name, "metadata.json")
                    if os.path.isfile(metadataFile):
                        with open(metadataFile) as inFile:
                            oldBackups.append(json.loads(inFile.read()))

            for backup in sorted(oldBackups, key = lambda x: x['created'], reverse = True):
                if backup["successful"]:
                    compareDirectory = os.path.join(config.TARGET_DIR, backup['name'], os.path.basename(config.SOURCE_DIR))
                    break
                else:
                    log("error", "It seems the last backup failed, so it will be skipped and the new backup will compare the source to the backup '" + backup["name"] + "'. The failed backup should probably be deleted.")

    log("info", "source directory: " + config.SOURCE_DIR)
    log("info", "metadata directory: " + metadataDirectory)
    log("info", "target directory: " + targetDirectory)
    log("info", "compare directory: " + compareDirectory)

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
    actionFilePath = os.path.join(metadataDirectory, "actions.json")
    with open(actionFilePath, "w") as actionFile:
        actionFile.write('{\n\t"sourceDirectory": "' + config.SOURCE_DIR.encode("unicode_escape").decode("utf-8") + 
                         '",\n\t"compareDirectory": "' + compareDirectory.encode("unicode_escape").decode("utf-8") + 
                         '",\n\t"targetDirectory": "' + targetDirectory.encode("unicode_escape").decode("utf-8") + 
                         '",\n\t"actions": [\n')

        actionFile.write("\t\t" + ",\n\t\t".join(map(lambda x: str(x), actions)) + "\n")

        actionFile.write('\t]\n}\n')

    if config.OPEN_ACTIONLIST:
        os.startfile(actionFilePath)

    execActionsReturn = 0
    if config.EXECUTE_ACTIONLIST:
        # TODO: Maybe not assume python is in the path and rather use something eval-ey?
        execActionsReturn = subprocess.run(["python", "applyActions.py", actionFilePath]).returncode

    if execActionsReturn == 0:
        metadata = None
        with open(os.path.join(metadataDirectory, "metadata.json")) as inFile:
            metadata = json.loads(inFile.read())
        metadata["successful"] = True
        with open(os.path.join(metadataDirectory, "metadata.json"), "w") as outFile:
            outFile.write(json.dumps(metadata))

    if config.DELETE_ACTIONLIST:
        os.remove(actionFilePath)
