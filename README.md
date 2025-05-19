# teom_areg_logger

A simple Python-based logger and dashboard for the **TEOM 1400AB** air quality monitor.  
This tool logs data from the TEOM via serial port and stores daily CSV files.  
A browser-based dashboard provides real-time and historical data visualization.

---

## 🚀 Usage

1. **Clone or copy** the repository to your desired directory.
2. **Install dependencies** using:
   ```bash
   pip install -r requirements.txt
   ```
3. **Edit the serial port** in `teom_areg_logger.py` to match your system:
   ```python
   SERIAL_PORT = 'COM30'  # Change to your TEOM's port
   ```
4. **Start the logger**:
   ```bash
   python teom_areg_logger.py
   ```
5. **In a second terminal**, start the dashboard server:
   ```bash
   python teom_dashboard.py
   ```
6. **Open your browser** and go to: [http://127.0.0.1:8050](http://127.0.0.1:8050)

---

## 🐛 Troubleshooting

If you encounter this error:
```
AttributeError: module 'typing_extensions' has no attribute 'Generic'
```
Fix it by upgrading the package:
```bash
pip install --upgrade typing_extensions
```

---

## ⚙️ Configuration

A `config.ini` file is planned. For now, configuration is done by editing the Python scripts directly.

### `teom_areg_logger.py`

| Variable              | Description                                                    | Default      |
|-----------------------|----------------------------------------------------------------|--------------|
| `SERIAL_PORT`         | Serial port connected to the TEOM                              | `'COM30'`    |
| `QUERY_INTERVAL_SECONDS` | Data logging interval (in seconds)                         | `10`         |
| `LOG_DIR`             | Folder where daily CSV logs are saved                          | `'logs'`     |

### `teom_dashboard.py`

| Variable              | Description                                                    | Default      |
|-----------------------|----------------------------------------------------------------|--------------|
| `LOG_DIR`             | Directory where CSV logs are located                           | `'logs'`     |
| `UNFILTERED_STEPS`    | Number of samples (back in time) to compute unfiltered mass    | `30`         |

---

## 🧪 About the Derived Mass Concentration

The TEOM reports:
- 30-minute average mass concentration
- 1-hour average mass concentration
- A smoothed 5-minute running average

However, the smoothed 5-minute value is filtered and may exclude short-term fluctuations.  
The dashboard calculates a parallel **unfiltered running average** using:

### **Derived Mass Concentration (µg/m³)**
Calculated from the frequency change over time:

```
K0 × (1/f1² − 1/f0²) × 10^9 / flow / Δt
```

Where:
- `f0` is the frequency in hz from `UNFILTERED_STEPS` measurements ago (configurable)
- `f1` is the current frequency in hz
- `K0` is the TEOM calibration constant
- `flow` is the current main flow in lpm
- `Δt` is the time in minutes between `f0` and `f1`

You can adjust the `UNFILTERED_STEPS` to match the averaging period you want (e.g. 30 steps at 10s = 5 min).

Refer to the TEOM 1400AB manual (Appendices B and C) for register definitions and formula references.

---

## 📄 License

This project is licensed under the GNU General Public License v3.0.  
See [LICENSE](LICENSE) for full terms.
