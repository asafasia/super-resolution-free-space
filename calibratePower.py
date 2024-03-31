# Send constant pulse to calibrate output power
# Written by Naftali 1/21

from qm import QuantumMachinesManager
from qm.qua import *
import OPX.config_generator as config_generator
from matplotlib import pyplot as plt
# import instruments_py27.anritsu as MG
import instruments_py27.M9347A as M9347A_MG

from pprint import pprint

# import instruments_py27.E8241A as MG
# import instruments_py27.M9347A as MG

MG_class = M9347A_MG.M9347A_MG  # MG.Anritsu_MG
# MG_class = MG.E8241A_MG
# MG_class = MG.M9347A_MG
# MG_class = MG.Anritsu_MG
# -----------Parameters-------------

debug = False  # set True to measure the pulse with OPX inputs

# Local oscillator
mg_address = ("TCPIP0::DESKTOP-VT04ESJ::hislip1::INSTR",
              2)  # "GPIB0::5::INSTR"#"GPIB0::28::INSTR"# "TCPIP0::DESKTOP-VT04ESJ::hislip1::INSTR",1) #
# mg_address = "GPIB0::5::INSTR"
lo_freq = 5150e9  # 4582.8e6# 4160e6#f_d+lo_offset  5678.5e6##Hz
lo_offset = 100e6 # 135.8e6#150e6 # lo_freq-4068e6
f_d = lo_freq - lo_offset  # Hz, desired frequency 6150e6#
lo_power = 0.0  # 13.0#18.0 #dBm 16.0#

# SBM
if_freq = lo_freq - f_d  # Hz, SBM frequency is lo_freq-if_freq

# OPX

# input=readout channels
I_readout_channel = 1
Q_readout_channel = 2
I_input_offset = 0
Q_input_offset = 0
# output channels
I_channel = 1  # 1#
Q_channel = 2  # 2#
I_output_offset = 0.001  # 0.0055885  # -0.03058754
Q_output_offset = 0  # -0.007492  # 02864566

# Pulse
pulse_length = 1000  # ns
ampl = 0.34  # 3e-3#1e-3
repetitions = 10  # for debug
wait_time = 100  # *4 ns. for debug

# Readout
trigger_delay = 0
trigger_length = 10
time_of_light = 28 + 152  # ns. must be at least 28

# OPX config
cg = config_generator.ConfigGenerator(
    output_offsets={I_channel: I_output_offset,
                    Q_channel: Q_output_offset},
    input_offsets={I_readout_channel: I_input_offset,
                   Q_readout_channel: Q_input_offset}
)

cg.add_mixer("mixer1", {(lo_freq, if_freq): [1.0, 0.0, 0.0, 1.0]})

if debug:
    cg.add_mixed_readout_element("readout", lo_freq + if_freq, lo_freq, I_channel, Q_channel,
                                 {"out_I": I_readout_channel, "out_Q": Q_readout_channel}, "mixer1", time_of_light)
else:
    cg.add_mixed_input_element("output", lo_freq + if_freq, lo_freq, I_channel, Q_channel, "mixer1")

# Output / readout
cg.add_constant_waveform("const", ampl)
if debug:
    cg.add_integration_weight("simple_cos", [1.0] * (pulse_length // 4), [0.0] * (pulse_length // 4))
    cg.add_integration_weight("simple_sin", [0.0] * (pulse_length // 4), [1.0] * (pulse_length // 4))
    cg.add_mixed_measurement_pulse("const_readout", pulse_length, ["const", "const"],
                                   {"simple_cos": "simple_cos", "simple_sin": "simple_sin"},
                                   cg.TriggerType.RISING_TRIGGER, trigger_delay, trigger_length)
    cg.add_operation("readout", "readout", "const_readout")
else:
    cg.add_mixed_control_pulse("const", pulse_length, ["const", "const"])
    cg.add_operation("output", "output", "const")

# OPX measurement program
if debug:
    with program() as prog:
        rep = declare(int)

        with for_(rep, 0, rep < repetitions, rep + 1):
            measure("readout", "readout", "samples")
            wait(wait_time)
else:
    with program() as prog:
        with infinite_loop_():
            play("output", "output", None)

# ----------------main program---------------
# run
# turn MG on
# mg = MG_class(mg_address)
# mg.setup_MG(lo_freq / 1e6, lo_power)
#
qmManager = QuantumMachinesManager("192.168.137.43", 9510)  # QuantumMachinesManager()
config = cg.get_config()
# add trigger - TODO: using config_generator
if not debug:
    config["controllers"]["con1"]["digital_outputs"] = {}
    config["controllers"]["con1"]["digital_outputs"][1] = {}
    config["elements"]["output"]["digitalInputs"] = {
        "trigger1":
            {
                "port": ("con1", 1),
                "delay": 144,
                "buffer": 10
            }
    }
    config["pulses"]["const"]["digital_marker"] = "trigger"
    config["digital_waveforms"] = {}
    config["digital_waveforms"]["trigger"] = {"samples": [(1, 0)]}

qm = qmManager.open_qm(config)
pending_job = qm.queue.add_to_start(prog)
if debug:
    import numpy as np

    # get data
    job = pending_job.wait_for_execution()
    result_handles = job.result_handles
    result_handles.wait_for_all_values()
    print("Got results")
    s1 = result_handles.samples_input1.fetch_all()
    s2 = result_handles.samples_input2.fetch_all()
    # plot
    plt.figure()
    plt.plot(s1["timestamp"][1, :], np.mean(s1["value"], axis=0))
    plt.plot(s2["timestamp"][1, :], np.mean(s2["value"], axis=0))
    plt.show()
