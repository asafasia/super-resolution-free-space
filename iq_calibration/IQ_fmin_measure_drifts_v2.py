"""Use shrinking 1d I,Q scans to find minimum in I,Q plane
Written by Naftali 1/18,1/21 , uses functions from Yoni's IQMixerMap
Measure drifts as a function of time
new in v2: use instruments_py27 libraries
"""

import time
from time import sleep
import numpy as np
from numpy import linspace, arange
# from instruments_py27.anritsu import Anritsu_MG
from instruments_py27.E8241A import E8241A_MG
from instruments_py27.spectrum_analyzer import N9010A_SA

MG_class = E8241A_MG #Anritsu_MG #


# import numpy as np
from qm.QuantumMachinesManager import QuantumMachinesManager
from qm.qua import *

from scipy import optimize

BW = 100
num_averages = 3
wait_time = 1


MG_address = "GPIB0::28::INSTR"#"GPIB0::5::INSTR" #
SA_address = "TCPIP0::192.168.137.177::inst0::INSTR"

#OPX ports to which the I,Q ports of the IQ mixer are connected
I_port = 3
Q_port = 4

LOAmp = 12.0#18.0 #dBm #
LOFreq =  4490 #MHz

warmup_time = 0.0 #seconds


I_FIG_NUM = 1
Q_FIG_NUM = 2

#for drift measurement
measure_drift = False
dt = 1.0 #seconds
measure_time = 180 #seconds
num_drift_points = int(measure_time/dt)

plotFigs = True
import matplotlib.pyplot as pyplot
pyplot.ion()




def open_qm():
    qmManager = QuantumMachinesManager()

    return qmManager.open_qm({
        "version" : 1 ,
        "controllers": {
            "con1": {
                "type": "opx1",
                "analog": {
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
                "frequency": 0.0,
                "operations": {
                    "pulse": "my_pulse"
                }
            },
            "RR2": {
                "singleInput": {
                    "port": ("con1", Q_port)
                },
                "frequency": 0.0,
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



def setupSpectrumAnalyzer(SA, LOFreq, BW = 100, num_averages = 8):
    SA.setup_spectrum_analyzer(center_freq=LOFreq, span=10, BW=BW, points=1)
    SA.setup_averaging(True, num_averages)
    sleep(1.0)
    SA.set_marker_max()

def getWithIQ(IQ,qm,SA,verbose=False, wait_time=1.0):
    """Sets DAC output to I=IQ[0] and Q=IQ[1] and measures with spectrum analyzer"""
    if verbose:
        print("Setting I=%f, Q=%f" % (IQ[0],IQ[1]))
    qm.set_output_dc_offset_by_element("RR1","single",float(IQ[0]))
    qm.set_output_dc_offset_by_element("RR2","single",float(IQ[1]))

    # print("Setting I=%d, Q=%d" % (IQ[0], IQ[1]))
    # print("IQ[0]={}".format(IQ[0]))
    # print("IQ[1]={}".format(IQ[1]))

    # sleep(0.1)
    SA.restart_averaging()
    sleep(wait_time)

    t = SA.get_marker()

    # print("Transmitted power is %f dBm" % t)

    if verbose:
        print("Transmitted power is %f dBm" % t)
    return t


def findMinI(I0,Q0,currRange,numPoints,qm,SA, wait_time ,plotRes=False):
    """scans numPoints +/-currRange/2 around I0 with a constant Q0
    returns the I which gave the minimal transmission
    plot scan if plotRes = True
    """
    scanVec = linspace(max([I0-currRange/2,-0.5]),min([I0+currRange/2,0.5-2**-16]),numPoints)
    tRes = []
    
    for val in scanVec:
        tRes.append(getWithIQ([val,Q0],qm,SA, wait_time=wait_time))
        # print(tRes)

    if plotRes:
        pyplot.figure(I_FIG_NUM)
        pyplot.plot(scanVec,tRes,label=str(Q0))
        pyplot.draw_all()
        pyplot.pause(0.01)
    
    minVal = min(tRes)
    return minVal,scanVec[tRes.index(minVal)]

def findMinQ(I0,Q0,currRange,numPoints,qm,SA, wait_time, plotRes=False):
    """scans numPoints +/-currRange/2 around Q0 with a constant I0
    returns the Q which gave the minimal transmission
    plot scan if plotRes = True
    """
    scanVec = linspace(max([Q0-currRange/2,-0.5]),min([Q0+currRange/2,0.5-2**-16]),numPoints)
    tRes = []
    
    for val in scanVec:
        tRes.append(getWithIQ([I0,val],qm,SA, wait_time=wait_time))
    
    if plotRes:
        pyplot.figure(Q_FIG_NUM)
        pyplot.plot(scanVec,tRes,label=str(I0))
        pyplot.draw_all()
        pyplot.pause(0.01)

    minVal = min(tRes)
    return minVal,scanVec[tRes.index(minVal)]


print("Make sure the Sweep type rule is \"Best speed\"!")
#setup
MG = MG_class(MG_address)
MG.setup_MG(LOFreq, LOAmp)
print("Waiting %f seconds for warm-up" % warmup_time)
sleep(warmup_time)
SA = N9010A_SA(SA_address)
qm = open_qm()

with program() as prog:
    with infinite_loop_():
        play("pulse", "RR1")
        play("pulse", "RR2")

job = qm.execute(prog, experimental_calculations=False)

getWithIQ([0.0,0.0],qm,SA) #send a sequence in order to have a trigger before setting SA marker to max
setupSpectrumAnalyzer(SA, LOFreq, BW, num_averages)


print("LOFreq = %f, LOAmp = %f" % (LOFreq,LOAmp))
currMin = 100.0 #minimal transmission, start with a high value
currRange = 0.48#0.1#0.98#0.80  #range to scan around the minima
minimum = -90#Stop at this value
numPoints = 16  #number of points
I0 = 0.0
Q0 = 0.0
start = time.time()
# while currMin>minimum and currRange>=16./2**16:
#     minTI, I0 = findMinI(I0,Q0,currRange,numPoints,qm,SA,wait_time, plotFigs) #scan I
#     currMin, Q0 = findMinQ(I0,Q0,currRange,numPoints,qm,SA,wait_time,plotFigs) #Scan Q
#     print ("Range = %f, I0 = %f, Q0 = %f, currMin = %f " % (currRange,I0,Q0,currMin))
#     currRange = currRange/2
ret = optimize.minimize(getWithIQ, x0=[I0,Q0], method="Nelder-Mead", args=(qm, SA, True, wait_time),options={"xatol":1e-4,"fatol":2,"disp":True,
    "initial_simplex":np.array([[-0.02,0.02],[0.02,0.02],[0,-0.02]])})
# ret = optimize.minimize(getWithIQ, x0=[I0,Q0], method="Nelder-Mead", args=(qm, SA, True, wait_time),options={"xatol":1e-4,"fatol":2,"disp":True,
#     "initial_simplex":np.array([[-0.1,0.1],[0.1,0.1],[0,-0.1]])})
print(ret)
#set to minimum
getWithIQ(ret.x,qm,SA,True)
end = time.time()

print("Elapsed time is %f seconds" % (end-start))

#measure drifts
if measure_drift:
    drifts = []
    print("Measuring drift for %f seconds" % measure_time)
    for _ in range(num_drift_points):
        drifts.append(SA.get_marker())
        sleep(dt)
        SA.restart_averaging() # restart average


# turn MG off
MG.set_on(False)


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


if measure_drift:
    pyplot.figure()
    pyplot.plot(arange(0,measure_time,dt),drifts)
    pyplot.ylabel("Power [dBm]")
    pyplot.xlabel("Time [sec.]")
    pyplot.draw()

pyplot.show()


