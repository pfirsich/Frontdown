import os, sys

from collections import OrderedDict
import fnmatch
import filecmp
import importlib.util
import json
import logging
import time

from applyActions import executeActionList
from constants import *

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

def relativeFileWalk(path):
    for root, dirs, files in os.walk(path):
        relRoot = os.path.relpath(root, path)
        #yield os.path.normpath(relRoot)
        for name in files:
            yield os.path.normpath(os.path.join(relRoot, name))

# Possible actions:
# copy (always from source to target),
# delete (always in target)
# hardlink (always from compare directory to target directory)
# rename (always in target) (2-variate) (only needed for move detection)
# hardlink2 (alway from compare directory to target directory) (2-variate) (only needed for move detection)
def Action(type, **params):
    return OrderedDict(type=type, params=params)

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

    stderrHandler = logging.StreamHandler(stream=sys.stderr)
    stderrHandler.setFormatter(LOGFORMAT)
    logger.addHandler(stderrHandler)

    if len(sys.argv) < 2:
        logging.critical("Please specify the configuration file for your backup.")
        quit()

    if not os.path.isfile(sys.argv[1]):
        logging.critical("Configuration '" + sys.argv[1] + "' does not exist.")
        quit()

    # from here: http://stackoverflow.com/questions/67631/how-to-import-a-module-given-the-full-path
    spec = importlib.util.spec_from_file_location("config", sys.argv[1])
    # TODO: default values for config, also implement config class that prohibits setting and getting non-registered values
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)

    logger.setLevel(config.LOG_LEVEL)

    if config.MODE == "hardlink":
        config.VERSIONED = True
        config.COMPARE_WITH_LAST_BACKUP = True

    # Setup target and metadata directories and metadata file
    os.makedirs(config.TARGET_DIR, exist_ok = True)
    if config.VERSIONED:
        metadataDirectory = os.path.join(config.TARGET_DIR, time.strftime(config.VERSION_NAME))

        suffixNumber = 1
        while True:
            try:
                path = metadataDirectory
                if suffixNumber > 1: path = path + "_" + str(suffixNumber)
                os.makedirs(path)
                metadataDirectory = path
                break
            except FileExistsError as e:
                suffixNumber += 1
                logging.error("Target Backup directory '" + path + "' already exists. Appending suffix '_" + str(suffixNumber) + "'")
    else:
        metadataDirectory = config.TARGET_DIR

    # Create metadataDirectory and targetDirectory
    targetDirectory = os.path.join(metadataDirectory, os.path.basename(config.SOURCE_DIR))
    compareDirectory = targetDirectory
    os.makedirs(targetDirectory, exist_ok = True)

    # Init log file
    fileHandler = logging.FileHandler(os.path.join(metadataDirectory, LOG_FILENAME))
    fileHandler.setFormatter(LOGFORMAT)
    logger.addHandler(fileHandler)

    # update compare directory
    if config.VERSIONED and config.COMPARE_WITH_LAST_BACKUP:
        oldBackups = []
        for entry in os.scandir(config.TARGET_DIR):
            if entry.is_dir() and os.path.join(config.TARGET_DIR, entry.name) != metadataDirectory:
                metadataFile = os.path.join(config.TARGET_DIR, entry.name, METADATA_FILENAME)
                if os.path.isfile(metadataFile):
                    with open(metadataFile) as inFile:
                        oldBackups.append(json.load(inFile))

        logging.debug("Found " + str(len(oldBackups)) + " old backups: " + str(oldBackups))

        for backup in sorted(oldBackups, key = lambda x: x['started'], reverse = True):
            if backup["successful"]:
                compareDirectory = os.path.join(config.TARGET_DIR, backup['name'], os.path.basename(config.SOURCE_DIR))
                break
            else:
                logging.error("It seems the last backup failed, so it will be skipped and the new backup will compare the source to the backup '" + backup["name"] + "'. The failed backup should probably be deleted.")
        else:
            logging.warning("No old backup found. Creating first backup.")

    # Prepare metadata.json
    with open(os.path.join(metadataDirectory, METADATA_FILENAME), "w") as outFile:
        json.dump({
            'name': os.path.basename(metadataDirectory),
            'successful': False,
            'started': time.time(),
            'sourceDirectory': config.SOURCE_DIR,
            'compareDirectory': compareDirectory,
            'targetDirectory': targetDirectory,
        }, outFile, indent=4)

    logging.info("Source directory: " + config.SOURCE_DIR)
    logging.info("Metadata directory: " + metadataDirectory)
    logging.info("Target directory: " + targetDirectory)
    logging.info("Compare directory: " + compareDirectory)
    logging.info("Starting backup in " + config.MODE + " mode")

    # Build a list of all files in source and target
    # TODO: Include/exclude empty folders
    fileSet = []
    for fullName in relativeFileWalk(config.SOURCE_DIR):
        for exclude in config.EXCLUDE_PATHS:
            if fnmatch.fnmatch(fullName, exclude):
                break
        else:
            fileSet.append(File(fullName, source=True, target=False))

    for fullName in relativeFileWalk(compareDirectory):
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

        # source\target
        if element.source and not element.target:
            actions.append(Action("copy", name=element.path))

        # source&target
        elif element.source and element.target:
            # same
            if filesEq(os.path.join(config.SOURCE_DIR, element.path), os.path.join(compareDirectory, element.path)):
                if config.MODE == "hardlink":
                    actions.append(Action("hardlink", name=element.path))

            # different
            else:
                actions.append(Action("copy", name=element.path))

        # target\source
        elif not element.source and element.target:
            if config.MODE == "mirror":
                if not config.COMPARE_WITH_LAST_BACKUP or not config.VERSIONED:
                    actions.append(Action("delete", name=element.path))


    # Create the action object
    actionJson = "[\n" + ",\n".join(map(json.dumps, actions)) + "\n]"

    if config.SAVE_ACTIONFILE:
        # Write the action file
        actionFilePath = os.path.join(metadataDirectory, ACTIONS_FILENAME)
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
        reportPath = os.path.join(metadataDirectory, ACTIONSHTML_FILENAME)
        with open(reportPath, "w") as reportFile:
            reportFile.write(html)

        if config.OPEN_ACTIONHTML:
            os.startfile(reportPath)

    if config.APPLY_ACTIONS:
        executeActionList(metadataDirectory, actions)

