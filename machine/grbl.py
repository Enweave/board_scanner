import random
import re
import time
import serial
from tools.uart import serial_ports
from decimal import *
getcontext().prec = 3

BAUD_RATE = 115200


class GRBL:
    STATUS_REGEX = r"""<(?P<State>Idle|Run|Hold|Home|Alarm|Check|Door|Jog)(?:,MPos:(?P<MX>-?[0-9\.]*),(?P<MY>-?[0-9\.]*),(?P<MZ>-?[0-9\.]*))?(?:,WPos:(?P<WX>-?[0-9\.]*),(?P<WY>-?[0-9\.]*),(?P<WZ>-?[0-9\.]*))?(?:,Buf:(?P<Buf>[0-9]*))?(?:,RX:(?P<RX>[0-9]*))?(?:,Ln:(?P<L>[0-9]*))?(?:,F:(?P<F>-?[0-9\.]*))?(?:,Lim:(?P<Lim>[0-1]*))?(?:,Ctl:(?P<Ctl>[0-1]*))?(?:,FS:(?P<FS1>[0-9]*),(?P<FS2>[0-9]*))?(?:,Ov:(?P<OvFeed>-?[0-9\.]*),(?P<OvRapid>-?[0-9\.]*),(?P<OvSpindle>-?[0-9\.]*))?(?:,WCO:(?P<WCX>-?[0-9\.]*),(?P<WCY>-?[0-9\.]*),(?P<WCZ>-?[0-9\.]*))?>"""

    def __init__(self, port: str = None):
        assert port
        self.port = port
        self.conn = serial.Serial(port, BAUD_RATE)
        self.status_matcher = re.compile(self.STATUS_REGEX)
        self.state = None
        self._wait_ok = False
        self._ok = False
        self.machine_position = 0, 0, 0
        self.work_position = 0, 0, 0

    def __del__(self):
        try:
            self.conn.close()
        except:
            pass

    @staticmethod
    def _xyz_to_decimal(xyz):
        return Decimal(xyz[0]), Decimal(xyz[1]), Decimal(xyz[2])

    def read_machine(self):
        while self.conn.in_waiting != 0:
            grbl_response = self.conn.readline().strip().decode('utf-8')
            result = self.status_matcher.match(grbl_response.replace('|', ','))
            if result:
                self.state = result.group('State')
                received_machine_position = result.group('MX'), result.group('MY'), result.group('MZ')
                received_work_position = result.group('WX'), result.group('WY'), result.group('WZ')
                received_offset_position = result.group('WCX'), result.group('WCY'), result.group('WCZ')

                if received_machine_position[0]:
                    self.machine_position = self._xyz_to_decimal(received_machine_position)
                    if received_offset_position[0]:
                        # WPos = MPos - WCO
                        offset_x, offset_y, offset_z = self._xyz_to_decimal(received_offset_position)
                        self.work_position = \
                            self.machine_position[0] - offset_x, \
                            self.machine_position[1] - offset_y,\
                            self.machine_position[2] - offset_z

                if received_work_position[0]:
                    if received_offset_position[0]:
                        self.work_position = self._xyz_to_decimal(received_work_position)
                        # MPos = WPos + WCO
                        offset_x, offset_y, offset_z = self._xyz_to_decimal(received_offset_position)
                        self.machine_position = \
                            self.work_position[0] + offset_x, \
                            self.work_position[1] + offset_y, \
                            self.work_position[2] + offset_z,

            elif grbl_response == 'ok':
                self._ok = True
            else:
                print(grbl_response)

    def send_command(self, command: str, wait_ok=True):
        self.conn.flushInput()
        print(command)
        self.conn.write(str.encode(command + '\n'))
        self._ok = False
        while wait_ok and not self._ok:
            self.read_machine()

    def update_status(self):
        self.send_command('?', True)
        self.read_machine()
        print('S', self.state, ' | M:', self.machine_position[0], self.machine_position[1], ' | W:', self.work_position[0], self.work_position[1])

    def wake_up(self):
        self.send_command("\r\n\r\n", wait_ok=False)
        time.sleep(3)
        self.conn.flushInput()

    def set_zero(self):
        self.send_command('G10 P0 L20 X0 Y0 Z0')

    def go_to(self, x, y, f=1000):
        command = f'G0X{x}Y{y}F{f}'
        self.send_command(command)

    def home(self):
        self.send_command('$H')

    def unlock(self):
        self.send_command('$X')

    def reset(self):
        self.conn.setDTR(False)  # Drop DTR
        time.sleep(0.022)  # Read somewhere that 22ms is what the UI does.
        self.conn.setDTR(True)  # UP the DTR back

    def go_to_zero(self):
        command = f'G90G0X0Y0'
        self.send_command(command)

    def jog(self, d_x, d_y, f=2000):
        self.send_command(f'$J=G21G91X{d_x}Y{d_y}F{f}', False)


if __name__ == '__main__':
    print(serial_ports())
    g = GRBL("/dev/ttyUSB0")
    g.reset()
    g.wake_up()
    g.unlock()
    g.home()
    g.set_zero()
    g.jog(-20, -30, f=2000)
    g.set_zero()
    g.jog(5, 7, f=2000)
    while True:
        time.sleep(1)
        g.update_status()
        if random.randint(0, 5) == 4:
            g.jog(random.randint(-30, 30), random.randint(-30, 30), f=1000)
        if random.randint(0, 50) == 5:
            g.set_zero()