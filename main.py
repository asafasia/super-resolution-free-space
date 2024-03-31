import numpy as np
import pyvisa
import visa
from matplotlib import pyplot as plt
from qm import QuantumMachinesManager

from instruments_py27.spectrum_analyzer import N9010A_SA

# rm = pyvisa.ResourceManager()
# print(rm)
# print(rm.list_resources())
# #
# my_instrument = rm.open_resource('USB0::0x0957::0x0B0B::MY47191316::INSTR')
#
# my_instrument.write(":FORM:DATA ASC,8")
#
# import keysight_ktrfsiggen


sa = N9010A_SA('USB0::0x0957::0x0B0B::MY47191316::INSTR')

sa.set_marker_max()
print(sa.get_marker())

