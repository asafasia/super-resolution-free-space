#Find optimal calibration parameters for IQ mixer imbalance using a model of phase and amplitude imbalance
#Written by Naftali Kirsh 5/20

from qm.QuantumMachinesManager import QuantumMachinesManager
from qm.qua import *
import OPX.config_generator as config_generator
import numpy as np
from matplotlib import pyplot as plt
from time import sleep
import instruments_py27.spectrum_analyzer as SA
import instruments_py27.anritsu as MG
from scipy import optimize

#parameters

#instruments
mg_address = "GPIB0::5::INSTR" #"GPIB0::7::INSTR"
sa_address = "GPIB0::24::INSTR"

#OPX ports to which the I,Q ports of the IQ mixer are connected
I_channel = 1
Q_channel = 3

#offset
I_offset = -0.02277855
Q_offset = -0.01944626

#LO
lo_freq = 5000e6
lo_amp = 18.0
#IF
if_freq = 0e6#20e6

#IQ response
num_points_IQ = 101 #angular points to test response
response_amp = 0.1 #I,Q amplitude

#SBM
ampl = 0.01
pulse_length = 100000

#OPX config
cg = config_generator.ConfigGenerator(output_offsets={I_channel:I_offset,Q_channel:Q_offset},input_offsets={1:0.0, 2:0.0})
cg.add_mixer("mixer",{(lo_freq, if_freq):[1.0,0.0,0.0,1.0]})
cg.add_mixed_input_element("mixer",lo_freq+if_freq,lo_freq,I_channel,Q_channel,"mixer")
cg.add_constant_waveform("const", ampl)
cg.add_constant_waveform("zeros", 0.0)
cg.add_mixed_control_pulse("const_pulse",pulse_length,["const","zeros"])
cg.add_operation("mixer", "control_const", "const_pulse")
cg.add_mixed_control_pulse("zero_pulse",pulse_length,["zeros","zeros"])
cg.add_operation("mixer", "control_zero", "zero_pulse")

#---functions---
def getWithIQ(IQ, qm, sa, element_name, verbose=False):
    """Sets DAC output to I=IQ[0] and Q=IQ[1] and measures with spectrum analyzer"""
    if verbose:
        print("Setting I=%f, Q=%f" % (IQ[0],IQ[1]))
    qm.set_output_dc_offset_by_element(element_name,"I",float(IQ[0]))
    qm.set_output_dc_offset_by_element(element_name,"Q",float(IQ[1]))
    sleep(0.5)#sleep(0.2)
    sa.set_marker_max()
    t = sa.get_marker()

    if verbose:
        print("Transmitted power is %f dBm" % t)
    return t

def plot_ellipse(plt, theta, volt, title, figs=[None, None]):
    plt.figure(figs[0])
    plt.polar(theta, volt)
    plt.title(title)

    plt.figure(figs[1])
    plt.plot(theta / np.pi / 2, volt)
    plt.xlabel("$\Theta/2\pi$")
    plt.ylabel("Voltage ($\sqrt{10^{P/10}\cdot 50}$)")
    plt.title(title)

def model_corr_mat(g, phi):
    """See my OneNote documentation (Naftali)"""
    scaling_m = np.array([[g, 0], [0, 1]])
    rot_m = (1 / (np.cos(phi / 2) ** 2 - np.sin(phi / 2) ** 2)) * np.array(
        [[np.cos(phi / 2), -np.sin(phi / 2)], [-np.sin(phi / 2), np.cos(phi / 2)]])
    mm = scaling_m @ rot_m

    return mm.flatten()

def check_with_model_corr(corr_params, qm, mixer_name, sa, lo_freq, if_freq, sleep_time=1.0, averaging = True):
    qm.set_mixer_correction(mixer_name, int(if_freq), int(lo_freq), tuple(model_corr_mat(*corr_params)))
    if averaging:
        sa.restart_averaging()
    sleep(sleep_time)
    neg = sa.get_marker()
    print("setting g=%f, phi=%f. negative=%f" % (corr_params[0],corr_params[1], neg))
    return neg

#---QM programs---
#IQ response
with program() as IQ_response_prog:
    with infinite_loop_():
        play("control_zero","mixer")

#SBM
with program() as SBM_prog:
    with infinite_loop_():
        play("control_const","mixer")


#----main programs---

#setup
plt.ion()

mg = MG.Anritsu_MG(mg_address)
mg.setup_MG(lo_freq/1e6,lo_amp)
#init spectrum analyzer
sa = SA.N9010A_SA(sa_address)
sa.setup_spectrum_analyzer(center_freq=lo_freq/1e6,span=1,BW=100,points=1)
sa.setup_averaging(False)


qmManager = QuantumMachinesManager()
qm = qmManager.open_qm(cg.get_config())

#----IQ response----
job = qm.execute(IQ_response_prog, experimental_calculations=False)

#get response
theta = np.linspace(0,2*np.pi,num_points_IQ)
power = np.zeros(theta.shape)
I = response_amp*np.cos(theta)
Q = response_amp*np.sin(theta)

print("Getting response...")
getWithIQ([I_offset,Q_offset],qm,sa,"mixer") #to prevent problems
for idx in range(len(theta)):
    iq = [I[idx]+I_offset,Q[idx]+Q_offset]
    power[idx] = getWithIQ(iq, qm, sa, "mixer")

volt = np.sqrt(10**(power/10.0)*50)

#plot
plot_ellipse(plt, theta, volt, "Uncalibrated",[1,2])

#Extract model parameters
theta_m = np.array([0,np.pi,np.pi/2,3*np.pi/2,np.pi/4,7*np.pi/4])
power_m = np.zeros(theta_m.shape)
I_m = response_amp*np.cos(theta_m)
Q_m = response_amp*np.sin(theta_m)
print("Getting response for model...")
getWithIQ([I_offset,Q_offset],qm,sa,"mixer") #to prevent problems
for idx in range(len(theta_m)):
    iq = [I_m[idx]+I_offset,Q_m[idx]+Q_offset]
    power_m[idx] = getWithIQ(iq,qm,sa,"mixer")

volt_m = np.sqrt(10**(power_m/10.0)*50)
g_I = np.mean([volt_m[0],volt_m[1]])
g_Q = np.mean([volt_m[2],volt_m[3]])
x = volt_m[4]**2-volt_m[5]**2
phi = np.arcsin(x/(2*g_I*g_Q))
model = np.sqrt(g_I**2*np.cos(theta)**2+g_Q**2*np.sin(theta)**2+g_I*g_Q*np.sin(phi)*np.sin(2*theta))
plt.figure(1)
plt.polar(theta,model,'k')
plt.legend(["Measurement","Model"])

#inverse transformation
scaling_m = np.array([[g_Q/g_I,0],[0,1]])
rot_m = (1/(np.cos(phi/2)**2-np.sin(phi/2)**2))*np.array([[np.cos(phi/2),-np.sin(phi/2)],[-np.sin(phi/2),np.cos(phi/2)]])

print("Getting response with inverse transformation...")
getWithIQ([I_offset,Q_offset],qm,sa,"mixer") #to prevent problems
for idx in range(len(theta)):
    iq = scaling_m@rot_m@([I[idx],Q[idx]])+[I_offset,Q_offset]
    power[idx] = getWithIQ(iq,qm,sa,"mixer")

volt = np.sqrt(10**(power/10.0)*50)

#plot
plot_ellipse(plt, theta, volt, "Calibarted",[7,8])

#---SBM calibration---
getWithIQ([I_offset,Q_offset],qm,sa,"mixer")  #reset offsets
sa.setup_spectrum_analyzer(center_freq=(lo_freq+if_freq)/1e6,span=10e3,BW=10,points=10000)
# sa.setup_spectrum_analyzer(center_freq=(lo_freq-if_freq)/1e6,span=10e3,BW=10,points=1000)
job = qm.execute(SBM_prog, experimental_calculations=False)
sleep(1.0)
sa.set_marker_max()
qm.set_mixer_correction("mixer", int(if_freq), int(lo_freq), tuple((scaling_m@rot_m).flatten()))
g = g_Q/g_I
eps = 0.2
ret = optimize.minimize(check_with_model_corr, x0=[g,phi], method="Nelder-Mead", args=(qm, "mixer", sa, lo_freq, if_freq),
                        options = {"xatol": 1e-4, "fatol": 2,
                                    "initial_simplex": np.array([[np.max([g-eps,0]), phi+eps], [np.min([g+eps,1]), phi+eps], [g, phi-eps]])})

print("Setting matrix to optimal:")
qm.set_mixer_correction("mixer", int(if_freq), int(lo_freq), tuple(model_corr_mat(*ret.x)))

#plot calibrated model
g_Q_cal = g_Q
g_I_cal = ret.x[0]*g_Q
phi_cal = ret.x[1]
model_cal = np.sqrt(g_I_cal**2*np.cos(theta)**2+g_Q_cal**2*np.sin(theta)**2+g_I_cal*g_Q_cal*np.sin(phi_cal)*np.sin(2*theta))
plt.figure(1)
plt.polar(theta,model_cal,'--')
plt.legend(["Measurement","Model","Optimized model"])

#turn MG off
mg.set_on(False)


