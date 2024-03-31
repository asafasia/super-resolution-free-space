from pprint import pprint
from qm import QuantumMachinesManager
from qm.qua import *
import OPX.config_generator as config_generator

# parameters

lo_freq = 5150e9
lo_offset = 0
f_d = lo_freq - lo_offset
lo_power = 0
if_freq = lo_freq - f_d

I_input_offset = 0
Q_input_offset = 0
I_channel = 1
Q_channel = 2
I_output_offset = 0
Q_output_offset = 0

pulse_length = 1000
ampl = 0.2

# create config

cg = config_generator.ConfigGenerator(
    output_offsets={I_channel: I_output_offset,
                    Q_channel: Q_output_offset}
)

cg.add_mixed_input_element("output", lo_freq + if_freq, lo_freq, I_channel, Q_channel, "mixer1")
cg.add_constant_waveform("const", ampl)
cg.add_mixed_control_pulse("const", pulse_length, ["const", "const"])
cg.add_operation("output", "output", "const")

# create program

with program() as prog:
    with infinite_loop_():
        play("output", "output", None)

# run program

qmManager = QuantumMachinesManager("192.168.137.43", 9510)  # QuantumMachinesManager()
config = cg.get_config()
pprint(config)
qm = qmManager.open_qm(config)
pending_job = qm.queue.add_to_start(prog)

