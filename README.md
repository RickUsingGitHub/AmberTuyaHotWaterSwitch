# Amber Alarm & Hot Water Monitor

A Tkinter-based desktop application that monitors real-time electricity prices from Amber Electric and controls a hot water system via a Tuya smart plug.

## Features

- **Real-time Price Monitoring**: Displays current electricity price (c/kWh) from Amber Electric.
- **Price Alerts**: Visual color coding (Green/Yellow/Red) and audio alerts based on user-defined thresholds.
- **Hot Water Control**: Toggle your hot water system via a Tuya smart plug.
- **Mute Functionality**: Temporarily mute audio alerts for a set duration or during night hours.
- **Customizable Thresholds**: Set your own "Low" (Green) and "High" (Yellow) price thresholds.

## Configuration

The application uses a single `config.json` file for all settings.

### `config.json` Structure

```json
{
    "AMBER_API_TOKEN": "your_amber_api_token",
    "AMBER_SITE_ID": null,
    "TUYA_DEVICE_ID": "your_tuya_device_id",
    "TUYA_IP_ADDRESS": "your_tuya_device_ip",
    "TUYA_LOCAL_KEY": "your_tuya_local_key",
    "TUYA_VERSION": 3.4,
    "REFRESH_RATE": 60,
    "WINDOW_SIZE": "1142x410",
    "CHEER_SOUND_FILE": "Cheer.wav",
    "ALARM_SOUND_FILE": "Alarm.wav",
    "MUTE_START_HOUR": 23,
    "MUTE_END_HOUR": 8,
    "low_thresh": 15.0,
    "high_thresh": 30.0
}
```

- **AMBER_API_TOKEN**: Your API token from Amber Electric.
- **AMBER_SITE_ID**: (Optional) Your site ID. If null, it will be fetched automatically.
- **TUYA_DEVICE_ID**, **TUYA_IP_ADDRESS**, **TUYA_LOCAL_KEY**: Configuration for your Tuya smart plug.
- **low_thresh**: Prices below this value are considered "Green".
- **high_thresh**: Prices below this value (but above low_thresh) are considered "Yellow". Prices above this are "Red".

## Usage

1.  Ensure you have Python installed.
2.  Install dependencies (see `requirements.txt` if available, or install `requests`, `tinytuya`, `tk`).
3.  Configure `config.json` with your credentials.
4.  Run the application:
    ```bash
    python AmberTuyaHotWaterAlarm.pyw
    ```

## Settings

You can adjust the price thresholds directly in the application interface. These changes are saved back to `config.json`.
