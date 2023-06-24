from modules.app import ScannerApp


if __name__ == '__main__':
    app = ScannerApp(webcam_index=1)
    app.run()
    app.__del__()
