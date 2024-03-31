"""Generate positive and negative sidebands with a given phase difference and amplitude factor"""

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
I_offset = -0.01642523
Q_offset = -0.02274586

#calibration matrix
g = 0.83376476
phi = 0.16533382


#LO
lo_freq = 5000e6
lo_amp = 18.0
#IF
if_freq = 20e6#20e6

#SBM
ampl = 0.01
amp_factor = 0.0 #for positive sideband
pulse_length = 100000
phase = 0.0 #relative

#OPX config
cg = config_generator.ConfigGenerator(output_offsets={I_channel:I_offset,Q_channel:Q_offset},input_offsets={1:0.0, 2:0.0})
cg.add_mixer("mixer1",{(lo_freq, if_freq):[1.0,0.0,0.0,1.0]})
cg.add_mixer("mixer2",{(lo_freq, if_freq):[1.0,0.0,0.0,1.0]})
cg.add_mixed_input_element("SB1",lo_freq+if_freq,lo_freq,I_channel,Q_channel,"mixer1")
cg.add_constant_waveform("const", ampl)
cg.add_constant_waveform("zeros", 0.0)
cg.add_mixed_control_pulse("const_pulse",pulse_length,["const","zeros"])
cg.add_operation("SB1", "control_const", "const_pulse")
cg.add_mixed_input_element("SB2",lo_freq+if_freq,lo_freq,I_channel,Q_channel,"mixer2")
cg.add_operation("SB2", "control_const", "const_pulse")

#SBM program
with program() as SBM_prog:
    z_rotation(phase,"SB2")
    with infinite_loop_():
        play("control_const","SB1")
        play("control_const"*amp(amp_factor),"SB2")
        align("SB1","SB2")

#----main programs---

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

#run program
job = qm.execute(SBM_prog, experimental_calculations=False)