from .instrument import Instrument
import subprocess
from os.path import join
import inspect


class LDA:
    """"A class for controlling LabBrick digital attenuator"""
    LDA_FILES_FOLDER = r"X:\CodeVault\PythonLibs\instruments_py27\LDA_files"
    LDA_PROGRAM_NAME = r"LDA64Test.exe"

    def __init__(self, device_number):
        """Initizalize the instrument"""
        self.device_number = device_number
        self.update_functions = {
            "attenuation": lambda a: self.set_attenuation(a)
        }

    def set_attenuation(self, attenuation):
        """Set attenuation for the device"""
        subprocess.call(
            [join(self.LDA_FILES_FOLDER, self.LDA_PROGRAM_NAME), "-d", "%d" % self.device_number, "1", "-b", "-a",
             "%f" % attenuation])

    def update_property(self, property, value):
        """Update the given property of the instrument to the given value"""

        if property not in self.update_functions:
            raise Exception("LDA.update_property: Property is not supported")

        self.update_functions[property](value)
