"""Use shrinking 1d I,Q scans to find minimum in I,Q plane
Written by Naftali 1/18 , uses functions from Yoni's IQMixerMap"""

import time
from time import sleep
from scipy import linspace
from qm.QuantumMachinesManager import QuantumMachinesManager
from qm.qua import *


class IQ_min_finder:

    def open_qm(self, I_port, Q_port):
        qmManager = QuantumMachinesManager(host="192.168.137.15")

        return qmManager.open_qm({
            "version": 1,
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

    def __init__(self, SA, verbose=False, I_port=1, Q_port=2):

        self.I_FIG_NUM = 1
        self.Q_FIG_NUM = 2

        self.verbose = verbose
        self.SA = SA
        # setup qm
        self.qm = self.open_qm(I_port, Q_port)

        with program() as prog:
            with infinite_loop_():
                play("pulse", "RR1")
                play("pulse", "RR2")

        job = self.qm.execute(prog, experimental_calculations=False)

    def getWithIQ(self, IQ):
        """Sets DAC output to I=IQ[0] and Q=IQ[1] and measures with spectrum analyzer"""
        if self.verbose:
            print("Setting I=%f, Q=%f" % (IQ[0], IQ[1]))
        self.qm.set_dc_offset_by_qe("RR1", "port", float(IQ[0]))
        self.qm.set_dc_offset_by_qe("RR2", "port", float(IQ[1]))
        sleep(0.1)

        t = self.SA.get_marker()

        if self.verbose:
            print("Transmitted power is %f dBm" % t)
        return t

    def findMinI(self, I0, Q0, currRange, numPoints, plotRes=False):
        """scans numPoints +/-currRange/2 around I0 with a constant Q0
        returns the I which gave the minimal transmission
        plot scan if plotRes = True
        """
        scanVec = linspace(max([I0 - currRange / 2, -0.5]), min([I0 + currRange / 2, 0.5 - 2 ** -16]), numPoints)
        tRes = []

        for val in scanVec:
            tRes.append(self.getWithIQ([val, Q0]))

        if plotRes:
            self.pyplot.figure(self.I_FIG_NUM)
            self.pyplot.plot(scanVec, tRes, label=str(Q0))

        minVal = min(tRes)
        return minVal, scanVec[tRes.index(minVal)]

    def findMinQ(self, I0, Q0, currRange, numPoints, plotRes=False):
        """scans numPoints +/-currRange/2 around Q0 with a constant I0
        returns the Q which gave the minimal transmission
        plot scan if plotRes = True
        """
        scanVec = linspace(max([Q0 - currRange / 2, -0.5]), min([Q0 + currRange / 2, 0.5 - 2 ** -16]), numPoints)
        tRes = []

        for val in scanVec:
            tRes.append(self.getWithIQ([I0, val]))

        if plotRes:
            self.pyplot.figure(self.Q_FIG_NUM)
            self.pyplot.plot(scanVec, tRes, label=str(I0))

        minVal = min(tRes)
        return minVal, scanVec[tRes.index(minVal)]

    def find_IQ_min(self, I0, Q0, range, lo_freq, minimum=-90.0, plotFigs=False):

        print(
            "Starting calibration. Make sure spectrum analyzer averaging is off and sweep type rules are \"best speed\"!")

        if plotFigs:
            import matplotlib.pyplot as pyplot
            self.pyplot = pyplot
            self.pyplot.ion()

        self.getWithIQ([0.0, 0.0])  # send a sequence in order to have a trigger before setting SA marker to max
        self.SA.setup_spectrum_analyzer(center_freq=lo_freq, span=1.0, BW=100.0, points=1)
        self.SA.set_marker_max()
        currMin = 100.0  # minimal transmission, start with a high value
        currRange = range  # range to scan around the minima
        numPoints = 16  # number of points
        start = time.time()
        while currMin > minimum and currRange >= 16. / 2 ** 16:
            minTI, I0 = self.findMinI(I0, Q0, currRange, numPoints, plotFigs)  # scan I
            currMin, Q0 = self.findMinQ(I0, Q0, currRange, numPoints, plotFigs)  # Scan Q
            print("Range = %f, I0 = %f, Q0 = %f, currMin = %f " % (currRange, I0, Q0, currMin))
            currRange = currRange / 2
        end = time.time()

        print("Elapsed time is %f seconds" % (end - start))

        if plotFigs:
            self.pyplot.figure(self.I_FIG_NUM)
            self.pyplot.xlabel("I [pixels]")
            self.pyplot.ylabel("Transmitted power [dBm]")
            self.pyplot.legend()
            self.pyplot.draw()
            self.pyplot.figure(self.Q_FIG_NUM)
            self.pyplot.xlabel("Q [pixels]")
            self.pyplot.ylabel("Transmitted power [dBm]")
            self.pyplot.legend()
            self.pyplot.draw()
            self.pyplot.show()

        return (I0, Q0, currMin)
