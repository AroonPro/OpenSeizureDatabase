#!/usr/bin/env python3

import argparse
from re import X
import sys
import os
import json
import importlib
from urllib.parse import _NetlocResultMixinStr
#from tkinter import Y
import sklearn.model_selection
import sklearn.metrics
import numpy as np
import matplotlib.pyplot as plt

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import libosd.osdDbConnection
import libosd.dpTools
import libosd.osdAlgTools
import libosd.configUtils


def type2id(typeStr):
    if typeStr.lower() == "seizure":
        id = 1
    elif typeStr.lower() == "false alarm":
        id = 0
    elif typeStr.lower() == "nda":
        id = 0
    else:
        id = 2
    return id

def dp2accVector(dpObj):
    '''Convert a datapoint object into an input vector to be fed into the neural network.   Note that if dp is not a dict, it is assumed to be a json string
    representation instead.
    '''
    dpInputData = []
    if (type(dpObj) is dict):
        rawDataStr = libosd.dpTools.dp2rawData(dpObj)
    else:
        rawDataStr = dpObj
    accData, hr = libosd.dpTools.getAccelDataFromJson(rawDataStr)
    #print(accData, hr)

    if (accData is not None):
        for n in range(0,len(accData)):
            dpInputData.append(accData[n])
    else:
        print("*** Error in Datapoint: ", dpObj)
        print("*** No acceleration data found with datapoint.")
        print("*** I recommend adding event %s to the invalidEvents list in the configuration file" % dp['eventId'])
        exit(-1)

    return dpInputData
    

def dp2row(ev, dp, header=False):
    ''' convert event Object ev and Datapoint object dp into a list of data to be output to a csv file.
    If header=True, returns a .csv header which will represent the columns in the data.
    '''
    rowLst = []
    if (header):
        rowLst.append("id")
        rowLst.append("userId")
        rowLst.append("type")
        rowLst.append("dataTime")
        rowLst.append("hr")
        rowLst.append("o2sat")
        for n in range(0,125):
            rowLst.append("M%03d" % n)
    else:
        rowLst.append(ev['id'])
        rowLst.append(ev['userId'])
        rowLst.append(type2id(ev['type']))
        rowLst.append(libosd.dpTools.getParamFromDp('dataTime',dp))
        rowLst.append(libosd.dpTools.getParamFromDp('hr',dp))
        rowLst.append(libosd.dpTools.getParamFromDp('o2sat',dp))
        rowLst.extend(libosd.dpTools.getParamFromDp('rawData', dp))
    return(rowLst)

def writeRowToFile(rowLst, f):
    first = True
    for item in rowLst:
        if not first:
            f.write(",")
        f.write(str(item))
        first = False
    f.write("\n")



def flattenOsdb(inFname, outFname, configObj, debug=False):
    '''
    getDataFromEventIds() - takes a list of event IDs to be used, an instance of OsdDbConnection to access the
    OSDB data, and a configuration object, and returns a tuple (outArr, classArr) which is a list of datapoints
    and a list of classes (0=OK, 1=seizure) for each datapoint.
    FIXME - this is where we need to implement Phase Augmentation.
    '''
    dbDir = libosd.configUtils.getConfigParam("cacheDir", configObj)
    invalidEvents = libosd.configUtils.getConfigParam("invalidEvents", configObj)

    # Load each of the three events files (tonic clonic seizures,
    #all seizures and false alarms).
    osd = libosd.osdDbConnection.OsdDbConnection(cacheDir=dbDir, debug=debug)

    if inFname is not None:
        print("flattenOsdb - loading file %s" % inFname)
        eventsObjLen = osd.loadDbFile(inFname)
    else:
        dataFilesLst = libosd.configUtils.getConfigParam("dataFiles", configObj)
        for fname in dataFilesLst:
            eventsObjLen = osd.loadDbFile(fname)
            print("loaded %d events from file %s" % (eventsObjLen, fname))
    osd.removeEvents(invalidEvents)
    #osd.listEvents()
    print("Events Loaded")

    if outFname is not None:
        outPath = os.path.join(dbDir, outFname)
        print("sending output to file %s" % outPath)
        outFile = open(outPath,'w')
    else:
        print("sending output to stdout")
        outFile = sys.stdout
    writeRowToFile(dp2row(None, None, True), outFile)

    eventIdsLst = osd.getEventIds()
    nEvents = len(eventIdsLst)
    outArr = []
    classArr = []
    for eventNo in range(0,nEvents):
        eventId = eventIdsLst[eventNo]
        eventObj = osd.getEvent(eventId, includeDatapoints=True)
        if (not 'datapoints' in eventObj or eventObj['datapoints'] is None):
            print("Event %s: No datapoints - skipping" % eventId)
        else:
            #print("nDp=%d" % len(eventObj['datapoints']))
            lastDpInputData = None
            for dp in eventObj['datapoints']:
                rowLst = dp2row(eventObj, dp)
                writeRowToFile(rowLst, outFile)
    if (outFname is not None):
        outFile.close()
        print("Output written to file %s" % outFname)


    return True

 

def main():
    print("flattenOsdb.main()")
    parser = argparse.ArgumentParser(description='Produce a flattened version of OpenSeizureDatabase data')
    parser.add_argument('--config', default="flattenConfig.json",
                        help='name of json file containing configuration data')
    parser.add_argument('-i', default=None,
                        help='Input filename (uses stdin if not specified)')
    parser.add_argument('-o', default=None,
                        help='Output filename (uses stout if not specified)')
    parser.add_argument('--debug', action="store_true",
                        help='Write debugging information to screen')
    argsNamespace = parser.parse_args()
    args = vars(argsNamespace)
    print(args)



    configObj = libosd.configUtils.loadConfig(args['config'])
    print("configObj=",configObj)
    # Load a separate OSDB Configuration file if it is included.
    if configObj is not None and ("osdbCfg" in configObj):
        osdbCfgFname = libosd.configUtils.getConfigParam("osdbCfg",configObj)
        print("Loading separate OSDB Configuration File %s." % osdbCfgFname)
        osdbCfgObj = libosd.configUtils.loadConfig(osdbCfgFname)
        # Merge the contents of the OSDB Configuration file into configObj
        configObj = configObj | osdbCfgObj

    print("configObj=",configObj)


    flattenOsdb(args['i'], args['o'], configObj)

if __name__ == "__main__":
    main()
