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
        time.sleep(1)
        self.conn.flushInput()

    def send_command(self, command: str):
        self.logger.info(f'>>> {command}')
        self.conn.write(str.encode(command))
        idle_counter = 0
        while True:
            command = str.encode('?' + '\n')
            self.conn.reset_input_buffer()
            self.conn.write(command)
            grbl_out = self.conn.readline()
            grbl_response = grbl_out.strip().decode('utf-8')
            if 'Error' in grbl_response or 'Reset' in grbl_response or 'ALARM' in grbl_response:
                self.logger.error('Destruction move!!!')
                raise Exception('Destruction move!!!')
            if grbl_response != 'ok':
                if grbl_response.find('Idle') > 0:
                    idle_counter += 1
            if idle_counter > 10:
                break

    def set_zero(self):
        self.send_command('G10 P0 L20 X0 Y0 Z0')

    def go_to(self, x, y, f=2000):
        command = f'G0X{x}Y{y}F{f}'
        self.send_command(command)

    def home(self):
        self.send_command('$H')

    def reset(self):
        self.conn.setDTR(False)  # Drop DTR
        time.sleep(0.022)  # Read somewhere that 22ms is what the UI does.
        self.conn.setDTR(True)  # UP the DTR back
        self.send_command('$X')


    def go_to_zero(self):
        command = f'G90G0X0Y0'
        self.send_command(command)

    def jog(self, d_x, d_y, f=4000):
        # silent to ALARM)))
        self.send_command(f'$J=G21G91X{d_x}Y{d_y}F{f}')

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
    g.home()

    # try:
    #     g.go_to(10, 10)
    # except Exception as e:
    #     g.reset()
    #     g.home()
    #     g.go_to(-10, -10)
    #
    exit(0)
