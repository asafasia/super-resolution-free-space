from time import sleep
import visa
from .instrument import Instrument


class N9010A_SA:
    """"A class for controlling Agilent N9010A spectrum analyzer using GPIB"""

    def __init__(self, address, set_best_speed=True):
        """Initizalize the instrument, using a given VISA address"""
        rm = visa.ResourceManager()
        self.SA = rm.open_resource(address)
        self.SA.write(":FORM:DATA ASC,8")  # data formating = ASCII
        # turn on markers
        self.SA.write(":CALC:MARK1:STAT ON")
        if set_best_speed:
            self.SA.write("SWE:TYPE:AUTO:RUL SPE")  # set sweep type rules to "best speed"
        self.update_functions = {
            "center_freq": lambda f: self.setup_spectrum_analyzer(center_freq=f),
            "span": lambda s: self.setup_spectrum_analyzer(span=s),
            "BW": lambda bw: self.setup_spectrum_analyzer(BW=bw),
            "points": lambda p: self.setup_spectrum_analyzer(points=p),
            "averaging": lambda on: self.setup_averaging(on),
            "avg_count": lambda c: self.setup_averaging(True, c)
        }

    def setup_spectrum_analyzer(self, center_freq=None, span=None, BW=None, points=None):
        """"Set spectrum analyzer span (Hz), center frequency (MHz), IF BW (Hz) and number of points"""
        if center_freq is not None:
            self.SA.write(":FREQ:CENTER %fE6" % center_freq)
        if span is not None:
            self.SA.write(":FREQ:SPAN %f" % span)
        if BW is not None:
            self.SA.write(":BAND %f" % BW)
        if points is not None:
            self.SA.write(":SWE:POIN %d" % points)
        sleep(1.0)

    def setup_averaging(self, on, avg_count=100):
        """"Setup averaging. on=True/False. count=number of averages"""
        if on:
            self.SA.write(":TRAC:TYPE AVER")
            self.SA.write("AVER:COUN %d" % avg_count)
        else:
            self.SA.write("TRAC:TYPE WRIT")

    def restart_averaging(self):
        self.SA.write(":TRAC:TYPE AVER")

    def get_marker(self):
        """Get the value at the marker"""
        return float(self.SA.query(":CALC:MARK:Y?;"))

    def set_marker_max(self):
        """Put the marker at maximum"""
        self.SA.write(":CALC:MARK1:MAX;")

    def set_marker_position(self, freq):
        """Put the marker at the given position [MHz]"""
        self.SA.write(":CALC:MARK1:X %fE6" % freq)

    def get_data(self):
        """Get the traca data as text with pairs of frequency,power [dBm]"""
        return (self.SA.query("CALC:DATA?"))

    def update_property(self, property, value):
        """Update the given property of the instrument to the given value"""

        if property not in self.update_functions:
            raise Exception("N9010A_SA.update_property: Property is not supported")

        self.update_functions[property](value)
