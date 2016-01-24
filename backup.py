import os, sys

from collections import OrderedDict
import fnmatch
import filecmp
import importlib.util
import json
import logging
import time

from applyActions import executeActionList

class File:
    def __init__(self, path, *, source, target):
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

# Possible actions:
# copy (always from source to target),
# delete (always in target)
# hardlink (always from compare directory to target directory)
# rename (always in target) (2-variate) (only needed for move detection)
# hardlink2 (alway from compare directory to target directory) (2-variate) (only needed for move detection)
def Action(type, **params):
    return dict(type=type, params=params)

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
                logging.critical("Compare method '" + method + "' does not exist")
                quit()
        else:
            return True

        return False
    except Exception as e: # Why is there no proper list of exceptions that may be thrown by filecmp.cmp and os.stat?
        logging.exception("Either 'stat'-ing or comparing the files failed: " + str(e))
        return False # If we don't know, it has to be assumed they are different, even if this might result in more file operatiosn being scheduled

if __name__ == '__main__':
    logger = logging.getLogger()
    logFormat = logging.Formatter(fmt='%(levelname)-8s %(asctime)-8s.%(msecs)03d: %(message)s', datefmt="%H:%M:%S")

    stderrHandler = logging.StreamHandler(stream=sys.stderr)
    stderrHandler.setFormatter(logFormat)
    logger.addHandler(stderrHandler)

    logFile = None
    if len(sys.argv) < 2:
        logging.critical("Please specify the configuration file for your backup.")
        quit()

    if not os.path.isfile(sys.argv[1]):
        logging.critical("Configuration '" + sys.argv[1] + "' does not exist.")
        quit()

    # from here: http://stackoverflow.com/questions/67631/how-to-import-a-module-given-the-full-path
    spec = importlib.util.spec_from_file_location("config", sys.argv[1])
    # TODO: default values for config
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)

    logger.setLevel(config.LOG_LEVEL)

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
                logging.error("Target Backup directory '" + metadataDirectory + "' already exists. Appending suffix '# " + str(suffixNumber) + "'")

        # Prepare metadata.json
        with open(os.path.join(metadataDirectory, "metadata.json"), "w") as outFile:
            outFile.write(json.dumps({'name': os.path.basename(metadataDirectory), 'successful': False, 'created': time.time()}))

        fileHandler = logging.FileHandler(os.path.join(metadataDirectory, "log.txt"))
        fileHandler.setFormatter(logFormat)
        logger.addHandler(fileHandler)

        targetDirectory = os.path.join(metadataDirectory, os.path.basename(config.SOURCE_DIR))
        compareDirectory = targetDirectory
        os.makedirs(targetDirectory) # Create the config.SOURCE_DIR folder inside the Backup folder

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
                    logging.error("It seems the last backup failed, so it will be skipped and the new backup will compare the source to the backup '" + backup["name"] + "'. The failed backup should probably be deleted.")

    logging.info("source directory: " + config.SOURCE_DIR)
    logging.info("metadata directory: " + metadataDirectory)
    logging.info("target directory: " + targetDirectory)
    logging.info("compare directory: " + compareDirectory)

    # Build a list of all files in source and target
    # TODO: Include/exclude empty folders
    fileSet = []
    for root, dirs, files in os.walk(config.SOURCE_DIR):
        relRoot = os.path.relpath(root, config.SOURCE_DIR)
        for name in files:
            fullName = os.path.normpath(os.path.join(relRoot, name))
            for exlude in config.EXCLUDE_PATHS:
                if fnmatch.fnmatch(fullName, exlude):
                    break
            else:
                fileSet.append(File(fullName, source=True, target=False))

    for root, dirs, files in os.walk(compareDirectory):
        relRoot = os.path.relpath(root, compareDirectory)
        for name in files:
            fullName = os.path.normpath(os.path.join(relRoot, name))
            for element in fileSet:
                if element.path == fullName:
                    element.target = True
                    break
            else:
                fileSet.append(File(fullName, source=False, target=True))

    for file in fileSet:
        logging.debug(file)

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
                actions.append(Action("copy", name=element.path))

    if config.MODE == "save" or config.MODE == "mirror":
        for element in fileSet:
            if element.source and element.target:
                if not filesEq(os.path.join(config.SOURCE_DIR, element.path), os.path.join(compareDirectory, element.path)):
                    actions.append(Action("copy", name=element.path))

    if config.MODE == "mirror":
        if config.COMPARE_WITH_LAST_BACKUP:
            for element in fileSet:
                if not element.source and element.target:
                    actions.append(Action("delete", name=element.path))
    elif config.MODE == "hardlink":
        for element in fileSet:
            if element.source and element.target:
                if filesEq(os.path.join(config.SOURCE_DIR, element.path), os.path.join(compareDirectory, element.path)):
                    actions.append(Action("hardlink", name=element.path))
                else:
                    actions.append(Action("copy", name=element.path))

    # Create the action object
    actionObject = OrderedDict()
    actionObject["sourceDirectory"] = config.SOURCE_DIR
    actionObject["compareDirectory"] = compareDirectory
    actionObject["targetDirectory"] = targetDirectory
    actionObject["actions"] = actions

    actionJson = json.dumps(actionObject, indent=2)

    if config.SAVE_ACTIONFILE:
        # Write the action file
        actionFilePath = os.path.join(metadataDirectory, "actions.json")
        logging.info("Saving the action file to " + actionFilePath)
        with open(actionFilePath, "w") as actionFile:
            actionFile.write(actionJson)

        if config.OPEN_ACTIONFILE:
            os.startfile(actionFilePath)

    if config.SAVE_ACTIONHTML:
        templatePath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "template.html")
        with open(templatePath, "r") as templateFile:
            template = templateFile.read()
        html = template.replace("<!-- JSON -->", actionJson)
        reportPath = os.path.join(metadataDirectory, "actions.html")
        with open(reportPath, "w") as reportFile:
            reportFile.write(html)

        if config.OPEN_ACTIONHTML:
            os.startfile(reportPath)

    if config.APPLY_ACTIONS:
        executeActionList(actionObject)

        with open(os.path.join(metadataDirectory, "metadata.json")) as inFile:
            metadata = json.loads(inFile.read())

        metadata["successful"] = True

        with open(os.path.join(metadataDirectory, "metadata.json"), "w") as outFile:
            outFile.write(json.dumps(metadata))

