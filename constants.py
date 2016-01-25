import logging

LOG_FILENAME = "log.txt"
METADATA_FILENAME = "metadata.json"
ACTIONS_FILENAME = "actions.json"
ACTIONSHTML_FILENAME = "actions.html"
LOGFORMAT = logging.Formatter(fmt='%(levelname)-8s %(asctime)-8s.%(msecs)03d: %(message)s', datefmt="%H:%M:%S")
