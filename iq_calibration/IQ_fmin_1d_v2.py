"""Use shrinking 1d I,Q scans to find minimum in I,Q plane
Written by Naftali 1/18 , uses functions from Yoni's IQMixerMap"""

import time
from time import sleep
from numpy import linspace
from datetime import date
import visa

# import numpy as np
from qm import QuantumMachinesManager
from qm.qua import *

# save_to_file = True
# folder = r"X:\Users\Naftali\Projects\QuantumMachines\Basic mixer calib"
# file_name = "offsets.txt"
# offsets = np.matrix()

# MG_address = 'USB0::0x0957::0x0B0B::MY47191316::INSTR'  # "GPIB0::5::INSTR" #

# OPX ports to which the I,Q ports of the IQ mixer are connected
I_port = 1
Q_port = 2

LOAmp = 18.0  # dBm #
LOFreq = 5000.0  # MHz

I_FIG_NUM = 1
Q_FIG_NUM = 2

MAX_PIXEL = 2 ** 14

plotFigs = True
if plotFigs:
    import matplotlib.pyplot as pyplot


def open_qm():
    qmManager = QuantumMachinesManager("192.168.137.43", 9510)

    return qmManager.open_qm({
        "version": 1,
        "controllers": {
            "con1": {
                "type": "opx1",
                "analog_outputs": {
                    I_port: {"offset": 0.0},
                    Q_port: {"offset": 0.0}
                }
            }
        },
        "elements": {
            "RR1": {
                "singleInput": {
                    "port": ("con1", I_port)
                },
                "intermediate_frequency": 0.0,
                "operations": {
                    "pulse": "my_pulse"
                }
            },
            "RR2": {
                "singleInput": {
                    "port": ("con1", Q_port)
                },
                "intermediate_frequency": 0.0,
                "operations": {
                    "pulse": "my_pulse"
                }
            }
        },
        "pulses": {
            "my_pulse": {
                "operation": "control",
                "length": 2000,
                "waveforms": {
                    "single": "zero_wave"
                }
            }
        },
        "waveforms": {
            "zero_wave": {
                "type": "constant",
                "sample": 0.0
            }
        }
    })


def setupSpectrumAnalyzer(SA, LOFreq):
    SA.write(":FREQ:SPAN 10e0;:FREQ:CENTER " + str(LOFreq * 1e6) + ";:BAND 1.0e2;:SWE:POIN 1;:FORM:DATA ASC,8;")
    SA.write("TRAC:TYPE WRIT")  # turn off averaging
    sleep(1.0)
    SA.write(":CALC:MARK1:STAT ON")
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
        print("Setting I=%f, Q=%f" % (IQ[0], IQ[1]))
    qm.set_output_dc_offset_by_element("RR1", "single", float(IQ[0]))
    qm.set_output_dc_offset_by_element("RR2", "single", float(IQ[1]))

    # print("Setting I=%d, Q=%d" % (IQ[0], IQ[1]))
    # print("IQ[0]={}".format(IQ[0]))
    # print("IQ[1]={}".format(IQ[1]))
    sleep(0.1)

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


print("Make sure the Sweep type rule is \"Best speed\"!")
# setup
rm = visa.ResourceManager()
res_list = rm.list_resources()
# MG = rm.open_resource(MG_address)
# setupMG(MG, LOFreq, LOAmp)
SA = rm.open_resource('USB0::0x0957::0x0B0B::MY47191316::INSTR')
qm = open_qm()

with program() as prog:
    with infinite_loop_():
        play("pulse", "RR1")
        play("pulse", "RR2")

job = qm.execute(prog)
#
getWithIQ([0.0, 0.0], qm, SA)  # send a sequence in order to have a trigger before setting SA marker to max
setupSpectrumAnalyzer(SA, LOFreq)

print("LOFreq = %f, LOAmp = %f" % (LOFreq, LOAmp))
currMin = 100.0  # minimal transmission, start with a high value
currRange = 0.1  # 0.98#0.80 # 2**10 #range to scan around the minima
minimum = -90  # Stop at this value
numPoints = 16  # number of points
I0 = 0.0
Q0 = 0.0
start = time.time()
while currMin > minimum and currRange >= 16. / 2 ** 16:
    minTI, I0 = findMinI(I0, Q0, currRange, numPoints, qm, SA, plotFigs)  # scan I
    currMin, Q0 = findMinQ(I0, Q0, currRange, numPoints, qm, SA, plotFigs)  # Scan Q
    print("Range = %f, I0 = %f, Q0 = %f, currMin = %f " % (currRange, I0, Q0, currMin))
    currRange = currRange / 2
end = time.time()
#
print("Elapsed time is %f seconds" % (end - start))

# turn MG off
# MG.write("RF 0")

if plotFigs:
    pyplot.xlabel("I/Q [pixels]")
    pyplot.ylabel("Transmitted power [dBm]")
    pyplot.legend(['I','Q'])
    pyplot.show()
