from time import sleep
import visa
from .instrument import Instrument


class M9347A_MG(Instrument):
    """"A class for controlling Keysight E8241A M9347A dual DDS"""

    def __init__(self, address):
        """Initizalize the instrument, using a given VISA address (address[0]) and synthisizer number (address[1])"""
        rm = visa.ResourceManager()
        self.MG = rm.open_resource(address[0])
        self.synth_num = address[1]
        self.update_functions = {
            "freq": lambda f: self.setup_MG(freq=f, set_on=False),
            "power": lambda p: self.setup_MG(power=p, set_on=False),
            "on": lambda on: self.set_on(on)
        }

    def setup_MG(self, freq=None, power=None, set_on=True):
        """Set the MG to a given frequency (in MHz) and power (in dBm). If one of them is None don't set it.
        if set_on is True set power on"""

        if freq is not None:
            self.MG.write(':DDS%d:FREQ %fe6' % (self.synth_num, freq))
            sleep(0.100)
        if power is not None:
            self.MG.write(':DDS%d:POW %f' % (self.synth_num, power))
            sleep(0.100)
        if set_on:
            self.MG.write(":DDS%d:OUTP 1" % (self.synth_num))
            sleep(0.100)

    def set_on(self, on=True):
        """Set MG on/off"""
        if on:
            self.MG.write(":DDS%d:OUTP 1" % (self.synth_num))
        else:
            self.MG.write(":DDS%d:OUTP 0" % (self.synth_num))
        sleep(0.100)

    def update_property(self, property, value):
        """Update the given property of the instrument to the given value"""

        if property not in self.update_functions:
            raise Exception("M9347A_MG.update_property: Property is not supported")

        self.update_functions[property](value)
