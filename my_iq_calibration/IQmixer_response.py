import numpy as np
from qm import QuantumMachinesManager
from qm.qua import *
from time import sleep
from matplotlib import pyplot as plt
import instruments_py27.spectrum_analyzer as SA
import instruments_py27.anritsu as MG

# parameters
num_points = 31  # angular points to test response
averaging = True
amp = 0.2  # I,Q amplitude

# mg_address = "GPIB0::7::INSTR"
sa_address = 'USB0::0x0957::0x0B0B::MY47191316::INSTR'

lo_freq = 4996.9
lo_amp = 10.0

# OPX ports to which the I,Q ports of the IQ mixer are connected
I_port = 1
Q_port = 2

# offset
I0 = 0.020397949218750006
Q0 = 0.015197753906250005


def open_qm():
    qmManager = QuantumMachinesManager("192.168.137.43", 9510)

    return qmManager.open_qm({
        "version": 1,
        "controllers": {
            "con1": {
                "type": "opx1",
                "analog_outputs": {
                    I_port: {"offset": 0.0},
                    Q_port: {"offset": 0.0}
                }
            }
        },
        "elements": {
            "RR1": {
                "singleInput": {
                    "port": ("con1", I_port)
                },
                "intermediate_frequency": 0.0,
                "operations": {
                    "pulse": "my_pulse"
                }
            },
            "RR2": {
                "singleInput": {
                    "port": ("con1", Q_port)
                },
                "intermediate_frequency": 0.0,
                "operations": {
                    "pulse": "my_pulse"
                }
            }
        },
        "pulses": {
            "my_pulse": {
                "operation": "control",
                "length": 2000,
                "waveforms": {
                    "single": "zero_wave"
                }
            }
        },
        "waveforms": {
            "zero_wave": {
                "type": "constant",
                "sample": 0.0
            }
        }
    })


def getWithIQ(IQ, qm, sa, averaging=False, verbose=False):
    """Sets DAC output to I=IQ[0] and Q=IQ[1] and measures with spectrum analyzer"""
    if verbose:
        print("Setting I=%f, Q=%f" % (IQ[0], IQ[1]))
    qm.set_output_dc_offset_by_element("RR1", "single", float(IQ[0]))
    qm.set_output_dc_offset_by_element("RR2", "single", float(IQ[1]))
    if averaging:
        sa.restart_averaging()
        sleep(1.0)
    else:
        sleep(0.2)
    sa.set_marker_max()
    t = sa.get_marker()

    if verbose:
        print("Transmitted power is %f dBm" % t)
    return t


def plot_ellipse(plt, theta, volt, title, figs=[None, None]):
    plt.figure(figs[0])
    # plt.plot(volt * np.cos(theta), volt * np.sin(theta))
    plt.polar(theta, volt)
    # plt.xlabel('I')
    # plt.ylabel('Q')
    # plt.axis('square')
    plt.title(title)

    plt.figure(figs[1])
    plt.plot(theta / np.pi / 2, volt)
    plt.xlabel("$\Theta/2\pi$")
    plt.ylabel("Voltage ($\sqrt{10^{P/10}\cdot 50}$)")
    plt.title(title)


# -------------------program-----------------
plt.ion()

# mg = MG.Anritsu_MG(mg_address)
# mg.setup_MG(lo_freq, lo_amp)
# init spectrum analyzer
sa = SA.N9010A_SA(sa_address)
sa.setup_spectrum_analyzer(center_freq=lo_freq, span=50e6, BW=1e5, points=501)

if averaging:
    sa.setup_averaging(True, 4)
else:
    sa.setup_averaging(False)

qm = open_qm()
#
with program() as prog:
    with infinite_loop_():
        play("pulse", "RR1")
        play("pulse", "RR2")

job = qm.execute(prog)

# get response
theta = np.linspace(0, 2 * np.pi, num_points)
power = np.zeros(theta.shape)
I = amp * np.cos(theta)
Q = amp * np.sin(theta)

print("Getting response...")
getWithIQ([I0, Q0], qm, sa)  # to prevent problems
for i, idx in enumerate(range(len(theta))):
    print(f'{i} / {num_points} ')
    iq = [I[idx] + I0, Q[idx] + Q0]
    # iq = [I[idx], Q[idx]]
    power[idx] = getWithIQ(iq, qm, sa, averaging=averaging)
#
volt = np.sqrt(10 ** (power / 10.0) * 50)

# plot
plot_ellipse(plt, theta, volt, "Uncalibrated", [1, 2])
plt.show()
# %% calibrate angle - set maximal voltage to theta=0
theta0 = theta[volt.argmax()]
c = np.cos(theta0)
s = np.sin(theta0)
rot = np.array([[c, -s], [s, c]])  # rotation matrix

print("Getting response with angular correction...")
getWithIQ([I0, Q0], qm, sa)  # to prevent problems
for idx in range(len(theta)):
    iq = rot @ [I[idx], Q[idx]]
    power[idx] = getWithIQ(iq + [I0, Q0], qm, sa, averaging=averaging)

volt = np.sqrt(10 ** (power / 10.0) * 50)
# plot
plot_ellipse(plt, theta, volt, "Angular correction", [3, 4])
plt.show()

# %%
# calibrate scaling
# find long radius - volt at 0,pi (actually should be equal if symmetric around origin)
idx_pi = np.abs(theta - np.pi).argmin()
r_long = volt[idx_pi] + volt[0]
# find short radius - volt at +/- pi/2 (actually should be equal if symmetric around origin)
idx_pi_2 = np.abs(theta - np.pi / 2).argmin()
idx_3_pi_2 = np.abs(theta - 3 * np.pi / 2).argmin()
r_short = volt[idx_3_pi_2] + volt[idx_pi_2]

scaling_m = np.array([[r_short / r_long, 0.0], [0.0, 1.0]])

print("Getting response with all corrections...")
getWithIQ([I0, Q0], qm, sa)  # to prevent problems
for idx in range(len(theta)):
    iq = scaling_m @ rot @ [I[idx], Q[idx]]
    power[idx] = getWithIQ(iq + [I0, Q0], qm, sa, averaging=averaging)

volt = np.sqrt(10 ** (power / 10.0) * 50)
# plot
plot_ellipse(plt, theta, volt, "Corrected", [5, 6])
plt.show()

# %% #test model
theta_m = np.array([0, np.pi, np.pi / 2, 3 * np.pi / 2, np.pi / 4, 7 * np.pi / 4])
power_m = np.zeros(theta_m.shape)
I_m = amp * np.cos(theta_m)
Q_m = amp * np.sin(theta_m)
print("Getting response...")
getWithIQ([I0, Q0], qm, sa)  # to prevent problems
for idx in range(len(theta_m)):
    iq = [I_m[idx] + I0, Q_m[idx] + Q0]
    power_m[idx] = getWithIQ(iq, qm, sa, averaging=averaging)

volt_m = np.sqrt(10 ** (power_m / 10.0) * 50)
g_I = np.mean([volt_m[0], volt_m[1]])
g_Q = np.mean([volt_m[2], volt_m[3]])
x = volt_m[4] ** 2 - volt_m[5] ** 2
phi = np.arcsin(x / (2 * g_I * g_Q))
model = np.sqrt(
    g_I ** 2 * np.cos(theta) ** 2 + g_Q ** 2 * np.sin(theta) ** 2 + g_I * g_Q * np.sin(phi) * np.sin(2 * theta))
plt.figure(1)
plt.polar(theta, model, 'k')
plt.show()
#
# # idx_pi = np.abs(theta - np.pi).argmin()
# # g_I = np.mean([volt[idx_pi],volt[0]])
# # idx_pi_2 = np.abs(theta - np.pi/2).argmin()
# # idx_3pi_2 = np.abs(theta - 3*np.pi/2).argmin()
# # g_Q = np.mean([volt[idx_pi_2],volt[idx_3pi_2]])
# # idx_pi_4 = np.abs(theta - np.pi/4).argmin()
# # idx_7pi_4 = np.abs(theta - 7*np.pi/4).argmin()
# # x = (np.array([volt[idx_pi_4],volt[idx_7pi_4]])**2-0.5*(g_I**2+g_Q**2))/(g_I*g_Q)
# # phi = np.arcsin(np.mean([x[0],-x[1]]))
# # model = np.sqrt(g_I**2*np.cos(theta)**2+g_Q**2*np.sin(theta)**2+g_I*g_Q*np.sin(phi)*np.sin(2*theta))
# # plt.figure(1)
# # plt.polar(theta,model,'r')
#
# # inverse transformation
# scaling_m = np.array([[g_Q / g_I, 0], [0, 1]])
# rot_m = (1 / (np.cos(phi / 2) ** 2 - np.sin(phi / 2) ** 2)) * np.array(
#     [[np.cos(phi / 2), -np.sin(phi / 2)], [-np.sin(phi / 2), np.cos(phi / 2)]])
#
# print("Getting response with inverse transformation...")
# getWithIQ([I0, Q0], qm, sa)  # to prevent problems
# for idx in range(len(theta)):
#     iq = scaling_m @ rot_m @ ([I[idx], Q[idx]]) + [I0, Q0]
#     # iq = scaling_m @ rot_m @ ([I[idx]+I0, Q[idx]+Q0])
#     power[idx] = getWithIQ(iq, qm, sa, averaging=averaging)
#
# volt = np.sqrt(10 ** (power / 10.0) * 50)
#
# # plot
# plot_ellipse(plt, theta, volt, "Calibarted", [7, 8])
#
# # mg.set_on(False)
