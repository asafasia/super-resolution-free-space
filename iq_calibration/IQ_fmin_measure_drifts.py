"""Use shrinking 1d I,Q scans to find minimum in I,Q plane
Written by Naftali 1/18 , uses functions from Yoni's IQMixerMap
Measure drifts as a function of time"""

import time
from time import sleep
import numpy as np
from numpy import linspace, arange
import visa

# import numpy as np
from qm.QuantumMachinesManager import QuantumMachinesManager
from qm.qua import *

from scipy import optimize

MG_address = "GPIB0::5::INSTR" #"GPIB0::7::INSTR" #

#OPX ports to which the I,Q ports of the IQ mixer are connected
I_port = 1
Q_port = 2

LOAmp = 18.0 #dBm #
LOFreq = 6103.0 #MHz

warmup_time = 0.0 #seconds


I_FIG_NUM = 1
Q_FIG_NUM = 2

#for drift measurement
measure_drift = False
dt = 1.0 #seconds
measure_time = 180 #seconds
num_drift_points = int(measure_time/dt)

plotFigs = False#True
import matplotlib.pyplot as pyplot




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



def setupSpectrumAnalyzer(SA, LOFreq):
    SA.write(":FREQ:SPAN 10e0;:FREQ:CENTER "+str(LOFreq*1e6)+";:BAND 1.0e2;:SWE:POIN 1;:FORM:DATA ASC,8;")
    # SA.write("TRAC:TYPE WRIT") #turn off averaging
    SA.write(":TRAC:TYPE AVER")
    SA.write("AVER:COUN %d" % 8)
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


def getWithIQ(IQ,qm,SA,verbose=False):
    """Sets DAC output to I=IQ[0] and Q=IQ[1] and measures with spectrum analyzer"""
    if verbose:
        print("Setting I=%f, Q=%f" % (IQ[0],IQ[1]))
    qm.set_output_dc_offset_by_element("RR1","single",float(IQ[0]))
    qm.set_output_dc_offset_by_element("RR2","single",float(IQ[1]))

    # print("Setting I=%d, Q=%d" % (IQ[0], IQ[1]))
    # print("IQ[0]={}".format(IQ[0]))
    # print("IQ[1]={}".format(IQ[1]))

    # sleep(0.1)
    SA.write(":TRAC:TYPE AVER") #restart average
    sleep(1.0)

    t = float(SA.query(":CALC:MARK:Y?;"))

    # print("Transmitted power is %f dBm" % t)

    if verbose:
        print("Transmitted power is %f dBm" % t)
    return t


def findMinI(I0,Q0,currRange,numPoints,qm,SA,plotRes=False):
    """scans numPoints +/-currRange/2 around I0 with a constant Q0
    returns the I which gave the minimal transmission
    plot scan if plotRes = True
    """
    scanVec = linspace(max([I0-currRange/2,-0.5]),min([I0+currRange/2,0.5-2**-16]),numPoints)
    tRes = []
    
    for val in scanVec:
        tRes.append(getWithIQ([val,Q0],qm,SA))
        # print(tRes)

    if plotRes:
        pyplot.figure(I_FIG_NUM)
        pyplot.plot(scanVec,tRes,label=str(Q0))
    
    minVal = min(tRes)
    return minVal,scanVec[tRes.index(minVal)]

def findMinQ(I0,Q0,currRange,numPoints,qm,SA,plotRes=False):
    """scans numPoints +/-currRange/2 around Q0 with a constant I0
    returns the Q which gave the minimal transmission
    plot scan if plotRes = True
    """
    scanVec = linspace(max([Q0-currRange/2,-0.5]),min([Q0+currRange/2,0.5-2**-16]),numPoints)
    tRes = []
    
    for val in scanVec:
        tRes.append(getWithIQ([I0,val],qm,SA))
    
    if plotRes:
        pyplot.figure(Q_FIG_NUM)
        pyplot.plot(scanVec,tRes,label=str(I0))

    minVal = min(tRes)
    return minVal,scanVec[tRes.index(minVal)]


print("Make sure the Sweep type rule is \"Best speed\"!")
#setup
rm = visa.ResourceManager()
res_list = rm.list_resources()
MG = rm.open_resource(MG_address)
setupMG(MG, LOFreq, LOAmp)
print("Waiting %f seconds for warm-up" % warmup_time)
sleep(warmup_time)
SA = rm.open_resource("GPIB0::24::INSTR")
qm = open_qm()

with program() as prog:
    with infinite_loop_():
        play("pulse", "RR1")
        play("pulse", "RR2")

job = qm.execute(prog, experimental_calculations=False)

getWithIQ([0.0,0.0],qm,SA) #send a sequence in order to have a trigger before setting SA marker to max
setupSpectrumAnalyzer(SA, LOFreq)


print("LOFreq = %f, LOAmp = %f" % (LOFreq,LOAmp))
currMin = 100.0 #minimal transmission, start with a high value
currRange = 0.48#0.1#0.98#0.80  #range to scan around the minima
minimum = -90#Stop at this value
numPoints = 16  #number of points
I0 = 0.0
Q0 = 0.0
start = time.time()
# while currMin>minimum and currRange>=16./2**16:
#     minTI, I0 = findMinI(I0,Q0,currRange,numPoints,qm,SA,plotFigs) #scan I
#     currMin, Q0 = findMinQ(I0,Q0,currRange,numPoints,qm,SA,plotFigs) #Scan Q
#     print ("Range = %f, I0 = %f, Q0 = %f, currMin = %f " % (currRange,I0,Q0,currMin))
#     currRange = currRange/2
ret = optimize.minimize(getWithIQ, x0=[I0,Q0], method="Nelder-Mead", args=(qm, SA, True),options={"xatol":1e-4,"fatol":2,"disp":True,
    "initial_simplex":np.array([[-0.02,0.02],[0.02,0.02],[0,-0.02]])})
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
        drifts.append(float(SA.query(":CALC:MARK:Y?;")))
        sleep(dt)
        SA.write(":TRAC:TYPE AVER")  # restart average


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


if measure_drift:
    pyplot.figure()
    pyplot.plot(arange(0,measure_time,dt),drifts)
    pyplot.ylabel("Power [dBm]")
    pyplot.xlabel("Time [sec.]")
    pyplot.draw()

pyplot.show()


