"""Test amplitude and phase relation for two sidebands"""

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

def test_amplitude_and_phase(qm, if_freqs, amp_factor, phase, M_i):
    """ Measure two sidebands of if_freqs with desired amplitude ration and phase difference (not including electrical delay)
    M_i is the demodulation calibration matrix

    returns: list of Fourier coefficients - (positive SB uncalibarted, negative SB uncalibarted, positive SB calibarted, negative SB uncalibarted)
             for each sideband.
    """

    # measurement program
    with program() as measurement_prog:
        z_rotation(phase, "SB2")
        play("control_const", "SB1")
        measure("readout" * amp(float(amp_factor)), "SB2", "samples")

    job = qm.execute(measurement_prog, duration_limit=0, data_limit=0)
    job.wait_for_all_results()
    results = job.get_results()
    # analyze
    t = list(zip(*results.raw_results.input1))[0][0:pulse_length]
    I = np.array(list(zip(*results.raw_results.input2))[1][0:pulse_length])
    Q = np.array(list(zip(*results.raw_results.input1))[1][0:pulse_length])
    freqs = np.fft.fftfreq(pulse_length, 1e-9)

    I_ = I - np.mean(I)
    Q_ = Q - np.mean(Q)
    s = I_ - 1j * Q_
    s = s - np.mean(s)
    f_s = np.fft.fft(s)
    IQ = np.array([I_, Q_])
    IQ2 = M_i @ IQ
    IQ2_c = IQ2[0, :] - 1j * IQ2[1, :]
    f_s2 = np.fft.fft(IQ2_c)

    ret = []
    for if_freq in if_freqs:
        idx_p = np.abs(freqs - if_freq).argmin()
        idx_n = np.abs(freqs + if_freq).argmin()
        c_p = f_s[idx_p]
        c_n = f_s[idx_n]
        c_p_cal = f_s2[idx_p]
        c_n_cal = f_s2[idx_n]
        ret.append((c_p, c_n, c_p_cal, c_n_cal))

    return ret


#--------------------------


#parameters

#instruments
mg_address = "GPIB0::7::INSTR"

#OPX ports to which the I,Q ports of the IQ mixer are connected
I_channel = 3
Q_channel = 1

#offset
I_offset = -0.01565542
Q_offset = -0.021652

#calibration matrix
g = 0.83460607
phi = 0.16009536


#LO
lo_freq = 5000e6
lo_amp = 18.0
#IF
if_freq = 20e6#20e6

#SBM
ampl = 0.01
pulse_length = 22000
pos_amp_factors = np.logspace(-2,0,20) #for positive sideband
phases = np.linspace(0,np.pi,20) #relative

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

#calibrate demodultaion with a single SB
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


ret = []
for amp_factor in pos_amp_factors:
    print("phase = 0, amp_factor=%f" % amp_factor)
    ret.append(test_amplitude_and_phase(qm, [if_freq], amp_factor, 0.0, M_i)[0])

rets = list(zip(*ret))
#plot
plt.figure()
plt.plot(np.abs(rets[1]),'*-')
plt.plot(np.abs(rets[3]),'*-')
plt.legend(["Uncalibrated","Calibrated"])
plt.ylabel("Negative SB amplitude")
plt.title("Negative SB amplitude")
plt.show()

plt.figure()
plt.plot(np.log10(pos_amp_factors),10*np.log10(np.abs(rets[0])/np.abs(rets[1])/pos_amp_factors),'*-')
plt.plot(np.log10(pos_amp_factors),10*np.log10(np.abs(rets[2])/np.abs(rets[3])/pos_amp_factors),'*-')
plt.xlabel("$\log_{10}$ (desired ratio)")
plt.ylabel("Positive SB amplitude/Negative SB amplitude/desired ratio [dB]")
plt.legend(["Uncalibrated","Calibrated"])
plt.title("Positive SB amplitude/Negative SB amplitude/desired ratio [dB]")
plt.show()

plt.figure()
plt.plot(np.log10(pos_amp_factors),np.angle(rets[0])-np.angle(rets[1]),'*-')
plt.plot(np.log10(pos_amp_factors),np.angle(rets[2])-np.angle(rets[3]),'*-')
plt.xlabel("$\log_{10}$ (desired ratio)")
plt.ylabel("Positive SB phase - Negative SB phase")
plt.legend(["Uncalibrated","Calibrated"])
plt.title("Positive SB phase - Negative SB phase")
plt.show()


ret = []
for phase in phases:
    print("phase = %f, amp_factor=1" % phase)
    ret.append(test_amplitude_and_phase(qm, [if_freq], 1, phase, M_i)[0])

rets = list(zip(*ret))
#plot
plt.figure()
plt.plot(np.abs(rets[1]),'*-')
plt.plot(np.abs(rets[3]),'*-')
plt.legend(["Uncalibrated","Calibrated"])
plt.ylabel("Negative SB amplitude")
plt.title("Negative SB amplitude")
plt.show()

plt.figure()
plt.plot(phases/np.pi,np.log10(np.abs(rets[0])/np.abs(rets[1])),'*-')
plt.plot(phases/np.pi,np.log10(np.abs(rets[2])/np.abs(rets[3])),'*-')
plt.xlabel(r"$\phi_{desired}/\pi$")
plt.ylabel("Positive SB amplitude/Negative SB amplitude [dB]")
plt.legend(["Uncalibrated","Calibrated"])
plt.title("Positive SB amplitude/Negative SB amplitude [dB]")
plt.show()

plt.figure()
phase0_uncal = np.angle(rets[0][0])-np.angle(rets[1][0])
phase0_cal = np.angle(rets[2][0])-np.angle(rets[3][0])
plt.plot(phases/np.pi,np.unwrap((np.angle(rets[0])-np.angle(rets[1])-phase0_uncal-phases)),'*-')
plt.plot(phases/np.pi,np.unwrap((np.angle(rets[2])-np.angle(rets[3])-phase0_cal-phases)),'*-')
plt.xlabel(r"$\phi_{desired}/\pi$")
plt.ylabel(r"$\phi_{pos.}-\phi_{neg.}-\phi_0-\phi_{desired}$")
# plt.ylabel(r"$\left(\phi_{pos.}-\phi_{neg.}-\phi_0-\phi_{desired}\right)/2\pi$")
plt.legend(["Uncalibrated","Calibrated"])
plt.title("Phase difference")
plt.show()



