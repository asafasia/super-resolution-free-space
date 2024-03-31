from abc import ABCMeta, abstractmethod

class Instrument:
    """An abstract class for an instrument"""

    __metaclass__ = ABCMeta

    @abstractmethod
    def update_property(self, property, value):
        """Update the given property of the instrument to the given value"""
        pass