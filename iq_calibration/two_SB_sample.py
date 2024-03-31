"""Generate positive and negatice sidebands. Sample using OPX"""

from qm.QuantumMachinesManager import QuantumMachinesManager
from qm.qua import *
import OPX.config_generator as config_generator
import numpy as np
from time import sleep
import instruments_py27.anritsu as MG
from matplotlib import pyplot as plt

#-----------functions------------
def model_corr_mat(g, phi):
    """See my OneNote documentation (Naftali)"""
    scaling_m = np.array([[g, 0], [0, 1]])
    rot_m = (1 / (np.cos(phi / 2) ** 2 - np.sin(phi / 2) ** 2)) * np.array(
        [[np.cos(phi / 2), -np.sin(phi / 2)], [-np.sin(phi / 2), np.cos(phi / 2)]])

    return scaling_m @ rot_m
#--------------------------


#parameters

#instruments
mg_address = "GPIB0::7::INSTR"

#OPX ports to which the I,Q ports of the IQ mixer are connected
I_channel = 3
Q_channel = 1

#offset
I_offset = -0.01583184
Q_offset = -0.02170017

#calibration matrix
g = 0.83463565
phi = 0.16016212

#LO
lo_freq = 5000e6
lo_amp = 18.0
#IF
if_freq = 20e6#20e6

#SBM
ampl = 0.01
pulse_length = 22000
neg_amp_factor = 1.0 #for negative sideband
pos_amp_factor = 0.0 #for positive sideband
phase = 0.0 #relative

#readout
trigger_delay = 0
trigger_length = 10

#OPX config
cg = config_generator.ConfigGenerator(output_offsets={I_channel:I_offset,Q_channel:Q_offset},input_offsets={1:0.0, 2:0.0})
cg.add_mixer("mixer1",{(lo_freq, if_freq):[1.0,0.0,0.0,1.0]})
cg.add_mixer("mixer2",{(lo_freq, if_freq):[1.0,0.0,0.0,1.0]})
cg.add_mixed_input_element("SB1",lo_freq+if_freq,lo_freq,I_channel,Q_channel,"mixer1")
cg.add_constant_waveform("const", ampl)
cg.add_constant_waveform("zeros", 0.0)
cg.add_mixed_control_pulse("const_pulse",pulse_length,["const","zeros"])
cg.add_operation("SB1", "control_const", "const_pulse")
# cg.add_mixed_input_element("SB2",lo_freq+if_freq,lo_freq,I_channel,Q_channel,"mixer2")
cg.add_mixed_readout_element("SB2",lo_freq+if_freq,lo_freq,I_channel,Q_channel,{"out_I":2, "out_Q":1},"mixer2",200)
cg.add_operation("SB2", "control_const", "const_pulse")
#readout
cg.add_integration_weight("simple_cos", [1.0]*(pulse_length//4), [0.0]*(pulse_length//4))
cg.add_integration_weight("simple_sin", [0.0]*(pulse_length//4), [1.0]*(pulse_length//4))
cg.add_mixed_measurement_pulse("const_readout",pulse_length , ["const","zeros"],
                               {"simple_cos":"simple_cos", "simple_sin":"simple_sin"},
                               cg.TriggerType.RISING_TRIGGER, trigger_delay, trigger_length)
cg.add_operation("SB2", "readout", "const_readout")

#measurement program - single SB
with program() as SSB_measurement_prog:
    II = declare(fixed)
    IQ = declare(fixed)
    QI = declare(fixed)
    QQ = declare(fixed)
    rep = declare(int)

    play("control_const", "SB1")
    measure("readout"*amp(0.0), "SB2", "samples_SSB")

#measurement program
with program() as measurement_prog:
    II = declare(fixed)
    IQ = declare(fixed)
    QI = declare(fixed)
    QQ = declare(fixed)
    rep = declare(int)

    z_rotation(phase, "SB2")

    with for_(rep, 0, rep < 1, rep + 1):
        play("control_const"*amp(neg_amp_factor), "SB1")
        measure("readout"*amp(pos_amp_factor), "SB2", "samples",
                ("simple_cos", "out_I", II), ("simple_sin", "out_I", IQ),
                ("simple_cos", "out_Q", QI), ("simple_sin", "out_Q", QQ))
        wait(10, "SB2")
        save(II, "II")
        save(IQ, "IQ")
        save(QI, "QI")
        save(QQ, "QQ")
        align("SB1", "SB2")

#----main programs---
plt.ion()
plt.rcParams["font.size"] = "20"
#setup
mg = MG.Anritsu_MG(mg_address)
mg.setup_MG(lo_freq/1e6,lo_amp)


qmManager = QuantumMachinesManager()
qm = qmManager.open_qm(cg.get_config())

#set correction matrices
qm.set_mixer_correction("mixer1", int(if_freq), int(lo_freq), tuple(model_corr_mat(g,phi).flatten())) #negatice sideband
m_pos = model_corr_mat(g,phi)@(np.array([[1,0],[0,-1]]))
qm.set_mixer_correction("mixer2", int(if_freq), int(lo_freq),
                        tuple(m_pos.flatten())) #positive sideband

#calibrate with single SB
print("Running calibration program")
job = qm.execute(SSB_measurement_prog, duration_limit=0, data_limit=0)
job.wait_for_all_results()
results = job.get_results()
print("Got results")
# analyze and plot
t = list(zip(*results.raw_results.input1))[0][0:pulse_length]
I_c = np.array(list(zip(*results.raw_results.input2))[1][0:pulse_length])
Q_c = np.array(list(zip(*results.raw_results.input1))[1][0:pulse_length])
s_c = I_c-1j*Q_c
s_c = s_c-np.mean(s_c)
f_s_c = np.fft.fft(s_c)
freqs = np.fft.fftfreq(pulse_length,1e-9)

plt.figure()
plt.plot(freqs/1e6,20*np.log10(np.abs(f_s_c)))
plt.xlabel("Frequency [MHz]")
plt.ylabel(r"$20\log_{10}\left(|F(s(t))|\right)$")
plt.title("Single sideband - uncalibrated")
plt.show()

#calibration
print("Calculating calibration matrix")
idx_p = np.abs(freqs-if_freq).argmin()
idx_n = np.abs(freqs+if_freq).argmin()
m_II = np.real(f_s_c[idx_p]+f_s_c[idx_n])
m_QI = -np.imag(f_s_c[idx_p] + f_s_c[idx_n])
m_IQ = -np.imag(f_s_c[idx_p]-f_s_c[idx_n])
m_QQ = -np.real(f_s_c[idx_p]-f_s_c[idx_n])
M_i = 1/(m_II*m_QQ-m_IQ*m_QI)*np.array([[m_QQ,-m_IQ],[-m_QI,m_II]])

I_c_ = I_c -np.mean(I_c)
Q_c_ = Q_c -np.mean(Q_c)
IQ_c = np.array([I_c_,Q_c_])
IQ2_c = M_i@IQ_c
IQ2_c_complex = IQ2_c[0,:]-1j*IQ2_c[1,:]
f_s2_c = np.fft.fft(IQ2_c_complex)
plt.figure()
plt.plot(freqs/1e6,20*np.log10(np.abs(f_s2_c)))
plt.xlabel("Frequency [MHz]")
plt.ylabel(r"$20\log_{10}\left(|F(s(t))|\right)$ - corrected")
plt.title("Single sideband - calibrated")
plt.show()

#run program
job = qm.execute(measurement_prog, duration_limit=0, data_limit=0)
job.wait_for_all_results()
results = job.get_results()
print("Got results")
# analyze and plot
t = list(zip(*results.raw_results.input1))[0][0:pulse_length]
I = np.array(list(zip(*results.raw_results.input2))[1][0:pulse_length])
Q = np.array(list(zip(*results.raw_results.input1))[1][0:pulse_length])
s = I-1j*Q
s = s-np.mean(s)
f_s = np.fft.fft(s)
freqs = np.fft.fftfreq(pulse_length,1e-9)
plt.figure()
plt.plot(freqs/1e6,20*np.log10(np.abs(f_s)))
plt.xlabel("Frequency [MHz]")
plt.ylabel(r"$20\log_{10}\left(|F(s(t))|\right)$")
plt.title("Uncalibrated")
plt.show()

I_ = I -np.mean(I)
Q_ = Q -np.mean(Q)
IQ = np.array([I_,Q_])
IQ2 = M_i@IQ
IQ2_c = IQ2[0,:]-1j*IQ2[1,:]
f_s2 = np.fft.fft(IQ2_c)
plt.figure()
plt.plot(freqs/1e6,20*np.log10(np.abs(f_s2)))
plt.xlabel("Frequency [MHz]")
plt.ylabel(r"$20\log_{10}\left(|F(s(t))|\right)$ - corrected")
plt.title("Calibrated")
plt.show()