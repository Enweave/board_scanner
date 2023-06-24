import time

import serial
import logging

from tools.uart import serial_ports

BAUD_RATE = 115200

class GRBL:
    logger = logging.getLogger('GRBL')
    logger.setLevel(logging.DEBUG)

    def __init__(self, port: str = None):
        assert port
        self.port = port
        self.conn = serial.Serial(port, BAUD_RATE)
        self.logger.info(f'{self.conn.port} is connected')

    def send_wake_up(self):
        self.logger.info(f'Wake up Neo...')
        self.conn.write(str.encode("\r\n\r\n"))
        time.sleep(2)
        self.conn.flushInput()

    def send_command(self, command: str):
        self.logger.info(f'>>> {command}')
        self.conn.write(str.encode(command))
        time.sleep(0.01)
        idle_counter = 0
        while True:
            time.sleep(0.001)
            self.conn.reset_input_buffer()
            command = str.encode('?' + '\n')
            self.conn.write(command)
            grbl_out = self.conn.readline()
            grbl_response = grbl_out.strip().decode('utf-8')
            if grbl_response != 'ok':
                if grbl_response.find('Idle') > 0:
                    idle_counter += 1
            if idle_counter > 10:
                break

    def set_zero(self):
        command = 'G10 P0 L20 X0 Y0 Z0'
        self.send_command(command)

    def go_to(self, x, y, f=2000):
        command = f'G0X{x}Y{y}F{f}'
        self.send_command(command)

    def go_to_zero(self):
        command = f'G90G0X0Y0'
        self.send_command(command)

    def jog(self, d_x, d_y, f=4000):
        command = f'$J=G21G91X{d_x}Y{d_y}F{f}'
        self.send_command(command)

    def __del__(self):
        try:
            self.conn.close()
            self.logger.info(f'{self.conn.port} has been closed')
        except:
            pass


if __name__ == '__main__':
    # TODO
    logging.info("start")
    
    print(serial_ports())
    g = GRBL("COM6")
    g.send_wake_up()
    g.set_zero()
    g.jog(-10, 0)
    g.go_to(10, 10)
    g.go_to_zero()
    exit(0)
