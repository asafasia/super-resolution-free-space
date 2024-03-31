"""Use shrinking 1d I,Q scans to find minimum in I,Q plane
Written by Naftali 1/18 , uses functions from Yoni's IQMixerMap"""

import time
from time import sleep
from scipy import linspace
from datetime import date
import visa

import numpy as np
from qm.QuantumMachinesManager import QuantumMachinesManager
from qm.qua import *

# save_to_file = True
# folder = r"X:\Users\Naftali\Projects\QuantumMachines\Basic mixer calib"
# file_name = "offsets.txt"
# offsets = np.matrix()


LOAmp = -10.0  # 12.0 #dBm #
LOFreq = 5000.8  # MHz

I_FIG_NUM = 1
Q_FIG_NUM = 2

MAX_PIXEL = 2 ** 14

plotFigs = True
if plotFigs:
    import matplotlib.pyplot as pyplot


def open_qm():
    qmManager = QuantumMachinesManager(host="192.168.137.15")

    return qmManager.open_qm({
        "version": 1,
        "controllers": {
            "con1": {
                "type": "opx1"  # ,
                # "analog": {
                #     1: {"offset": offset1},
                #     2: {"offset": offset2}
                # }
            }
        },
        "elements": {
            "RR": {
                "mixInputs": {
                    "I": ("con1", 1),
                    "Q": ("con1", 2),
                    "mixer": "my_mixer",
                    "lo_frequency": 0
                },
                "frequency": 0,
            }
        },
        "mixers": {
            "my_mixer": [
                {"freq": 0, "lo_freq": 0, "correction": [1, 0, 0, 1]}
            ]
        }
    })


def setupSpectrumAnalyzer(SA, LOFreq):
    SA.write(":FREQ:SPAN 10e0;:FREQ:CENTER " + str(LOFreq * 1e6) + ";:BAND 1.0e2;:SWE:POIN 1;:FORM:DATA ASC,8;")
    sleep(1.0)
    SA.write(":CALC:MARK1:MAX;")


def setupMG(MG, LOFreq, LOAmp):
    MG.write('F1 %fMH' % LOFreq)
    sleep(0.100)
    MG.write('L1 %fDM' % LOAmp)
    sleep(0.100)
    MG.write("RF 1")
    sleep(0.100)


def getWithIQ(IQ, qm, SA, verbose=False):
    """Sets DAC output to I=IQ[0] and Q=IQ[1] and measures with spectrum analyzer"""
    if verbose:
        print("Setting I=%d, Q=%d" % (IQ[0], IQ[1]))

    qm.async_set_port_dc(("con1", 1), i=IQ[0], q=IQ[0])
    # qm.async_set_port_dc(("dac1", 5), i=IQ[0], q=IQ[0])
    qm.async_set_port_dc(("con1", 2), i=IQ[1], q=IQ[1])
    # qm.async_set_port_dc(("dac2", 4), i=IQ[1], q=IQ[1])
    qm.async_set_port_dc(("con1", 3), i=IQ[0], q=IQ[0])
    qm.async_set_port_dc(("con1", 4), i=IQ[1], q=IQ[1])
    # qm.async_set_port_dc(("dac3", 3), i=IQ[0], q=IQ[0])

    # print("Setting I=%d, Q=%d" % (IQ[0], IQ[1]))
    # print("IQ[0]={}".format(IQ[0]))
    # print("IQ[1]={}".format(IQ[1]))
    sleep(0.5)

    t = float(SA.query(":CALC:MARK:Y?;"))

    # print("Transmitted power is %f dBm" % t)

    if verbose:
        print("Transmitted power is %f dBm" % t)
    return t


def findMinI(I0, Q0, currRange, numPoints, qm, SA, plotRes=False):
    """scans numPoints +/-currRange/2 around I0 with a constant Q0
    returns the I which gave the minimal transmission
    plot scan if plotRes = True
    """
    scanVec = linspace(max([I0 - currRange / 2, -0.5]), min([I0 + currRange / 2, 0.5 - 2 ** -16]), numPoints)
    tRes = []

    for val in scanVec:
        tRes.append(getWithIQ([val, Q0], qm, SA))
        # print(tRes)

    if plotRes:
        pyplot.figure(I_FIG_NUM)
        pyplot.plot(scanVec, tRes, label=str(Q0))

    minVal = min(tRes)
    return minVal, scanVec[tRes.index(minVal)]


def findMinQ(I0, Q0, currRange, numPoints, qm, SA, plotRes=False):
    """scans numPoints +/-currRange/2 around Q0 with a constant I0
    returns the Q which gave the minimal transmission
    plot scan if plotRes = True
    """
    scanVec = linspace(max([Q0 - currRange / 2, -0.5]), min([Q0 + currRange / 2, 0.5 - 2 ** -16]), numPoints)
    tRes = []

    for val in scanVec:
        tRes.append(getWithIQ([I0, val], qm, SA))

    if plotRes:
        pyplot.figure(Q_FIG_NUM)
        pyplot.plot(scanVec, tRes, label=str(I0))

    minVal = min(tRes)
    return minVal, scanVec[tRes.index(minVal)]


if True:

    # setup
    rm = visa.ResourceManager()
    res_list = rm.list_resources()
    MG = rm.open_resource("GPIB0::7::INSTR")
    setupMG(MG, LOFreq, LOAmp)
    SA = rm.open_resource("GPIB0::24::INSTR")
    qm = open_qm()

    getWithIQ([0.0, 0.0], qm, SA)  # send a sequence in order to have a trigger before setting SA marker to max
    setupSpectrumAnalyzer(SA, LOFreq)

    print("LOFreq = %f, LOAmp = %f" % (LOFreq, LOAmp))
    currMin = 100.0  # minimal transmission, start with a high value
    currRange = 0.80  # 2**10 #range to scan around the minima
    numPoints = 16  # number of points
    I0 = 0.0
    Q0 = 0.0
    start = time.time()
    while currMin > -90 and currRange >= 16. / 2 ** 16:
        minTI, I0 = findMinI(I0, Q0, currRange, numPoints, qm, SA, plotFigs)  # scan I
        currMin, Q0 = findMinQ(I0, Q0, currRange, numPoints, qm, SA, plotFigs)  # Scan Q
        print("Range = %f, I0 = %f, Q0 = %f, currMin = %f " % (currRange, I0, Q0, currMin))
        currRange = currRange / 2
    end = time.time()

    print("Elapsed time is %f seconds" % (end - start))

    # turn MG off
    MG.write("RF 0")

    if plotFigs:
        pyplot.figure(I_FIG_NUM)
        pyplot.xlabel("I [pixels]")
        pyplot.ylabel("Transmitted power [dBm]")
        pyplot.legend()
        pyplot.draw()
        pyplot.figure(Q_FIG_NUM)
        pyplot.xlabel("Q [pixels]")
        pyplot.ylabel("Transmitted power [dBm]")
        pyplot.legend()
        pyplot.draw()
        pyplot.show()

else:
    qm = open_qm()

    dc = -0.2
    qm.async_set_port_dc(("con1", 3), i=dc, q=dc)
    qm.async_set_port_dc(("con1", 3), i=dc, q=dc)

'''
    for dc in np.arange(-0.5, 0.5, 0.05):
        qm.async_set_port_dc(("dac3", 3), i=dc, q=dc)
        print("setting dc={}".format(dc))
        time.sleep(0.5)
    '''
