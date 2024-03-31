"""A class for generating a QM config
#Written by Naftali Kirsh 11/19, 5/22
# IN PROGRESS
"""

from enum import Enum


class ConfigGenerator:
    """A generator for config. Currently supports a single controller"""

    # number of input and output channels
    NUM_OUTPUTS = 10
    NUM_INPUTS = 2

    class TriggerType(Enum):
        RISING_TRIGGER = 0
        FALLING_TRIGGER = 1

    def __init__(
            self,
            output_offsets=dict(zip(range(1, NUM_OUTPUTS + 1), [0.0] * NUM_OUTPUTS)),
            input_offsets=dict(zip(range(1, NUM_INPUTS + 1), [0.0] * NUM_INPUTS)),
            version=1
    ):
        """ctor.
        parameters:
            output_offsets - offsets for output channels, dict of channel:offset. Default: all zero.
            input_offsets - offsets for input channels, dict of channel:offset. Default: all zero.
            version - OPX version. Default: 1.
        """
        self.qm_config = \
            {
                "version": version,
                "controllers":
                    {
                        "con1":
                            {
                                "type": "opx1",
                                "analog_outputs": {ch: {"offset": output_offsets[ch]} for ch in output_offsets.keys()},
                                "analog_inputs": {ch: {"offset": input_offsets[ch]} for ch in input_offsets.keys()}
                            }
                    }
            }

    def get_config(self):
        return self.qm_config

    def add_mixer(self, mixer_name, corrections_dict):
        """Add a mixer with a given name.
        correction_dict is a dict of correction matrices: (lo_freq, if_freq):[V_00, V_01, V_10, V_01]
        """

        if not "mixers" in self.qm_config:
            self.qm_config["mixers"] = {}

        if mixer_name in self.qm_config["mixers"]:
            raise Exception("ConfigGenerator.add_mixer: mixer %s already exists" % mixer_name)
        self.qm_config["mixers"][mixer_name] = [{"intermediate_frequency": k[1], "lo_frequency": k[0], "correction": v}
                                                for (k, v) in corrections_dict.items()]

    def add_mixed_input_element(self, element_name, freq, lo_freq, I_channel, Q_channel, mixer_name):
        """Add an input element which uses  IQ mixing with a given name, frequency [Hz], local oscillator frequency [Hz],
        I and Q channels and mixer. Prerequisites: A mixer "mixer_name".
        """

        if not "elements" in self.qm_config:
            self.qm_config["elements"] = {}

        if element_name in self.qm_config["elements"]:
            raise Exception("ConfigGenerator.add_mixed_input_element: element %s already exists" % element_name)

        self.qm_config["elements"][element_name] = \
            {
                "mixInputs":
                    {
                        "I": ("con1", I_channel),
                        "Q": ("con1", Q_channel),
                        "mixer": mixer_name,
                        "lo_frequency": lo_freq
                    },
                "intermediate_frequency": freq - lo_freq
            }

        # if not (self.qm_config.has_key("mixers") and self.qm_config["mixers"].has_key(mixer_name)):
        #     raise Exception("ConfigGenerator.add_mixed_input_element: Mixer %s for element %s does not exist" %
        #         mixer_name, element_name)

    def add_single_input_element(self, element_name, freq, channel):
        """Add an input element which uses  a single input with a given name, frequency [Hz],
        and channel.
        """

        if not "elements" in self.qm_config:
            self.qm_config["elements"] = {}

        if element_name in self.qm_config["elements"]:
            raise Exception("ConfigGenerator.add_single_input_element: element %s already exists" % element_name)

        self.qm_config["elements"][element_name] = \
            {
                "singleInput": {"port": ("con1", channel)},
                "intermediate_frequency": freq
            }

    def add_mixed_readout_element(self, element_name, freq, lo_freq, input_I_channel, input_Q_channel, output_channels,
                                  mixer_name, time_of_flight, smearing=0):
        """Add a readout element which uses IQ mixing for pulse generating with a given name, frequency [Hz] , local oscillator frequency [Hz],
        input I and Q channels, output_channel(s), mixer, time of flight [ns] and smearing [ns, default=0].
        output_channels is a dict of channel_name:channel_number.
        Prerequisites: A mixer "mixer_name".
        """

        self.add_mixed_input_element(element_name, freq, lo_freq, input_I_channel, input_Q_channel, mixer_name)

        self.qm_config["elements"][element_name]["time_of_flight"] = time_of_flight
        self.qm_config["elements"][element_name]["smearing"] = smearing
        self.qm_config["elements"][element_name]["outputs"] = {channel_name: ("con1", output_channels[channel_name]) for
                                                               channel_name in output_channels.keys()}

    # TODO: waveforms with calibrations

    def add_arbitrary_waveform(self, waveform_name, samples):
        """Add an arbitrary waveform from samples.
        """

        if not "waveforms" in self.qm_config:
            self.qm_config["waveforms"] = {}

        if waveform_name in self.qm_config["waveforms"]:
            raise Exception("ConfigGenerator.add_arbitrary_waveforms: waveform %s already exists" % waveform_name)
        self.qm_config["waveforms"][waveform_name] = {"type": "arbitrary", "samples": samples}

    def add_constant_waveform(self, waveform_name, value):
        """Add a constant waveform from value.
        """

        if not "waveforms" in self.qm_config:
            self.qm_config["waveforms"] = {}

        if waveform_name in self.qm_config["waveforms"]:
            raise Exception("ConfigGenerator.add_constant_waveform: waveform %s already exists" % waveform_name)
        self.qm_config["waveforms"][waveform_name] = {"type": "constant", "sample": value}

    def add_mixed_control_pulse(self, pulse_name, length, waveforms,
                                trigger_type=None, trigger_delay=0, trigger_length=0):
        """Add a control pulse for a mixed element
        length is in ns.
        waveforms is a list of waveform names [I_waveform, Q_waveform]
        trigger_type: TriggerType.RISING_TRIGGER/TriggerType.FALLING_TRIGGER/None
        """

        if not "pulses" in self.qm_config:
            self.qm_config["pulses"] = {}

        if pulse_name in self.qm_config["pulses"]:
            raise Exception("ConfigGenerator.add_mixed_control_pulse: pulse %s already exists" % pulse_name)
        self.qm_config["pulses"][pulse_name] = {"operation": "control", "length": length,
                                                "waveforms": {"I": waveforms[0], "Q": waveforms[1]}}
        if trigger_type is not None:
            # create a digital waveform as a marker
            digital_waveform_name = ("%s_marker" % pulse_name)
            self.qm_config["pulses"][pulse_name]["digital_marker"] = digital_waveform_name
            trigger_on = 1 if trigger_type is self.TriggerType.RISING_TRIGGER else 0
            trigger_off = 0 if trigger_type is self.TriggerType.RISING_TRIGGER else 1
            if not "digital_waveforms" in self.qm_config:
                self.qm_config["digital_waveforms"] = {}
            self.qm_config["digital_waveforms"][digital_waveform_name] = {}
            self.qm_config["digital_waveforms"][digital_waveform_name]["samples"] = [(1, 0)]  # [
            #     (trigger_off, trigger_delay), (trigger_on, trigger_length), (trigger_off, 0)
            # ]
            print("config_generator.add_mixed_control_pulse: Warning: trigger_length and trigger_delay are not used!")

    def add_single_control_pulse(self, pulse_name, length, waveform):
        """Add a control pulse for a single output element
        length is in ns.
        waveform is the waveform name
        """

        if not "pulses" in self.qm_config:
            self.qm_config["pulses"] = {}

        if pulse_name in self.qm_config["pulses"]:
            raise Exception("ConfigGenerator.add_single_control_pulse: pulse %s already exists" % pulse_name)
        self.qm_config["pulses"][pulse_name] = {"operation": "control", "length": length,
                                                "waveforms": {"single": waveform}}

    def add_operation(self, element_name, operation_name, pulse_name):
        """Add an operation linked to a specific pulse to a given element
        """

        if not "operations" in self.qm_config["elements"][element_name]:
            self.qm_config["elements"][element_name]["operations"] = {}

        if operation_name in self.qm_config["elements"][element_name]["operations"]:
            raise Exception("ConfigGenerator.add_operation: operation %s for element %s already exists" % (
                operation_name, element_name))
        self.qm_config["elements"][element_name]["operations"][operation_name] = pulse_name

    def add_integration_weight(self, weight_name, cos_weight, sin_weight):
        """Add an integration_weight with given cosine and sine weights
        """

        if not "integration_weights" in self.qm_config:
            self.qm_config["integration_weights"] = {}

        if weight_name in self.qm_config["integration_weights"]:
            raise Exception(
                "ConfigGenerator.add_integration_weight: add_integration weight %s already exists" % weight_name)

        self.qm_config["integration_weights"][weight_name] = {}
        self.qm_config["integration_weights"][weight_name]["cosine"] = cos_weight
        self.qm_config["integration_weights"][weight_name]["sine"] = sin_weight

    def add_mixed_measurement_pulse(self, pulse_name, length, waveforms, integration_weights,
                                    trigger_type=None, trigger_delay=0, trigger_length=0):

        """Add a measurement pulse for a mixed element
        length is in ns.
        waveforms is a list of waveform names [I_waveform, Q_waveform]
        integration_weights is a dict "integration_weight acronym":"integration weight name"
        trigger_type: TriggerType.RISING_TRIGGER/TriggerType.FALLING_TRIGGER/None
        """

        self.add_mixed_control_pulse(pulse_name, length, waveforms,
                                     trigger_type, trigger_delay, trigger_length)
        self.qm_config["pulses"][pulse_name]["operation"] = "measurement"
        self.qm_config["pulses"][pulse_name]["integration_weights"] = integration_weights

# TODO: add pulse - mixed / not mixed
