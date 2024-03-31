"""Measure noise
Written by Naftali 6/20"""
import numpy as np
from qm.QuantumMachinesManager import QuantumMachinesManager
from qm.qua import *
import OPX.config_generator as config_generator
import instruments_py27.anritsu as MG
from matplotlib import pyplot as plt
from scipy.optimize import least_squares


#-----------Parameters-------------

repetitions = 50000
verbose = False


#NOTE: the pulse doesn't really needs to be sent since we measure noise
#OPX ports to which the I,Q ports of the IQ mixer are connected [not really used]
I_channel = 3
Q_channel = 1
I_readout_channel = 1
Q_readout_channel = 2

#offset
I_offset = -0.01583184
Q_offset = -0.02170017

lo_freq = 4250e6
if_freq = 100e6#0.0
if_freq2 = if_freq+4.7e6


#Pulse
ampl = 0.0
pulse_length = 10000

#readout
trigger_delay = 0
trigger_length = 10

#OPX config
cg = config_generator.ConfigGenerator(output_offsets={I_channel:I_offset,Q_channel:Q_offset},input_offsets={1:0.1958, 2:0.193}) #input_offsets={1:0.0, 2:0.0}
cg.add_mixer("mixer1",{(lo_freq, if_freq):[1.0,0.0,0.0,1.0],(lo_freq, if_freq2):[1.0,0.0,0.0,1.0]})
cg.add_mixed_readout_element("mixer",lo_freq+if_freq,lo_freq,I_channel,Q_channel,{"out_I":I_readout_channel, "out_Q":Q_readout_channel},"mixer1",200)
cg.add_mixed_readout_element("mixer2",lo_freq+if_freq2,lo_freq,I_channel,Q_channel,{"out_I":I_readout_channel, "out_Q":Q_readout_channel},"mixer1",200)
#readout
cg.add_constant_waveform("const", ampl)
cg.add_constant_waveform("zeros", 0.0)
cg.add_integration_weight("simple_cos", [1.0]*(pulse_length//4), [0.0]*(pulse_length//4))
cg.add_integration_weight("simple_sin", [0.0]*(pulse_length//4), [1.0]*(pulse_length//4))
cg.add_mixed_measurement_pulse("const_readout",pulse_length , ["const","zeros"],
                               {"simple_cos":"simple_cos", "simple_sin":"simple_sin"},
                               cg.TriggerType.RISING_TRIGGER, trigger_delay, trigger_length)
cg.add_operation("mixer", "readout", "const_readout")
cg.add_operation("mixer2", "readout", "const_readout")


#measurement program
with program() as measurement_prog:
    II = declare(fixed)
    IQ = declare(fixed)
    QI = declare(fixed)
    QQ = declare(fixed)
    II2 = declare(fixed)
    IQ2 = declare(fixed)
    QI2 = declare(fixed)
    QQ2 = declare(fixed)
    rep = declare(int)

    with for_(rep, 0, rep < repetitions, rep + 1):
        # measure("readout", "mixer", "samples",
        #         ("simple_cos", "out_I", II), ("simple_sin", "out_I", IQ),
        #         ("simple_cos", "out_Q", QI), ("simple_sin", "out_Q", QQ))
        measure("readout", "mixer", None,
                ("simple_cos", "out_I", II), ("simple_sin", "out_I", IQ),
                ("simple_cos", "out_Q", QI), ("simple_sin", "out_Q", QQ))
        measure("readout", "mixer2", None,
                ("simple_cos", "out_I", II2), ("simple_sin", "out_I", IQ2),
                ("simple_cos", "out_Q", QI2), ("simple_sin", "out_Q", QQ2))
        # wait(5000, "mixer") #TODO: check if needed and how long?
        save(II, "II")
        save(IQ, "IQ")
        save(QI, "QI")
        save(QQ, "QQ")
        save(II2, "II2")
        save(IQ2, "IQ2")
        save(QI2, "QI2")
        save(QQ2, "QQ2")

#----Main program---
plt.ion()

#setup

qmManager = QuantumMachinesManager()
qm = qmManager.open_qm(cg.get_config())

#run program
job = qm.execute(measurement_prog, duration_limit=0, data_limit=0)
job.wait_for_all_results()
results = job.get_results()
print("Got results")


#analyze
# t = list(zip(*results.raw_results.input1))[0]
# data = [np.array(list(zip(*results.raw_results.input1))[1]),np.array(list(zip(*results.raw_results.input2))[1])]
# I_all = data[I_readout_channel-1]
# Q_all = data[Q_readout_channel-1]
II = np.array(list(zip(*results.variable_results.II))[1])
QI = np.array(list(zip(*results.variable_results.QI))[1])
IQ = np.array(list(zip(*results.variable_results.IQ))[1])
QQ = np.array(list(zip(*results.variable_results.QQ))[1])
II2 = np.array(list(zip(*results.variable_results.II2))[1])
QI2 = np.array(list(zip(*results.variable_results.QI2))[1])
IQ2 = np.array(list(zip(*results.variable_results.IQ2))[1])
QQ2 = np.array(list(zip(*results.variable_results.QQ2))[1])

# plt.figure(1)
# plt.plot(II,QI,'.')
# plt.axis('square')

I_p = II-QQ
Q_p = -QI-IQ
I_m = II+QQ
Q_m = IQ-QI

plt.figure(1)
plt.subplot(221)
plt.plot(I_p,Q_p,'.')
plt.xlabel(r"$I1_+$")
plt.ylabel(r"$Q1_+$")
plt.axis('square')
plt.subplot(222)
plt.plot(I_m,Q_m,'.')
plt.xlabel(r"$I1_-$")
plt.ylabel(r"$Q1_-$")
plt.axis('square')
plt.subplot(223)
plt.plot(I_p,I_m,'.')
plt.xlabel(r"$I1_+$")
plt.ylabel(r"$I1_-$")
plt.axis('square')
plt.subplot(224)
plt.plot(Q_p,Q_m,'.')
plt.xlabel(r"$Q1_+$")
plt.ylabel(r"$Q1_-$")
plt.axis('square')
plt.suptitle("IF frequency=%f MHz" % (if_freq/1e6))

I_p2 = II2-QQ2
Q_p2 = -QI2-IQ2
I_m2 = II2+QQ2
Q_m2 = IQ2-QI2

plt.figure(2)
plt.subplot(221)
plt.plot(I_p2,Q_p2,'.')
plt.xlabel(r"$I2_+$")
plt.ylabel(r"$Q2_+$")
plt.axis('square')
plt.subplot(222)
plt.plot(I_m2,Q_m2,'.')
plt.xlabel(r"$I2_-$")
plt.ylabel(r"$Q2_-$")
plt.axis('square')
plt.subplot(223)
plt.plot(I_p2,I_m2,'.')
plt.xlabel(r"$I2_+$")
plt.ylabel(r"$I2_-$")
plt.axis('square')
plt.subplot(224)
plt.plot(Q_p2,Q_m2,'.')
plt.xlabel(r"$Q2_+$")
plt.ylabel(r"$Q2_-$")
plt.axis('square')
plt.suptitle("IF frequency=%f MHz" % (if_freq2/1e6))


plt.figure(3)
plt.subplot(121)
plt.plot(I_p,I_m2,'.')
plt.xlabel(r"$I1_+$")
plt.ylabel(r"$I2_-$")
plt.axis('square')
plt.subplot(122)
plt.plot(Q_p,Q_m2,'.')
plt.xlabel(r"$Q1_+$")
plt.ylabel(r"$Q2_-$")
plt.axis('square')
plt.suptitle("Checking correlations between different modes")