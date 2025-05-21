import serial
import time
from datetime import datetime, timedelta
from pathlib import Path
import configparser

# === Load Configuration ===
config = configparser.ConfigParser(interpolation=None)
config.read('config.ini')

SERIAL_PORT = config['LOGGER']['serial_port']
BAUD_RATE = int(config['LOGGER']['baud_rate'])
QUERY_INTERVAL_SECONDS = int(config['LOGGER']['query_interval_seconds'])
TIME_FORMAT = config['LOGGER']['time_format']
LOG_DIR = Path(config['LOGGER']['log_dir'])
LOG_DIR.mkdir(exist_ok=True)

def get_log_file_path():
    today_str = datetime.now().strftime('%Y-%m-%d')
    return LOG_DIR / f'teom_log_{today_str}.csv'

# === Register Definitions ===
REGISTER_DEFINITIONS = [
    {'code':   '8', 'label': 'Mass Concentration', 'unit': 'µg/m³'},
    {'code':   '7', 'label': 'Mass Rate', 'unit': 'µg/h'},
    {'code':   '9', 'label': 'Total Mass', 'unit': 'µg'},
    {'code':  '12', 'label': 'Frequency', 'unit': 'hz'},
    {'code':  '13', 'label': 'Noise', 'unit': 'µg'},
    {'code':  '35', 'label': 'Filter Loading', 'unit': '%'},
    {'code':  '39', 'label': 'Main Flow', 'unit': 'lpm'},
    {'code':  '40', 'label': 'Aux Flow', 'unit': 'lpm'},
    {'code':  '41', 'label': 'Status', 'unit': 'code'},
    {'code':  '42', 'label': 'K0 Constant', 'unit': 'g/s²'},
    {'code':  '57', 'label': 'Mass Concentration (30min Avg)', 'unit': 'µg/m³'},
    {'code':  '58', 'label': 'Mass Concentration (1hr Avg)', 'unit': 'µg/m³'},
    {'code':  '63', 'label': 'Serial Number', 'unit': 'N/A'},
    {'code': '130', 'label': 'Ambient Temperature', 'unit': '°C'},
    {'code': '131', 'label': 'Ambient Pressure', 'unit': 'atm'},
]

def send_areg_query(ser, reg_code, retries=2):
    """
    Send an AREG command and return the response value.
    Format: <STX><station number>AREG K0 xxx<ETX>
    Response: <STX><station number>AREG <status number> xxx value
    Error Response: <STX><station number>AREG <status number> SE<EXT><CR><LF>
    STX = Start of text = <chr2>
    ETX = End of text   = <chr3>
    Station number can be any random number
    XXX is the reg_code. Can be a single digit. It should not be filled to the right.
    value is the current value of the variable inquired through AREG query. Note: Varying length.
    status number = current Status condition (i.e. AREG code 41)
    """
    for _ in range(retries):
        try:
            command = f'4AREG K0 {reg_code}'
            command = chr(2) + command + chr(3)
            ser.write(command.encode('ascii'))
            time.sleep(0.001)
            response = ser.readline().decode('ascii', errors='ignore').strip()
            if response.split(' ')[0].endswith('AREG'):
                value = response.split(' ')[-1][:-1]
                # Check error
                return 'SE' if value.startswith('SE') else value
        except Exception:
            time.sleep(0.1)
    return 'ERR'

def log_teom_registers():
    try:
        with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=2) as ser:
            current_day = datetime.now().date()
            log_file_path = get_log_file_path()
            if not log_file_path.exists():
                with open(log_file_path, 'w', encoding='utf-8') as f:
                    header = ['Timestamp'] + [f"{reg['label']} ({reg['unit']})" for reg in REGISTER_DEFINITIONS]
                    f.write(','.join(header) + '\n')
                print(f"[INFO] Logging TEOM AREG data to {log_file_path} every {QUERY_INTERVAL_SECONDS} seconds.")

            while True:
                if datetime.now().date() != current_day:
                    current_day = datetime.now().date()
                    log_file_path = get_log_file_path()
                    if not log_file_path.exists():
                        with open(log_file_path, 'w', encoding='utf-8') as f:
                            header = ['Timestamp'] + [f"{reg['label']} ({reg['unit']})" for reg in REGISTER_DEFINITIONS]
                            f.write(','.join(header) + '\n')
                        print(f"[INFO] Logging TEOM AREG data to {log_file_path} every {QUERY_INTERVAL_SECONDS} seconds.") 
                            
                with open(log_file_path, 'a') as logfile:               
                    query_time = datetime.now()
                    current_day = query_time.date()
                    log_file_path = get_log_file_path()
                    next_query = query_time + timedelta(seconds=QUERY_INTERVAL_SECONDS)
                    
                    timestamp = query_time.strftime(TIME_FORMAT)
                    values = []
                    for reg in REGISTER_DEFINITIONS:
                        val = send_areg_query(ser, reg['code'])
                        values.append(val if val else 'NaN')
                    log_line = f"{timestamp}," + ','.join(values)
                    print(log_line)
                    logfile.write(log_line + '\n')
                    logfile.flush()
                    sleep_time = (next_query - datetime.now()).total_seconds()
                    time.sleep(sleep_time)

    except serial.SerialException as e:
        print(f"[ERROR] Serial port error: {e}")
    except KeyboardInterrupt:
        print("\n[INFO] Logging stopped by user.")
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")

if __name__ == '__main__':
    log_teom_registers()
